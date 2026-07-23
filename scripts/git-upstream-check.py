#!/usr/bin/env python3
"""SessionStart hook: warn when the working branch (and main) drift behind upstream.

Root cause it guards against: main only advanced via manual `git pull --ff-only`.
When that stops for a while, main silently falls behind. This hook makes the drift
visible at session start instead of relying on manual discipline (CLAUDE.md
noord-ster #3: automate over handwork).

Contract:
- Off the hot path: runs once at SessionStart, not per prompt.
- Fail-open: any error (not a repo, no upstream, network down, git missing) exits
  0 and stays silent. It must never block a session.
- Quiet when clean: emits nothing if everything is up to date.
- cwd-aware: only acts inside a git repo that has a configured upstream.

Emitted stdout becomes SessionStart context. Keep it compact.
"""
from __future__ import annotations

import subprocess
import sys

# git fetch can hang on a dead network; keep the whole check well under the
# session-start budget. Threshold: warn once the gap reaches this many commits.
FETCH_TIMEOUT = 8.0
BEHIND_THRESHOLD = 1


def _git(*args: str, timeout: float = 5.0) -> str | None:
    """Run a git command; return stdout stripped, or None on any failure."""
    try:
        out = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def _behind(local: str, upstream: str) -> int | None:
    """Commits `upstream` has that `local` lacks; None if unknown."""
    n = _git("rev-list", "--count", f"{local}..{upstream}")
    if n is None or not n.isdigit():
        return None
    return int(n)


def main() -> None:
    # In a repo at all? (also silences non-repo cwds)
    if _git("rev-parse", "--is-inside-work-tree") != "true":
        return

    lines: list[str] = []

    # 1) Current branch vs its own upstream.
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    cur_upstream = _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    main_upstream = None
    if branch != "main":
        main_upstream = _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "main@{upstream}")

    # No configured upstream anywhere -> stay silent (and avoid a potentially slow fetch).
    upstream_ref = cur_upstream or main_upstream
    if not upstream_ref:
        return

    # Fetch the relevant remote once so counts are fresh.
    remote = upstream_ref.split("/", 1)[0] if "/" in upstream_ref else "origin"
    _git("fetch", "--quiet", "--no-tags", remote, timeout=FETCH_TIMEOUT)

    if branch and branch != "HEAD" and cur_upstream:
        b = _behind("HEAD", cur_upstream)
        if b is not None and b >= BEHIND_THRESHOLD:
            lines.append(f"- huidige branch `{branch}` staat {b} commit(s) achter `{cur_upstream}`")

    # 2) main vs its upstream (the drift that bit us). Skip if main IS the branch
    #    (already covered above) or main has no upstream.
    if main_upstream:
        b = _behind("main", main_upstream)
        if b is not None and b >= BEHIND_THRESHOLD:
            lines.append(
                f"- `main` staat {b} commit(s) achter `{main_upstream}` "
                f"(sync: `git switch main && git pull --ff-only`)"
            )

    if lines:
        print("Git-upstream check — repo loopt achter:")
        print("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Absolute fail-open backstop: never let this hook break a session.
        pass
    sys.exit(0)
