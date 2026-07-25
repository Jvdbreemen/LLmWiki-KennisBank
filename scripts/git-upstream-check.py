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

import re
import subprocess
import sys

# XY-statusveld van `git status --porcelain`, gevolgd door whitespace.
_STATUS_PREFIX = re.compile(r"^\s*[A-Z?!ADMRCU ]{1,2}\s+")

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


def _emit(lines: list[str]) -> None:
    if lines:
        print("Git-check — repo vraagt aandacht:")
        print("\n".join(lines))


def _uncommitted_backlog() -> list[str]:
    """Taakbestanden die Backlog.md schreef maar die niemand heeft gecommit.

    backlog/config.yml zet `auto_commit: false` en .gitignore sluit backlog/ niet
    uit, dus het gereedschap schrijft bestanden die vervolgens buiten git blijven
    -- inclusief taken met status Done wier resultaat in geen enkele commit
    bestaat. Een CI-test kan dit per definitie niet zien: die draait op wat al
    gecommit is. Vandaar hier.

    `:(top)backlog` maakt de pathspec repo-relatief, zodat de check ook werkt
    wanneer de sessie in een submap start.
    """
    out = _git("-c", "core.quotepath=false", "status", "--porcelain", "--", ":(top)backlog")
    if not out:
        return []
    paths = []
    for line in out.splitlines():
        if not line.strip():
            continue
        # Niet op een vaste offset knippen: _git() strip't de hele output, dus
        # de leidende spatie van een " D"-status is bij de eerste regel al weg.
        raw = _STATUS_PREFIX.sub("", line, count=1).strip()
        if " -> " in raw:            # hernoemd: "oud -> nieuw", neem het nieuwe
            raw = raw.split(" -> ", 1)[1].strip()
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]          # git quote paden met bijzondere tekens
        paths.append(raw)
    if not paths:
        return []
    shown = ", ".join(p.rsplit("/", 1)[-1] for p in paths[:3])
    more = f" (+{len(paths) - 3})" if len(paths) > 3 else ""
    return [f"- {len(paths)} niet-gecommit backlog-bestand(en): {shown}{more}"]


def main() -> None:
    # In a repo at all? (also silences non-repo cwds)
    if _git("rev-parse", "--is-inside-work-tree") != "true":
        return

    # Backlog-integriteit eerst: deze moet ook melden wanneer er geen upstream
    # is geconfigureerd, en staat daarom vóór de early returns hieronder.
    lines: list[str] = _uncommitted_backlog()

    # 1) Current branch vs its own upstream.
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    cur_upstream = _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    main_upstream = None
    if branch != "main":
        main_upstream = _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "main@{upstream}")

    # No configured upstream anywhere -> stay silent (and avoid a potentially slow fetch).
    upstream_ref = cur_upstream or main_upstream
    if not upstream_ref:
        _emit(lines)
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

    _emit(lines)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Absolute fail-open backstop: never let this hook break a session.
        pass
    sys.exit(0)
