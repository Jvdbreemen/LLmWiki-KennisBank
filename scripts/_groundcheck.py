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
    qv = emb.embed(claim, kind="query")
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


def verify_pass(max_n: int = VERIFY_PASS_CAP) -> int:
    """Promote unverified memories whose source supports them. Returns count.

    Oldest first, so the backlog drains in capture order and no memory can
    starve behind a stream of newer ones. Touches ONLY status=unverified;
    promotes ONLY on `supported`; everything else is left for a later cycle
    or the client-LLM escalation. Never demotes -- that verdict class was
    measured wrong every time it was checked (0/20).
    """
    v = vault_root()
    tdir = v / "01-raw" / "transcripts"
    import _sweepstate as ss
    import _sweeputil as su

    todo = []
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
        todo.append((str(fm.get("created", "")), f, " ".join(body.split()),
                     src, str(fm.get("source_chunk", "")).strip()))
    todo.sort(key=lambda t: t[0])

    promoted = 0
    chunk_cache: dict = {}
    for _created, f, body, src, stamp in todo[:max_n]:
        try:
            if src not in chunk_cache:
                chunk_cache[src] = su.chunk(ss.transcript_text(tdir / src))
            r = verify_grounded(body, chunk_cache[src], stamp)
        except Exception:
            continue
        if r["verdict"] != "supported":
            continue
        if _memory.promote(f, reason=r["reason"], route=r["route"],
                           prompt_version=VERIFY_PROMPT_VERSION):
            promoted += 1
    return promoted
