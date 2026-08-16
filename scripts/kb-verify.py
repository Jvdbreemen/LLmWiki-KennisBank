#!/usr/bin/env python3
"""kb-verify.py - drain the unverified backlog through grounded promotion.

The sweep runs trap 1 capped (KB_VERIFY_CAP, default 40) so its tail stays
bounded; this CLI is how the historical backlog gets drained deliberately, in
one supervised run, with progress and a summary.

Only promotes on `supported` against the memory's own source. Never demotes,
never touches anything but status=unverified — see _groundcheck for the
measurements behind that asymmetry. Every promotion lands in the promote log
(.claude/memory-promote-log.jsonl) with its evidence quote, which is the
audit surface: a promotion you distrust is undone by setting the file's
status back to unverified, or dampened with `kb-noise.py <stem>`.

Usage: python3 kb-verify.py [--max N] [--dry-run]
  --max N     verify at most N memories this run (default: everything pending)
  --dry-run   judge and report, write nothing

Exit 0 always on a clean run; a missing model prints and exits 1 so a caller
can tell "nothing to do" from "could not run" (the TASK-148 rule).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _groundcheck  # noqa: E402
import _llm  # noqa: E402
import _memory  # noqa: E402
import _settings  # noqa: E402
import _sweepstate as ss  # noqa: E402
import _sweeputil as su  # noqa: E402
import _embeddings as emb  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402
from _progress import Progress  # noqa: E402
from _vaultpath import vault_root  # noqa: E402


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        print(__doc__.strip())
        return 0
    dry = "--dry-run" in argv
    max_n = None
    if "--max" in argv:
        try:
            max_n = int(argv[argv.index("--max") + 1])
        except Exception:
            max_n = None

    if not _settings.get("memory_capture", True):
        print("kb-verify: memory_capture staat uit; niets te doen")
        return 0
    if not (_llm.generate("ping") and emb.embed("ping")):
        print("kb-verify: model of embedding-backend onbereikbaar", file=sys.stderr)
        return 1

    v = vault_root()
    tdir = v / "01-raw" / "transcripts"
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
    if max_n is not None:
        todo = todo[:max_n]

    import collections
    tally = collections.Counter()
    chunk_cache: dict = {}
    with Progress(len(todo), "grounded verify") as p:
        for _created, f, body, src, stamp in todo:
            p.step(note=f.stem[:40])
            try:
                if src not in chunk_cache:
                    chunk_cache[src] = su.chunk(ss.transcript_text(tdir / src))
                r = _groundcheck.verify_grounded(body, chunk_cache[src], stamp)
            except Exception:
                tally["error"] += 1
                continue
            tally[r["verdict"]] += 1
            if r["verdict"] == "supported" and not dry:
                if _memory.promote(f, reason=r["reason"], route=r["route"],
                                   prompt_version=_groundcheck.VERIFY_PROMPT_VERSION):
                    tally["promoted"] += 1

    mode = " (dry-run, niets geschreven)" if dry else ""
    print(f"kb-verify{mode}: {len(todo)} beoordeeld -> " +
          ", ".join(f"{k} {v}" for k, v in tally.most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
