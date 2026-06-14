#!/usr/bin/env python3
"""
import-cc-history.py — Importeer Claude Code session-history naar de KennisBank.

Bron: $HOME/.claude/projects/<cwd-slug>/<session-uuid>.jsonl
Eén jsonl-bestand bevat één sessie. Records hebben velden zoals:
  type:        permission-mode | attachment | file-history-snapshot |
               user | assistant | system | last-prompt | queue-operation
  message:     {role, content, model?, ...}        (alleen op user/assistant)
  timestamp:   ISO-8601 string (UTC, met Z)
  cwd:         absolute pad waar CC draaide
  sessionId:   UUID (matcht meestal de bestandsnaam)
  version:     CC-versie
  gitBranch:   actieve git-branch tijdens de turn

Per sessie schrijven we één raw-sessie-log naar
  $HOME/KennisBank/01-raw/sessies/raw-sessie-YYYY-MM-DD-<slug>.md

Gebruik:
  python3 import-cc-history.py [--dry-run] [--verbose] [--json]
                               [--force] [--vault PATH]
                               [--projects-dir PATH]
                               [--limit N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import _today_iso, _utcnow_iso, print_summary, slugify  # noqa: E402

CC_PROJECTS_DIR_DEFAULT = Path.home() / ".claude" / "projects"
VAULT_DEFAULT = Path.home() / "KennisBank"


def extract_text(content) -> str:
    """Reduceer message.content (string of list-of-blocks) tot platte tekst."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                parts.append(block.get("text", ""))
            elif btype == "tool_result":
                tr = block.get("content", "")
                if isinstance(tr, str):
                    parts.append(tr)
                elif isinstance(tr, list):
                    for sub in tr:
                        if isinstance(sub, dict) and sub.get("type") == "text":
                            parts.append(sub.get("text", ""))
            # ignore thinking, tool_use, image
        return "\n".join(p for p in parts if p)
    return ""


def parse_session(jsonl_path: Path) -> dict | None:
    """Parse één sessie-jsonl. Return None als er geen user-turn in zit."""
    first_user_text: str | None = None
    first_user_ts: str | None = None
    first_ts: str | None = None
    user_turns = 0
    assistant_turns = 0
    tool_use_count = 0
    tool_use_files: list[str] = []
    models: list[str] = []
    cwd: str | None = None
    session_id: str | None = None
    version: str | None = None
    git_branch: str | None = None

    try:
        with jsonl_path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts = rec.get("timestamp")
                if ts and not first_ts:
                    first_ts = ts
                if cwd is None and rec.get("cwd"):
                    cwd = rec.get("cwd")
                if session_id is None and rec.get("sessionId"):
                    session_id = rec.get("sessionId")
                if version is None and rec.get("version"):
                    version = rec.get("version")
                if git_branch is None and rec.get("gitBranch"):
                    git_branch = rec.get("gitBranch")

                rtype = rec.get("type")
                msg = rec.get("message")
                if not isinstance(msg, dict):
                    continue

                role = msg.get("role")
                if rtype == "user" and role == "user":
                    user_turns += 1
                    if first_user_text is None:
                        text = extract_text(msg.get("content")).strip()
                        # Filter automatische tool_result-only turns
                        if text:
                            first_user_text = text
                            first_user_ts = ts
                elif rtype == "assistant" and role == "assistant":
                    assistant_turns += 1
                    model = msg.get("model")
                    if model and model not in models:
                        models.append(model)
                    content = msg.get("content")
                    if isinstance(content, list):
                        for block in content:
                            if not isinstance(block, dict):
                                continue
                            if block.get("type") == "tool_use":
                                tool_use_count += 1
                                inp = block.get("input")
                                if isinstance(inp, dict):
                                    for key in ("file_path", "path", "filePath"):
                                        v = inp.get(key)
                                        if isinstance(v, str) and v not in tool_use_files:
                                            tool_use_files.append(v)
    except OSError:
        return None

    if first_user_text is None or user_turns == 0:
        return None

    date_str = (first_user_ts or first_ts or "")[:10]
    if not re.match(r"\d{4}-\d{2}-\d{2}", date_str):
        try:
            date_str = datetime.fromtimestamp(jsonl_path.stat().st_mtime).date().isoformat()
        except OSError:
            date_str = _today_iso()

    project_slug = jsonl_path.parent.name
    cwd_display = cwd or project_slug

    return {
        "first_user_text": first_user_text,
        "date": date_str,
        "session_id": session_id or jsonl_path.stem,
        "user_turns": user_turns,
        "assistant_turns": assistant_turns,
        "tool_use_count": tool_use_count,
        "tool_use_files": tool_use_files[:20],
        "models": models,
        "cwd": cwd_display,
        "project_slug": project_slug,
        "version": version,
        "git_branch": git_branch,
        "source_path": str(jsonl_path),
    }


