#!/usr/bin/env python3
"""kb-autoreview.py - trap 2/3 of the autonomous review: bundle and apply.

Trap 1 (grounded promotion, kb-verify) promotes what a memory's own passage
supports and escalates the rest. This tool handles the escalation: it BUNDLES
each still-unverified memory with its whole transcript for a client-LLM
reading, and APPLIES the returned verdicts under rules that live here, in
code — an adjudicating agent proposes, this script disposes.

The rules encode the measured asymmetry (TASK-163/195):
  - `supported` (evidence found anywhere in the transcript) -> promote, with
    the evidence quote in the promote log.
  - `absent` -> retraction ONLY when the independent refutation pass also
    failed to overturn it (refuted=false), capped per apply run, both
    verdicts in the closed-log, reversible with _memory.reopen(). One
    reader's `absent` alone changes nothing: the single-passage variant of
    that verdict measured 0/20 correct when checked.
  - anything else (`partial`, `unclear`, missing refutation) -> stays
    unverified for a later cycle. Undecidable cases are exactly the ones an
    autonomous system should not force.

PRIVACY GATE: bundling prepares memory bodies and transcripts for a CLIENT
LLM — content leaves the local machine when those bundles are read in a
session or by a headless client. Both subcommands therefore refuse unless the
owner set `auto_review_llm` (default OFF; "Lokaal, altijd" holds for every
vault whose owner has not said yes).

Usage:
  python3 kb-autoreview.py bundle [--max N]
      Write case bundles + manifest.json under
      <vault>/.claude/autoreview/<batch>/ and print the batch path.
  python3 kb-autoreview.py apply <results.json> [--retract-cap N]
      Apply verdicts. The results file is a JSON list of rows:
      {"stem": ..., "verdict": "supported|partial|absent|unclear",
       "evidence": "<verbatim quote>", "refuted": true|false|null}

The adjudication itself is driven by /kennisbank:autoreview (in-session
subagents) or any headless client that reads a bundle and writes the results
file. The verdict contract above is the whole interface, so the two paths
cannot drift apart.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _memory  # noqa: E402
import _settings  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

#: Hard ceiling on retractions per apply run. Retraction is the only
#: destructive act in the pipeline; a runaway result file may not take the
#: whole quarantine down with it.
RETRACT_CAP = 50

VALID_VERDICTS = ("supported", "partial", "absent", "unclear")


def _gate() -> bool:
    if not _settings.get("memory_capture", True):
        print("kb-autoreview: memory_capture is off; nothing to do")
        return False
    if not _settings.get("auto_review_llm", False):
        print("kb-autoreview: auto_review_llm is OFF. This path sends memory "
              "bodies and transcripts to the client LLM; enable it "
              "deliberately with:\n  _settings.py set auto_review_llm true",
              file=sys.stderr)
        return False
    return True


def _unverified_with_source():
    v = vault_root()
    tdir = v / "01-raw" / "transcripts"
    out = []
    for f in sorted((v / "09-memory").glob("**/*.md")):
        try:
            fm, body = parse_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if fm.get("status") != "unverified":
            continue
        src = str(fm.get("source_session", "")).strip()
        if not src or not (tdir / src).exists():
            continue
        # Body verbatim: claim.md promises "exactly as the memory states it",
        # and flattening whitespace would mangle lists and code blocks.
        out.append({"stem": f.stem, "path": str(f), "src": src,
                    "body": body.strip(),
                    "created": str(fm.get("created", ""))})
    out.sort(key=lambda r: r["created"])
    return out


def bundle(max_n: int | None = None) -> int:
    if not _gate():
        return 1
    import _sweepstate as ss
    rows = _unverified_with_source()
    if max_n is not None:
        rows = rows[:max_n]
    if not rows:
        print("kb-autoreview: nothing unverified with a source; no bundle written")
        return 0
    v = vault_root()
    tdir = v / "01-raw" / "transcripts"
    # Microseconds included: two bundle runs within the same second would
    # otherwise collide on the batch name (mkdir has exist_ok=False by design).
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    batch = v / ".claude" / "autoreview" / f"batch-{stamp}"
    batch.mkdir(parents=True, exist_ok=False)

    manifest = []
    for i, r in enumerate(rows, 1):
        d = batch / f"case-{i:03d}"
        d.mkdir()
        (d / "claim.md").write_text(
            f"# {r['stem']}\n\n- source: `{r['src']}`\n\n"
            f"## The claim, exactly as the memory states it\n\n{r['body']}\n",
            encoding="utf-8")
        try:
            text = ss.transcript_text(tdir / r["src"])
        except Exception as e:
            text = f"<transcript unreadable: {e}>"
        (d / "transcript.txt").write_text(text, encoding="utf-8")
        manifest.append({"case": d.name, "stem": r["stem"], "src": r["src"]})
    (batch / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"kb-autoreview: {len(manifest)} cases -> {batch}")
    return 0


def apply(results_path: str, retract_cap: int = RETRACT_CAP) -> int:
    if not _gate():
        return 1
    try:
        rows = json.loads(Path(results_path).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"kb-autoreview: cannot read results: {e}", file=sys.stderr)
        return 1
    if not isinstance(rows, list):
        # A dict at the top level is a common LLM mistake; refusing up front
        # beats crashing halfway through a run that already changed state.
        print("kb-autoreview: results must be a JSON LIST of verdict rows",
              file=sys.stderr)
        return 1

    by_stem = {r["stem"]: r for r in _unverified_with_source()}
    import collections
    tally = collections.Counter()
    retracted = 0
    applied = []
    for row in rows:
        if not isinstance(row, dict):
            tally["invalid_row"] += 1
            continue
        stem = str(row.get("stem", ""))
        verdict = str(row.get("verdict", "")).strip().lower()
        target = by_stem.get(stem)
        if target is None:
            tally["unknown_or_not_unverified"] += 1
            continue
        if verdict not in VALID_VERDICTS:
            tally["invalid_verdict"] += 1
            continue
        if verdict == "supported":
            if _memory.promote(target["path"],
                               reason=str(row.get("evidence", ""))[:300],
                               route="client",
                               prompt_version="autoreview-1"):
                tally["promoted"] += 1
                applied.append({"stem": stem, "action": "promoted"})
            else:
                tally["promote_refused"] += 1
        elif verdict == "absent" and row.get("refuted") is False:
            # Double agreement: the adjudicator found nothing AND the
            # independent refuter failed to overturn that. Anything less
            # leaves the memory untouched.
            if retracted >= retract_cap:
                tally["retract_capped"] += 1
                continue
            if _memory.set_status(
                    target["path"], "retracted",
                    reason=("autoreview: client adjudication 'absent' + "
                            "refutation failed to overturn (autoreview-1)")):
                retracted += 1
                tally["retracted"] += 1
                applied.append({"stem": stem, "action": "retracted"})
            else:
                tally["retract_refused"] += 1
        else:
            tally["left_unverified"] += 1
    out = Path(results_path).with_suffix(".applied.json")
    out.write_text(json.dumps(applied, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("kb-autoreview apply: " +
          ", ".join(f"{k} {v}" for k, v in tally.most_common()))
    print(f"applied log: {out}")
    return 0


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] in ("--help", "-h"):
        print(__doc__.strip())
        return 0
    cmd = argv[0]
    if cmd == "bundle":
        max_n = None
        if "--max" in argv:
            try:
                max_n = int(argv[argv.index("--max") + 1])
            except Exception:
                max_n = None
        return bundle(max_n)
    if cmd == "apply":
        if len(argv) < 2:
            print("kb-autoreview: apply needs a results.json path", file=sys.stderr)
            return 1
        cap = RETRACT_CAP
        if "--retract-cap" in argv:
            try:
                cap = int(argv[argv.index("--retract-cap") + 1])
            except Exception:
                cap = RETRACT_CAP
        return apply(argv[1], retract_cap=cap)
    print(f"kb-autoreview: unknown subcommand {cmd!r}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
