"""safe-edit.py — deterministic hybrid-autonomy edit engine with git safety net.

Pure core functions (classify, unified) are import-safe and testable without
touching git or the filesystem. CLI behaviour is guarded behind
``if __name__ == "__main__":``.
"""
from __future__ import annotations

import difflib
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Pure core — no filesystem, no git
# ---------------------------------------------------------------------------

def classify(
    old: str,
    new: str,
    max_lines: int = 20,
    max_drop: int = 3,
) -> str:
    """Classify a proposed edit as ``"klein"`` (small) or ``"groot"`` (large).

    An edit is **klein** when ALL of the following hold:
    - diff_line_count (added + removed lines in the unified diff) <= max_lines.
      A *modified* line counts twice (once as ``-``, once as ``+``), so the
      default threshold of 20 is roughly ~10 modified lines.
    - No markdown heading (``^#{1,6} ``) is removed.
    - Net removed non-blank body lines <= max_drop.
    - The target is not being emptied (new is not empty / blank-only).

    Any condition violated makes the edit ``"groot"``.
    """
    # Emptying the file is always groot.
    if not new.strip():
        return "groot"

    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)

    # Unified diff — count +/- content lines (skip +++/--- headers and @@ hunks).
    added = 0
    removed = 0
    heading_re = re.compile(r"^#{1,6} ")

    for line in difflib.unified_diff(old_lines, new_lines, lineterm=""):
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("@@"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1

    diff_line_count = added + removed
    if diff_line_count > max_lines:
        return "groot"

    # Heading removal: a heading in old absent in new.
    old_headings = {l.rstrip("\n\r") for l in old_lines if heading_re.match(l)}
    new_headings = {l.rstrip("\n\r") for l in new_lines if heading_re.match(l)}
    if old_headings - new_headings:
        return "groot"

    # Net removed non-blank body lines.
    def _nonblank(lines):
        return sum(1 for l in lines if l.strip())

    net_drop = max(0, _nonblank(old_lines) - _nonblank(new_lines))
    if net_drop > max_drop:
        return "groot"

    return "klein"


def unified(old: str, new: str, path: str) -> str:
    """Return a unified diff string between old and new.

    Uses ``difflib.unified_diff`` with ``fromfile=a/<path>`` and
    ``tofile=b/<path>``. Returns an empty string when there are no changes.
    """
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _git(*args, cwd=None):
    """Run a git sub-command and return CompletedProcess."""
    import subprocess
    return subprocess.run(
        ["git"] + list(args),
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )


def _short_sha(repo_root: Path) -> str:
    r = _git("rev-parse", "--short", "HEAD", cwd=repo_root)
    return r.stdout.strip() if r.returncode == 0 else "unknown"


def _emit(report: dict):
    """Print report as JSON for machine readability. JSON output is always on."""
    print(json.dumps(report, ensure_ascii=False))


def _parse_porcelain_path(line: str) -> str:
    """Extract the (new) file path from a git status --porcelain line.

    Porcelain format: ``XY <path>`` or ``XY "<quoted-path>"``.
    For renames (``R``): ``XY <old> -> <new>`` — we take the new path.
    Git quotes paths with special characters in double-quotes; we strip those.
    """
    # Strip the 2-char XY status prefix and the separating space.
    raw = line[3:]
    # Handle rename: "old -> new" — take the part after " -> ".
    if " -> " in raw:
        raw = raw.split(" -> ", 1)[1]
    # Strip git's quoted-path escaping (paths with special chars are wrapped in "…").
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1]
    return raw