def render_body(meta: dict, imported_at: str) -> str:
    source_id = meta.get("session_id") or Path(meta["source_path"]).stem
    fm_lines = [
        "---",
        f"title: \"Sessie-log {meta['date']}\"",
        "type: raw-sessie",
        "source: cc-history",
        f"source_id: {source_id}",
        f"source_path: {meta['source_path']}",
        f"date: {meta['date']}",
        f"imported_at: {imported_at}",
        f"turns_user: {meta['user_turns']}",
        f"turns_assistant: {meta['assistant_turns']}",
        "tags: [claude-sessie, import-cc]",
        "status: raw",
    ]
    if meta.get("cwd"):
        fm_lines.append(f"cwd: {meta['cwd']}")
    if meta.get("git_branch"):
        fm_lines.append(f"git_branch: {meta['git_branch']}")
    if meta.get("version"):
        fm_lines.append(f"cc_version: {meta['version']}")
    fm_lines.append("---")

    doel = meta["first_user_text"].strip()
    if len(doel) > 500:
        doel = doel[:500].rstrip() + "..."

    samenvatting = (
        f"Imported from Claude Code session history. "
        f"{meta['user_turns']} user turns, {meta['assistant_turns']} assistant turns. "
        f"CWD: {meta['cwd']}. "
        f"Tool uses: {meta['tool_use_count']}."
    )

    models_line = ", ".join(meta["models"]) if meta["models"] else "onbekend"
    body = "\n".join(fm_lines) + "\n\n" + "\n".join([
        f"# Sessie-log {meta['date']}",
        "",
        "## Doel",
        doel,
        "",
        "## Samenvatting",
        samenvatting,
        "",
        "## Output",
        "",
        "## Nieuwe kennis",
        "_To be compiled by /wiki._",
        "",
        "## Vervolgacties",
        "",
        "## AI-verantwoording",
        f"- Model(len): {models_line}",
        f"- Tool-use count: {meta['tool_use_count']}",
        f"- CC-versie: {meta.get('version') or 'onbekend'}",
        "",
    ])
    return body


def target_path(out_dir: Path, meta: dict) -> Path:
    slug = slugify(meta["first_user_text"])
    # Append stable 8-char suffix so same-date same-title sessions don't collide.
    session_id = (meta.get("session_id") or "").strip()
    if session_id:
        suffix = re.sub(r"[^a-z0-9]", "", session_id.lower())[:8]
    else:
        suffix = ""
    if not suffix:
        seed = f"{meta.get('date','')}{meta.get('first_user_text','')[:200]}"
        suffix = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    return out_dir / f"raw-sessie-{meta['date']}-{slug}-{suffix}.md"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Importeer Claude Code sessie-history naar 01-raw/sessies/."
    )
    parser.add_argument("--vault", type=Path, default=VAULT_DEFAULT,
                        help=f"Vault root (default: {VAULT_DEFAULT})")
    parser.add_argument("--projects-dir", type=Path, default=CC_PROJECTS_DIR_DEFAULT,
                        help=f"CC projects directory (default: {CC_PROJECTS_DIR_DEFAULT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Toon wat geschreven zou worden, schrijf niets.")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON-summary aan het eind.")
    parser.add_argument("--force", action="store_true",
                        help="Overschrijf bestaande target-bestanden.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Beperk aantal te verwerken jsonl-bestanden (0 = alle).")
    args = parser.parse_args()

    projects_dir: Path = args.projects_dir
    out_dir: Path = args.vault / "01-raw" / "sessies"

    if not projects_dir.exists():
        print(f"[error] CC projects-dir niet gevonden: {projects_dir}", file=sys.stderr)
        return 2

    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    jsonl_files = sorted(projects_dir.glob("*/*.jsonl"))
    if args.limit:
        jsonl_files = jsonl_files[: args.limit]

    imported = 0
    skipped = 0
    errors = 0
    files_out: list[str] = []
    errors_detail: list[dict] = []
    imported_at = _utcnow_iso()

    for jp in jsonl_files:
        try:
            meta = parse_session(jp)
        except Exception as e:
            errors += 1
            errors_detail.append({"path": str(jp), "stage": "parse", "error": str(e)})
            if args.verbose:
                print(f"[err] parse {jp}: {e}", file=sys.stderr)
            continue

        if meta is None:
            if args.verbose:
                print(f"[skip] {jp.name}: no user turns")
            continue

        target = target_path(out_dir, meta)
        if target.exists() and not args.force:
            skipped += 1
            if args.verbose or not args.json:
                print(f"[skip] exists: {target}")
            continue

        body = render_body(meta, imported_at)

        if args.dry_run:
            imported += 1
            files_out.append(str(target))
            if args.verbose:
                print(f"[+] dry-run would write: {target} ({len(body)} bytes)")
            else:
                print(f"[+] dry-run {target}")
        else:
            try:
                target.write_text(body, encoding="utf-8")
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
    print_summary(summary, args.json)

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
