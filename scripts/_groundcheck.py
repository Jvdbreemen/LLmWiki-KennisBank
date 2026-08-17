#!/usr/bin/env python3
"""_groundcheck.py - grounded verification: does the source say what the memory says?

Trap 1 of the autonomous review pipeline (TASK-195, design in
docs/superpowers/specs/2026-08-16-autonomous-memory-review-design.md). Asks a
local model ONE narrow question about an unverified memory: does a passage
from its own source transcript state this claim? A `supported` answer promotes
the memory to `current`; every other answer changes nothing here.

Why promotion may act on a single local verdict while retraction may not:
measured, not assumed. Across 210 checked verdicts the `supported` answer
never fabricated its evidence (upper bound 1.8%), and in the G0 calibration
all 51 of its promotions were confirmed supported-or-partial by an exhaustive
client-LLM reading (lower bound 93%), with zero confirmed-absent anywhere in
the sample. The `unsupported` answer, by contrast, was never right when
checked (0/20) -- from inside one passage a retrieval miss and a false memory
look identical. Hence: promote on supported, escalate everything else, demote
nothing.

Passage selection, both routes measured (TASK-163):
  - stamped: `source_chunk: "N/M"` makes the passage a lookup via
    _memory.chunk_from_stamp -- exact, no retrieval;
  - unstamped: IDF-shortlist of 8 chunks, 1500-char windows inside them, best
    4 by cosine against the claim, joined in reading order. 87.8% of the time
    this contains the claim's true source at the 6000-char budget the judge
    reads (vs 62.7% for whole-chunk selection).

Stdlib + _embeddings; LLM via the _llm seam (mockable). Fail-soft everywhere:
no transcript, no embedding, no parseable answer -> the memory simply stays
unverified for a later cycle.
"""
from __future__ import annotations

import collections
import json
import math
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _embeddings as emb  # noqa: E402
import _llmjson  # noqa: E402
import _memory  # noqa: E402
from _common import env_int  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

#: Bump on ANY change to VERIFY_SYSTEM; stamped into the promote log so every
#: promotion stays traceable to the prompt that caused it (same contract as
#: RECONCILE_PROMPT_VERSION / SUPERSEDE_PROMPT_VERSION).
#:
#: Since TASK-198 a bump also REOPENS the whole attempts map: `_judged_here`
#: gates on this number, so every settled memory becomes a candidate again at
#: once. That is the intent -- a new prompt is the one reason to expect a
#: different answer -- and the cost is bounded by VERIFY_PASS_CAP, so it lands
#: as a few sweeps of local LLM rather than one long run. Know that you are
#: buying it before you bump.
VERIFY_PROMPT_VERSION = 1

#: Byte-identical to the prompt the validation measured (TASK-163). The quote
#: request in `reason` is not cosmetic: it is what made 210 verdicts
#: mechanically checkable, and the audit view shows it per promotion.
VERIFY_SYSTEM = (
    "You check whether a PASSAGE from a work transcript supports a CLAIM that "
    "was extracted from it. Judge only what the passage says. Do not use your "
    "own knowledge, and do not judge whether the claim is still true today -- "
    "only whether this passage supports it.\n"
    "Answer with one of:\n"
    "- supported: the passage states this, or states it in other words.\n"
    "- partial: the passage supports part of the claim but the claim adds "
    "specifics the passage does not contain.\n"
    "- unsupported: the passage is about this subject but does not support the "
    "claim, or contradicts it.\n"
    "- not_found: the passage is about something else entirely, so this is the "
    "wrong passage rather than a wrong claim.\n"
    "Answer with JSON ONLY: {\"verdict\": \"supported|partial|unsupported|"
    "not_found\", \"reason\": \"<short, quote the passage where you can>\"}."
)

VERDICTS = ("supported", "partial", "unsupported", "not_found")

#: The judge reads at most this much passage; chunks run to 6000 chars.
PASSAGE_BUDGET = 6000
#: Window size for the unstamped route. 1500 chars beat whole chunks by 20+
#: points of hit@1 in the retrieval measurement -- granularity, not volume.
WINDOW_CHARS = 1500
WINDOW_OVERLAP = 300
#: Chunks the IDF stage keeps before anything is embedded. Costs 2.4 points of
#: coverage against embedding everything (87.8% vs 90.2%) and saves a
#: twentyfold in embeddings on a long transcript.
SHORTLIST = 8

#: Per-run cap for the sweep pass. Roughly 6-8s of local LLM per memory, so 40
#: is a few minutes riding after a sweep -- and the backlog is drained by the
#: CLI (kb-verify.py), not by making every sweep pay for history.
VERIFY_PASS_CAP = env_int("KB_VERIFY_CAP", 40)

