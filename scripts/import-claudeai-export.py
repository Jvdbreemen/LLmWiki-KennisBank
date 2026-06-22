#!/usr/bin/env python3
"""
import-claudeai-export.py — Importeer een claude.ai data-export naar 01-raw/sessies/.

Een claude.ai export is een ZIP met conversations.json (en optioneel users.json,
projects.json). conversations.json is een array. Per conversation:
  - uuid           string
  - name           string (kan leeg zijn)
  - created_at     ISO timestamp
  - updated_at     ISO timestamp
  - chat_messages  list of {sender: "human" | "assistant", text, created_at,
                            attachments: [{file_name, ...}], ...}

Per conversatie schrijven we één raw-sessie-log met volledige transcript.

Gebruik:
  python3 import-claudeai-export.py --input /path/to/conversations.json
  python3 import-claudeai-export.py --input /path/to/export.zip
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402
from _common import _today_iso, _utcnow_iso, print_summary, slugify  # noqa: E402

VAULT_DEFAULT = vault_root()


def extract_message_text(msg: dict) -> str:
    """claude.ai messages: text field of content-blocks."""
    text = msg.get("text")
    if isinstance(text, str) and text.strip():
        return text
    content = msg.get("content")
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif "text" in block:
                    parts.append(block.get("text", ""))
        return "\n".join(p for p in parts if p)
    return ""


def parse_conversation(conv: dict) -> dict | None:
    msgs = conv.get("chat_messages") or conv.get("messages") or []
    if not isinstance(msgs, list):
        return None

    first_human_text: str | None = None
    human_turns = 0
    assistant_turns = 0
    attachments: list[str] = []
    transcript_lines: list[str] = []

    for m in msgs:
        if not isinstance(m, dict):
            continue
        sender = (m.get("sender") or m.get("role") or "").lower()
        if sender in ("human", "user"):
            human_turns += 1
            txt = extract_message_text(m).strip()
            if txt and first_human_text is None:
                first_human_text = txt
            transcript_lines.append("**Human:** " + (txt or "(leeg)"))
        elif sender == "assistant":
            assistant_turns += 1
            txt = extract_message_text(m).strip()
            transcript_lines.append("**Assistant:** " + (txt or "(leeg)"))
        else:
            continue

        for att in (m.get("attachments") or []):
            if isinstance(att, dict):
                fn = att.get("file_name") or att.get("filename") or att.get("name")
                if fn and fn not in attachments:
                    attachments.append(fn)

        transcript_lines.append("")  # blank line between turns

    if human_turns == 0 or first_human_text is None:
        return None

    created = conv.get("created_at") or conv.get("createdAt") or ""
    date_str = created[:10] if re.match(r"\d{4}-\d{2}-\d{2}", created[:10]) else ""
    if not date_str:
        date_str = _today_iso()

    name = (conv.get("name") or "").strip()
    return {
        "uuid": conv.get("uuid") or conv.get("id") or "",
        "name": name,
        "date": date_str,
        "first_human_text": first_human_text,
        "human_turns": human_turns,
        "assistant_turns": assistant_turns,
        "attachments": attachments,
        "transcript": "\n".join(transcript_lines).rstrip() + "\n",
    }


def slug_for(meta: dict) -> str:
    base = meta["name"] if meta["name"] else meta["first_human_text"]
    slug = slugify(base)
    # Append stable 8-char suffix so same-date same-title sessions don't collide.
    uuid = (meta.get("uuid") or "").strip()
    if uuid:
        suffix = re.sub(r"[^a-z0-9]", "", uuid.lower())[:8]
    else:
        suffix = ""
    if not suffix:
        seed = f"{meta.get('date','')}{meta.get('name','')}{meta.get('first_human_text','')[:200]}"
        suffix = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{suffix}"


def render_body(meta: dict, source_path: str, imported_at: str) -> str:
    source_id = meta.get("uuid") or ""
    fm_lines = [
        "---",
        f"title: \"Sessie-log {meta['date']}\"",
        "type: raw-sessie",
        "source: claudeai-export",
        f"source_id: {source_id}",
        f"source_path: {source_path}",
        f"date: {meta['date']}",
        f"imported_at: {imported_at}",
        f"turns_user: {meta['human_turns']}",
        f"turns_assistant: {meta['assistant_turns']}",
        "tags: [claude-sessie, import-claudeai]",
        "status: raw",
    ]
    if meta["name"]:
        # quote om YAML-special-chars te vermijden
        safe_name = meta["name"].replace('"', '\\"')
        fm_lines.append(f"conversation_name: \"{safe_name}\"")
    fm_lines.append("---")

    doel_parts = []
    if meta["name"]:
        doel_parts.append(meta["name"])
    first = meta["first_human_text"].strip()
    if len(first) > 500:
        first = first[:500].rstrip() + "..."
    doel_parts.append(first)
    doel = "\n\n".join(doel_parts)

    samenvatting = (
        f"Imported from claude.ai export. "
        f"{meta['human_turns']} human turns, {meta['assistant_turns']} assistant turns."
    )

    if meta["attachments"]:
        output_lines = [f"- {a}" for a in meta["attachments"]]
    else:
        output_lines = ["- (geen attachments)"]

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
        *output_lines,
        "",
        "## Nieuwe kennis",
        "_To be compiled by /wiki._",
        "",
        "## Vervolgacties",
        "",
        "## AI-verantwoording",
        "- Bron: claude.ai data-export",
        f"- Conversation-id: {meta['uuid'] or 'onbekend'}",
        "",
        "## Transcript",
        "",
        meta["transcript"],
    ])
    return body


def locate_conversations_json(path: Path) -> Path | None:
    """Zoek conversations.json in een ZIP of in een directory."""
    if path.is_file() and path.suffix.lower() == ".json":
        return path
    if path.is_dir():
        c = path / "conversations.json"
        if c.exists():
            return c
        # fallback: recursieve zoektocht
        for p in path.rglob("conversations.json"):
            return p
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Importeer claude.ai export (zip of conversations.json) naar 01-raw/sessies/."
    )
    parser.add_argument("--input", type=Path, required=True,
                        help="Pad naar conversations.json of export.zip")
    parser.add_argument("--vault", type=Path, default=VAULT_DEFAULT,
                        help=f"Vault root (default: {VAULT_DEFAULT})")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int, default=0,
                        help="Beperk aantal conversaties (0 = alle).")
    args = parser.parse_args()

    out_dir: Path = args.vault / "01-raw" / "sessies"
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    src: Path = args.input
    if not src.exists():
        print(f"[error] input bestaat niet: {src}", file=sys.stderr)
        return 2

    tmpdir: Path | None = None
    try:
        if src.is_file() and src.suffix.lower() == ".zip":
            tmpdir_obj = tempfile.mkdtemp(prefix="claudeai-export-")
            tmpdir = Path(tmpdir_obj)
            try:
                with zipfile.ZipFile(src) as zf:
                    # zip-slip + symlink guard: ensure no member escapes tmpdir
                    # and no member is a symlink (defensive against future
                    # zipfile.extractall changes / platform quirks).
                    tmpdir_abs = os.path.abspath(tmpdir)
                    for member in zf.namelist():
                        info = zf.getinfo(member)
                        # Unix file type lives in the upper 4 bits of external_attr.
                        # 0o120000 == S_IFLNK (symlink).
                        mode = (info.external_attr >> 16) & 0o170000
                        if mode == 0o120000:
                            raise ValueError(f"refused: zip member is a symlink: {member!r}")
                        member_path = os.path.abspath(os.path.join(tmpdir_abs, member))
                        if not (member_path == tmpdir_abs or member_path.startswith(tmpdir_abs + os.sep)):
                            raise ValueError(f"refused: zip member escapes target dir: {member!r}")
                    zf.extractall(tmpdir)
            except zipfile.BadZipFile as e:
                print(f"[error] kan zip niet openen: {e}", file=sys.stderr)
                return 2
            except ValueError as e:
                print(f"[error] {e}", file=sys.stderr)
                return 2
            conv_json = locate_conversations_json(tmpdir)
        else:
            conv_json = locate_conversations_json(src)

        if conv_json is None:
            print(f"[error] conversations.json niet gevonden in {src}", file=sys.stderr)
            return 2

        try:
            data = json.loads(conv_json.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"[error] kan {conv_json} niet parsen: {e}", file=sys.stderr)
            return 2

        if not isinstance(data, list):
            # sommige exports: {"conversations": [...]}
            if isinstance(data, dict) and isinstance(data.get("conversations"), list):
                data = data["conversations"]
            else:
                print("[error] conversations.json heeft onverwacht formaat", file=sys.stderr)
                return 2

        if args.limit:
            data = data[: args.limit]

        imported = 0
        skipped = 0
        errors = 0
        files_out: list[str] = []
        errors_detail: list[dict] = []
        imported_at = _utcnow_iso()
        source_path_str = str(src.resolve())

        for conv in data:
            cid = ""
            if isinstance(conv, dict):
                cid = conv.get("uuid") or conv.get("id") or ""
            try:
                meta = parse_conversation(conv)
            except Exception as e:
                errors += 1
                errors_detail.append({"source_id": cid, "stage": "parse", "error": str(e)})
                if args.verbose:
                    print(f"[err] parse {cid}: {e}", file=sys.stderr)
                continue
            if meta is None:
                if args.verbose:
                    name = conv.get("name", "?") if isinstance(conv, dict) else "?"
                    print(f"[skip] no human turns: {name}")
                continue

            slug = slug_for(meta)
            target = out_dir / f"raw-sessie-{meta['date']}-{slug}.md"

            if target.exists() and not args.force:
                skipped += 1
                if args.verbose or not args.json:
                    print(f"[skip] exists: {target}")
                continue

            body = render_body(meta, source_path_str, imported_at)
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

    finally:
        if tmpdir is not None:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
