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

Usage: python3 kb-verify.py [--max N] [--dry-run] [--retry-settled]
  --max N          verify at most N memories this run (default: everything pending)
  --dry-run        judge and report, write nothing (no verdict recorded either)
  --retry-settled  also re-judge memories whose verdict is still within the
                   cooldown. The sweep skips those so its cap goes to memories
                   nothing has read yet; this CLI is the deliberate drain, so
                   it will do the whole backlog when asked.

Exit 0 always on a clean run; a missing model prints and exits 1 so a caller
can tell "nothing to do" from "could not run" (the TASK-148 rule).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _groundcheck  # noqa: E402
import _llm  # noqa: E402
import _memory  # noqa: E402
import _settings  # noqa: E402
import _sweepstate as ss  # noqa: E402
import _sweeputil as su  # noqa: E402
import _embeddings as emb  # noqa: E402
from _progress import Progress  # noqa: E402
from _vaultpath import vault_root  # noqa: E402


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        print(__doc__.strip())
        return 0
    dry = "--dry-run" in argv
    retry_settled = "--retry-settled" in argv
    max_n = None
    if "--max" in argv:
        try:
            max_n = int(argv[argv.index("--max") + 1])
        except Exception:
            max_n = None

    if not _settings.get("memory_capture", True):
        print("kb-verify: memory_capture is off; nothing to do")
        return 0
    if not (_llm.generate("ping") and emb.embed("ping")):
        print("kb-verify: model or embedding backend unreachable", file=sys.stderr)
        return 1

    tdir = vault_root() / "01-raw" / "transcripts"
    # Same selection as the sweep, from one definition. It lived here as a
    # copied block until TASK-198, which is how the CLI and the sweep could
    # have drifted into judging different sets without anything saying so.
    todo = _groundcheck.candidates(max_n, retry_settled=retry_settled)

    import collections
    tally = collections.Counter()
    chunk_cache: dict = {}
    # Collected during the run and flushed once. A read-modify-write per
    # verdict would rewrite a growing file thousands of times on a full drain.
    learned: dict = {}
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
            if dry:
                continue
            # A dry run may not record either: the cooldown it wrote would rob
            # the real run that follows of its own candidates.
            if r["verdict"] != "supported":
                learned[_groundcheck.attempt_key(f)] = _groundcheck.outcome(
                    r["verdict"])
            elif _memory.promote(f, reason=r["reason"], route=r["route"],
                                 prompt_version=_groundcheck.VERIFY_PROMPT_VERSION):
                tally["promoted"] += 1

    _groundcheck.record_attempts(learned)

    mode = " (dry-run, nothing written)" if dry else ""
    print(f"kb-verify{mode}: {len(todo)} judged -> " +
          ", ".join(f"{k} {v}" for k, v in tally.most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