#: How long a decisive verdict stands before the memory is offered again.
#: A verdict is a property of claim-against-passage, not a coin flip, so
#: re-asking within days buys nothing; a week is short enough that a changed
#: model still gets a second reading without anyone bumping a version.
VERIFY_RETRY_DAYS = env_int("KB_VERIFY_RETRY_DAYS", 7)

#: How long an INCONCLUSIVE outcome stands. `unparseable` says something about
#: the run and must expire fast; `no_transcript` is deterministic -- an empty
#: or truncated source yields an empty passage on every run, forever -- so it
#: may not be free either, or those memories park at the head of the `created`
#: sort and own the whole cap. Hours, not days.
VERIFY_RETRY_HOURS = env_int("KB_VERIFY_RETRY_HOURS", 6)

#: Where the decisive verdicts are remembered. A compact map, not a JSONL log
#: like the promote log: those are pruned by line count, and the line pruned
#: would be exactly the record that stops a re-judge. Not the memory's own
#: frontmatter either -- writing 40 memory files per sweep changes their
#: semantic_hash and forces the knowledge graph to re-extract them.
ATTEMPTS_FILE = "memory-verify-attempts.json"

#: Entries kept in that map, newest attempt first. Eviction is self-healing:
#: an evicted memory simply looks unjudged again, which costs one verdict.
ATTEMPTS_MAX = 5000

_WORD = re.compile(r"[a-z0-9_]{4,}")


def _windows(text: str, size: int = WINDOW_CHARS, overlap: int = WINDOW_OVERLAP):
    if len(text) <= size:
        return [text]
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + size])
        i += size - overlap
    return out


def _idf_shortlist(claim: str, chunks: list, k: int = SHORTLIST) -> list:
    """Indices of the k chunks with the most claim-specific term overlap.

    Weighted by inverse chunk frequency WITHIN the transcript, so boilerplate
    that appears in most chunks (injected command blocks, preambles) stops
    winning on sheer length. Purely lexical, hence cheap -- and hence blind
    across languages, which is priced in: the window rerank below is what
    carries cross-language cases (TASK-165 measured the split).
    """
    want = set(_WORD.findall(claim.lower()))
    if not want or not chunks:
        return list(range(min(k, len(chunks))))
    tokens = [set(_WORD.findall(c.lower())) for c in chunks]
    df = collections.Counter()
    for have in tokens:
        df.update(have & want)
    total = len(chunks)
    scored = [(sum(math.log(1 + total / (1 + df[w])) for w in (want & have)), i)
              for i, have in enumerate(tokens)]
    scored.sort(key=lambda t: -t[0])
    return [i for _s, i in scored[:k]]


def select_passage(claim: str, chunks: list) -> str:
    """The best PASSAGE_BUDGET characters of a transcript for judging `claim`.

    Retrieve on small windows, spend the budget on the best windows wherever
    they fall, hand them over in reading order so the judge sees a sequence
    rather than a ranking. Fail-soft: no embeddings -> first chunks, so the
    judge still gets SOMETHING and the verdict stays fail-safe (worst case a
    not_found, which changes nothing).
    """
    if not chunks:
        return ""
    if len(chunks) == 1:
        return chunks[0][:PASSAGE_BUDGET]
    keep = set(_idf_shortlist(claim, chunks))
    qv = emb.embed_query(claim)
    if qv is None:
        return "\n---\n".join(chunks[:2])[:PASSAGE_BUDGET]
    scored = []
    for i, c in enumerate(chunks):
        if i not in keep:
            continue
        for j, w in enumerate(_windows(c)):
            wv = emb.embed(w, kind="doc")
            if wv:
                scored.append((emb.cosine(qv, wv), i, j, w))
    if not scored:
        return "\n---\n".join(chunks[:2])[:PASSAGE_BUDGET]
    scored.sort(key=lambda t: -t[0])
    kept, used = [], 0
    for _s, i, j, w in scored:
        if used + len(w) > PASSAGE_BUDGET:
            break
        used += len(w)
        kept.append((i, j, w))
    kept.sort(key=lambda t: (t[0], t[1]))
    return "\n[…]\n".join(w for _i, _j, w in kept)