def main(argv=None):
    import argparse
    import subprocess

    parser = argparse.ArgumentParser(description="Safe-edit engine for the wiki vault.")
    parser.add_argument("target", help="Path to the article file to edit.")
    parser.add_argument(
        "--new",
        required=True,
        metavar="FILE|-",
        help="Path to the file containing proposed new content, or - for stdin.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Apply even if classified as groot.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip dirty-tree and non-git-repo guards.",
    )
    parser.add_argument(
        "--message",
        metavar="MSG",
        default=None,
        help="Commit message. Defaults to 'wiki-rewrite: <basename>'.",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        default=True,
        help="Emit machine-readable JSON report (default on, always active).",
    )

    args = parser.parse_args(argv)

    # Both sides are .resolve()d so they are fully canonical; this handles macOS
    # /tmp -> /private/tmp remapping and is required by Path.is_relative_to
    # (Python 3.9+).
    target = Path(args.target).resolve()
    target_exists = target.exists()

    # Read proposed content.
    if args.new == "-":
        proposed = sys.stdin.read()
    else:
        proposed = Path(args.new).read_text(encoding="utf-8")

    # ---- Git guard ----
    target_dir = target.parent

    repo_result = _git(
        "-C", str(target_dir), "rev-parse", "--show-toplevel"
    )
    if repo_result.returncode != 0:
        if args.force:
            repo_root = None
        else:
            print(
                json.dumps(
                    {"action": "refused", "reason": "not-a-git-repo"},
                    ensure_ascii=False,
                )
            )
            sys.exit(3)
    else:
        repo_root = Path(repo_result.stdout.strip()).resolve()

    if repo_root is not None and not args.force:
        # Check for dirty tree: changes to files OTHER than the target.
        # Use exact path comparison, not substring match, to avoid false negatives
        # when a dirty file's path contains the target path as a substring
        # (e.g. target=02-wiki/a.md, dirty=02-wiki/a.md.bak).
        status_result = _git("-C", str(repo_root), "status", "--porcelain")
        dirty_lines = [
            l for l in status_result.stdout.splitlines()
            if l.strip()
        ]
        # target_rel uses .resolve()d repo_root so is_relative_to works on macOS.
        target_rel = target.relative_to(repo_root) if target.is_relative_to(repo_root) else target
        target_rel_str = str(target_rel)

        non_target_dirty = []
        for l in dirty_lines:
            parsed_path = _parse_porcelain_path(l)
            # Exact equality: a.md.bak != a.md even though a.md is a substring.
            if parsed_path != target_rel_str and parsed_path != str(target):
                non_target_dirty.append(l)

        if non_target_dirty:
            print(
                json.dumps(
                    {
                        "action": "refused",
                        "reason": "dirty-tree",
                        "dirty": non_target_dirty,
                    },
                    ensure_ascii=False,
                )
            )
            sys.exit(3)

    # ---- No-op detection ----
    # If proposed content is byte-identical to current file, nothing to do.
    if target_exists:
        current_bytes = target.read_bytes()
        if current_bytes == proposed.encode("utf-8"):
            _emit({"action": "no-op"})
            sys.exit(0)

    # ---- Classify ----
    if not target_exists:
        # New-file case: klein if content fits within max_lines lines.
        new_line_count = len(proposed.splitlines())
        size = "klein" if new_line_count <= 20 else "groot"
        old_text = ""
    else:
        old_text = target.read_text(encoding="utf-8")
        size = classify(old_text, proposed)

    commit_msg = args.message or f"wiki-rewrite: {target.name}"

    # ---- Apply or gate ----
    if size == "groot" and not args.confirm:
        # Emit diff + needs-confirm report, exit 2.
        if old_text:
            diff_str = unified(old_text, proposed, str(target.name))
            if diff_str:
                print(diff_str)
        report = {"action": "needs-confirm", "size": "groot"}
        _emit(report)
        sys.exit(2)

    # Apply: write file, git add, git commit.
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(proposed, encoding="utf-8")

    if repo_root is not None:
        add_result = _git("-C", str(repo_root), "add", str(target))
        if add_result.returncode != 0:
            _emit({
                "action": "error",
                "reason": "git-add-failed",
                "detail": add_result.stderr.strip(),
            })
            sys.exit(4)

        commit_result = _git("-C", str(repo_root), "commit", "-m", commit_msg)
        if commit_result.returncode != 0:
            _emit({
                "action": "error",
                "reason": "git-commit-failed",
                "detail": commit_result.stderr.strip(),
            })
            sys.exit(4)

        sha = _short_sha(repo_root)
    else:
        sha = "no-git"

    report = {"action": "applied", "size": size, "commit": sha}
    _emit(report)
    sys.exit(0)


if __name__ == "__main__":
    main()
