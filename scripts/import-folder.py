#!/usr/bin/env python3
"""
import-folder.py — Generieke recursieve import van .md/.txt bestanden naar 01-raw/sessies/.

Geen bron-specifieke parsing. Alleen frontmatter behouden, bron-pad bewaren,
inhoud ongewijzigd doorzetten.

Mac desktop Claude / Cowork data-paden om te onderzoeken (run met
--list-cowork-candidates voor live overzicht):

  $HOME/Library/Application Support/Claude/
      bevat o.a.: Claude Extensions/, claude-code-sessions/,
      cowork-file-preview/, claude-code/, claude_desktop_config.json,
      vm_bundles/, local-agent-mode-sessions/

  $HOME/Library/Application Support/Claude-3p/
      (3rd-party / dev variant, indien aanwezig)

  $HOME/Library/Containers/com.anthropic.claude/
  $HOME/Library/Containers/com.anthropic.claudefordesktop/
      (alleen aanwezig bij sandboxed Mac App Store builds; op deze
      machine niet aanwezig)

  $HOME/Library/Group Containers/*.anthropic.*
      (alleen bij sandboxed builds; op deze machine niet aanwezig)

Op deze machine (gemeten op 2026-05-08) staan de echte chat- en cowork-
gerelateerde paden onder $HOME/Library/Application Support/Claude/.
De Claude Code session-history staat NIET hier maar in
$HOME/.claude/projects/<cwd-slug>/<uuid>.jsonl — gebruik
import-cc-history.py voor die bron.

Gebruik:
  python3 import-folder.py --source /path/to/folder [--prefix chat]
  python3 import-folder.py --list-cowork-candidates
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()

VAULT_DEFAULT = Path.home() / "KennisBank"

ALLOWED_EXTS = {".md", ".markdown", ".txt"}

# Mac desktop Claude / Cowork candidate paths.
# Documents/Claude/Projects is the most useful real source: it holds project
# content (markdown notes, artifacts) created in the Mac desktop Cowork feature.
# The Library paths hold session metadata and are mostly opaque jsonl/binary;
# they are listed for completeness but rarely useful for /import folder.
COWORK_CANDIDATES = [
    Path.home() / "Documents" / "Claude" / "Projects",
    Path.home() / "Documents" / "Claude" / "Artifacts",
    Path.home() / "Library" / "Application Support" / "Claude",
    Path.home() / "Library" / "Application Support" / "Claude-3p",
    Path.home() / "Library" / "Application Support" / "Claude" / "cowork-file-preview",
    Path.home() / "Library" / "Application Support" / "Claude" / "claude-code-sessions",
    Path.home() / "Library" / "Application Support" / "Claude" / "claude-code",
    Path.home() / "Library" / "Application Support" / "Claude" / "local-agent-mode-sessions",
    Path.home() / "Library" / "Application Support" / "Claude" / "vm_bundles",
    Path.home() / "Library" / "Containers" / "com.anthropic.claude",
    Path.home() / "Library" / "Containers" / "com.anthropic.claudefordesktop",
]


def slugify(text: str, max_len: int = 50) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    if not text:
        return "untitled"
    return text[:max_len].rstrip("-") or "untitled"


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Splits YAML frontmatter af. Geeft (fm_dict, body)."""
    fm: dict = {}
    body = text
    if not text.startswith("---"):
        return fm, body
    end = text.find("\n---", 3)
    if end == -1:
        return fm, body
    block = text[3:end].lstrip("\n")
    after = text[end + 4 :]
    if after.startswith("\n"):
        after = after[1:]
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        # strip surrounding quotes
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        fm[key] = value
    return fm, after


def yaml_escape(value: str) -> str:
    """Eenvoudige YAML-string-escape voor één-regel waarden."""
    if value == "":
        return '""'
    if any(c in value for c in [':', '#', '"', "'", '\n', '\\', '[', ']', '{', '}', ',', '&', '*', '!', '|', '>', '%', '@', '`']):
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return value


def render_frontmatter(fm: dict) -> str:
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            inner = ", ".join(yaml_escape(str(x)) for x in v)
            lines.append(f"{k}: [{inner}]")
        else:
            lines.append(f"{k}: {yaml_escape(str(v))}")
    lines.append("---")
    return "\n".join(lines)