def verify_grounded(body: str, chunks: list, stamp: str = "") -> dict:
    """One grounded verdict for a memory body against its transcript chunks.

    Returns {"verdict", "reason", "route"}; verdict is one of VERDICTS,
    "unparseable", or "no_transcript" when no passage could be produced at
    all. Only "supported" may promote; the caller enforces that.
    """
    exact = _memory.chunk_from_stamp(stamp, chunks) if stamp else None
    if exact:
        passage, route = exact[:PASSAGE_BUDGET], "stamp"
    else:
        passage, route = select_passage(body, chunks), "windows"
    if not passage:
        return {"verdict": "no_transcript", "reason": "", "route": route}
    import _llm
    raw = _llm.generate(
        f"PASSAGE:\n{passage}\n\nCLAIM:\n{body}\n\nJudgement (JSON):",
        system=VERIFY_SYSTEM)
    obj = _llmjson.first_object(raw or "") or {}
    v = str(obj.get("verdict", "")).strip().lower()
    return {"verdict": v if v in VERDICTS else "unparseable",
            "reason": str(obj.get("reason", ""))[:300], "route": route}


def attempts_path() -> Path:
    return vault_root() / ".claude" / ATTEMPTS_FILE


def attempt_key(path) -> str:
    """The key a memory is remembered under: its vault-relative posix path.

    Not the bare stem. The memory scan is recursive and `09-memory/archive/`
    exists in real vaults, so two files can carry the same stem -- and then
    judging one would silently buy the other a cooldown it never earned.
    Falls back to the plain name for a path outside the vault, which only
    happens in a caller's own fixtures.
    """
    p = Path(path)
    try:
        return p.resolve().relative_to(vault_root().resolve()).as_posix()
    except (ValueError, OSError):
        return p.name


def load_attempts() -> dict:
    """The outcomes seen so far, keyed by vault-relative memory path.

    A missing file reads as "nothing judged yet". An UNREADABLE one does not
    quietly do the same: returning {} and then writing a single entry over the
    top would replace recoverable history with one record, so the bad file is
    moved aside for a human to look at first.
    """
    p = attempts_path()
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        data = None
    if isinstance(data, dict):
        return data
    try:
        p.replace(p.with_suffix(".corrupt"))
    except OSError:
        pass
    return {}


def outcome(verdict: str, ts: str = "",
            prompt_version: int = VERIFY_PROMPT_VERSION) -> dict:
    """One row of the attempts map."""
    return {"ts": ts or datetime.now(timezone.utc).isoformat(),
            "verdict": str(verdict), "prompt_version": prompt_version}


def _write_attempts(data: dict) -> None:
    p = attempts_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".kbva-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1, ensure_ascii=False)
        os.replace(tmp, p)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def record_attempts(items: dict) -> None:
    """Merge a batch of outcomes into the map in ONE read-modify-write.

    Writing per verdict made a full backlog drain rewrite a growing file once
    per memory -- quadratic I/O for bookkeeping, in a repo whose first rule is
    that the interactive path stays fast. Merging on read also bounds the
    damage when the sweep worker and the CLI overlap: the run that finishes
    second keeps its own records and loses at most the other's, which costs
    re-judging and never wrong data. Fail-soft: bookkeeping may not block a
    sweep.
    """
    items = {k: v for k, v in (items or {}).items() if k}
    if not items:
        return
    try:
        data = load_attempts()
        data.update(items)
        if len(data) > ATTEMPTS_MAX:
            data = dict(sorted(data.items(),
                               key=lambda kv: str(kv[1].get("ts", "")),
                               reverse=True)[:ATTEMPTS_MAX])
        _write_attempts(data)
    except Exception:
        pass


def record_attempt(key: str, verdict: str, ts: str = "",
                   prompt_version: int = VERIFY_PROMPT_VERSION) -> None:
    """One outcome, written straight through. Batch callers use record_attempts."""
    if not verdict:
        return
    record_attempts({key: outcome(verdict, ts, prompt_version)})


def _window(verdict: str) -> timedelta:
    """How long an outcome stands before the memory is offered again.

    A real verdict is about the memory and holds for days. Anything else is
    about the run or about a broken source, and expires in hours.
    """
    return (timedelta(days=VERIFY_RETRY_DAYS) if verdict in VERDICTS
            else timedelta(hours=VERIFY_RETRY_HOURS))


def _retry_due(rec: dict) -> bool:
    """Has a recorded outcome aged past its window? Unreadable stamp -> yes."""
    try:
        dt = datetime.fromisoformat(str(rec.get("ts", "")))
    except (TypeError, ValueError, AttributeError):
        return True
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - dt >= _window(str(rec.get("verdict", "")))


def _judged_here(rec) -> bool:
    """Was this outcome produced by the prompt trap 1 runs today?"""
    return (isinstance(rec, dict)
            and rec.get("prompt_version") == VERIFY_PROMPT_VERSION)


def is_settled(rec) -> bool:
    """Will trap 1 leave this memory alone on its own next run?

    ONE predicate, used by candidates() to pick and by rot_breakdown to
    report. The two answered this question differently until a review caught
    it: the report called every recorded memory final while the pass happily
    requeued the ones on an older prompt version or past their window, so the
    session-start message told the owner to decide by hand what the next
    sweep was about to redo anyway.
    """
    return _judged_here(rec) and not _retry_due(rec)


def _unverified_rows() -> list:
    """Every unverified memory whose source transcript is still on disk.

    One definition, shared by the sweep pass and kb-verify.py. It lived in
    both as a copied block until TASK-198; two copies of a selection rule is
    one drift away from the CLI and the sweep judging different sets.
    """
    v = vault_root()
    tdir = v / "01-raw" / "transcripts"
    rows = []
    for f in (v / "09-memory").glob("**/*.md"):
        try:
            fm, body = parse_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if fm.get("status") != "unverified":
            continue
        src = str(fm.get("source_session", "")).strip()
        if not src or not (tdir / src).exists():
            continue
        rows.append((str(fm.get("created", "")), f, " ".join(body.split()),
                     src, str(fm.get("source_chunk", "")).strip()))
    return rows


def candidates(max_n: int = VERIFY_PASS_CAP, retry_settled: bool = False) -> list:
    """The memories trap 1 should judge next, in the order that spends the cap best.

    Two tiers, because a verdict is stable: asking the same question of the
    same passage returns the same answer, so a memory already judged at this
    prompt version has no claim on the budget while anything unjudged waits.

      A. no decisive verdict at VERIFY_PROMPT_VERSION -- oldest `created`
         first, so capture order still drains first and nothing starves
         behind a stream of newer memories;
      B. judged longer than VERIFY_RETRY_DAYS ago -- oldest attempt first, so
         retries rotate rather than re-running the same head every time.

    This ORDERS, it never excludes. Trap 1 reads a selected passage where the
    client read (trap 2) reads the whole transcript, so the two disagree by
    construction, and trap 1 does promote memories the client graded
    `partial` -- on the vault that produced TASK-198 those were the only
    promotions still happening. Disqualifying them would have cured the
    symptom by stopping the cure.

    retry_settled ignores the cooldown, for the deliberate backlog drain;
    max_n=None means no cap at all, which is what that drain asks for.
    """
    att = load_attempts()
    rows = _unverified_rows()
    if max_n is None:
        max_n = len(rows)
    fresh, due = [], []
    for row in rows:
        rec = att.get(attempt_key(row[1]))
        if not _judged_here(rec):
            fresh.append(row)
        elif retry_settled or not is_settled(rec):
            due.append((str(rec.get("ts", "")), row))
    fresh.sort(key=lambda t: t[0])
    if len(fresh) >= max_n:
        return fresh[:max_n]
    due.sort(key=lambda t: t[0])
    return fresh + [row for _ts, row in due][:max_n - len(fresh)]


def verify_pass(max_n: int = VERIFY_PASS_CAP) -> int:
    """Promote unverified memories whose source supports them. Returns count.

    Touches ONLY status=unverified; promotes ONLY on `supported`; everything
    else is recorded and left for a later cycle or the client-LLM escalation.
    Never demotes -- that verdict class was measured wrong every time it was
    checked (0/20).
    """
    tdir = vault_root() / "01-raw" / "transcripts"
    import _sweepstate as ss
    import _sweeputil as su

    promoted = 0
    chunk_cache: dict = {}
    learned: dict = {}
    try:
        for _created, f, body, src, stamp in candidates(max_n):
            try:
                if src not in chunk_cache:
                    chunk_cache[src] = su.chunk(ss.transcript_text(tdir / src))
                r = verify_grounded(body, chunk_cache[src], stamp)
            except Exception:
                continue
            if r["verdict"] != "supported":
                learned[attempt_key(f)] = outcome(r["verdict"])
                continue
            # Nothing is recorded on the promoting branch. A promoted memory
            # leaves the unverified pool and can never be a candidate again,
            # and a REFUSED promote (locked or read-only file) is not a
            # settled memory: the write failed, the verdict did not. Recording
            # it would park a memory trap 1 wanted to promote, with nothing in
            # the promote log to show for it.
            if _memory.promote(f, reason=r["reason"], route=r["route"],
                               prompt_version=VERIFY_PROMPT_VERSION):
                promoted += 1
    finally:
        record_attempts(learned)
    return promoted