def file_date(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
    except OSError:
        return _today_iso()


def list_cowork_candidates() -> int:
    print("Mac desktop Claude / Cowork candidate paths:\n")
    for p in COWORK_CANDIDATES:
        marker = "[exists]" if p.exists() else "[absent]"
        kind = ""
        if p.exists():
            try:
                kind = "dir" if p.is_dir() else "file"
            except OSError:
                kind = "?"
        print(f"  {marker} {p} {kind}")
    print()
    print("Tip: punt --source naar een van de [exists] dirs om te importeren.")
    print("Voor Claude Code sessie-jsonl files: gebruik import-cc-history.py.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Importeer markdown/text uit een willekeurige map naar 01-raw/sessies/."
    )
    parser.add_argument("--source", type=Path,
                        help="Bronmap (recursief gescand op .md/.txt/.markdown).")
    parser.add_argument("--prefix", type=str, default="",
                        help="Prefix voor topic-slug (bijv. 'chat', 'cowork').")
    parser.add_argument("--vault", type=Path, default=VAULT_DEFAULT,
                        help=f"Vault root (default: {VAULT_DEFAULT})")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--list-cowork-candidates", action="store_true",
                        help="Toon Mac desktop Claude/Cowork data-paden en stop.")
    args = parser.parse_args()

    if args.list_cowork_candidates:
        return list_cowork_candidates()

    if args.source is None:
        parser.error("--source is verplicht (tenzij --list-cowork-candidates)")

    src: Path = args.source
    if not src.exists():
        print(f"[error] source bestaat niet: {src}", file=sys.stderr)
        return 2
    if not src.is_dir():
        print(f"[error] source is geen directory: {src}", file=sys.stderr)
        return 2

    out_dir: Path = args.vault / "01-raw" / "sessies"
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in src.rglob("*") if p.is_file() and p.suffix.lower() in ALLOWED_EXTS)

    imported = 0
    skipped = 0
    errors = 0
    files_out: list[str] = []
    errors_detail: list[dict] = []
    imported_at = _utcnow_iso()
    prefix = slugify(args.prefix) if args.prefix else ""

    for fp in files:
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            errors += 1
            errors_detail.append({"path": str(fp), "stage": "read", "error": str(e)})
            if args.verbose:
                print(f"[err] read {fp}: {e}", file=sys.stderr)
            continue

        existing_fm, body = split_frontmatter(text)
        date_str = existing_fm.get("date") or existing_fm.get("created") or file_date(fp)
        date_str = str(date_str)[:10]
        if not re.match(r"\d{4}-\d{2}-\d{2}", date_str):
            date_str = file_date(fp)

        base_slug = slugify(fp.stem) or "untitled"
        slug = f"{prefix}-{base_slug}" if prefix else base_slug
        slug = slug[:50].rstrip("-") or "untitled"

        target = out_dir / f"raw-sessie-{date_str}-{slug}.md"

        if target.exists() and not args.force:
            skipped += 1
            if args.verbose or not args.json:
                print(f"[skip] exists: {target}")
            continue

        # Bouw nieuwe frontmatter: kern fields + bewaarde originele velden onder original_*
        new_fm: dict = {
            "title": existing_fm.get("title") or f"Sessie-log {date_str}",
            "type": "raw-sessie",
            "source": "folder",
            "source_id": str(fp.resolve()),
            "source_path": str(fp.resolve()),
            "date": date_str,
            "imported_at": imported_at,
            "turns_user": 0,
            "turns_assistant": 0,
            "tags": existing_fm.get("tags") or "[claude-sessie, import-folder]",
            "status": "raw",
        }
        if prefix:
            new_fm["import_prefix"] = prefix
        # bewaar overige originele frontmatter velden
        reserved = {
            "title", "type", "source", "source_id", "source_path",
            "date", "imported_at", "turns_user", "turns_assistant",
            "tags", "status",
        }
        for k, v in existing_fm.items():
            if k in reserved:
                continue
            new_fm[f"orig_{k}"] = v

        # tags-lijst: render-frontmatter ondersteunt list-of-strings of plain-string
        if isinstance(new_fm["tags"], str) and new_fm["tags"].startswith("["):
            # laat zoals het is; render_frontmatter doet yaml_escape per item alleen bij list-objects
            pass

        new_body = (
            render_frontmatter(new_fm)
            + "\n\n"
            + f"# Sessie-log {date_str}\n\n"
            + "## Original location\n"
            + str(fp.resolve())
            + "\n\n"
            + "## Content\n"
            + body.lstrip("\n")
        )
        if not new_body.endswith("\n"):
            new_body += "\n"

        if args.dry_run:
            imported += 1
            files_out.append(str(target))
            if args.verbose:
                print(f"[+] dry-run would write: {target} ({len(new_body)} bytes)")
            else:
                print(f"[+] dry-run {target}")
        else:
            try:
                target.write_text(new_body, encoding="utf-8")
                imported += 1
                files_out.append(str(target))
                if not args.json:
                    print(f"[+] imported {target}")
            except OSError as e:
                errors += 1
                errors_detail.append({"path": str(target), "stage": "write", "error": str(e)})
                if args.verbose:
                    print(f"[err] write {target}: {e}", file=sys.stderr)

    summary = {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "files": files_out,
        "errors_detail": errors_detail,
    }
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"--- summary: imported={imported} skipped={skipped} errors={errors}")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
