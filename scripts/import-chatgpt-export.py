#!/usr/bin/env python3
"""
import-chatgpt-export.py - Importeer een ChatGPT data-export naar 01-raw/sessies/.

Zo krijg je controle over je eigen ChatGPT-gesprekken terug: OpenAI's export is
een ZIP met conversations.json; dit script destilleert er raw-sessie-logs uit die
daarna via /wiki en de memory-sweep tot herbruikbare kennis worden verwerkt -
lokaal, in je soevereine vault. Zie README (sectie "ChatGPT data-export") voor
hoe je de export bij OpenAI aanvraagt.

SCHEMA-VERSCHIL met de claude.ai-export (belangrijk): ChatGPT slaat elk gesprek
op als een BOOM, niet als een platte berichtenlijst. Per conversation:
  - title        string
  - create_time  unix-float
  - mapping      dict van node_id -> {id, parent, children, message}
                 message: {author: {role}, create_time, content: {parts: [...]}}
Wij lopen de mapping in tijdsvolgorde (create_time) en houden user/assistant-
beurten; system/tool en lege nodes vallen weg. Eén raw-sessie-log per gesprek.

Gebruik:
  python3 import-chatgpt-export.py --input /path/to/conversations.json
  python3 import-chatgpt-export.py --input /path/to/chatgpt-export.zip
  python3 import-chatgpt-export.py --input export.zip --dry-run --verbose
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


def extract_parts_text(message: dict) -> str:
    """ChatGPT content.parts is een lijst van strings (of dicts met 'text')."""
    content = message.get("content")
    if not isinstance(content, dict):
        return ""
    parts = content.get("parts")
    if not isinstance(parts, list):
        return ""
    out = []
    for p in parts:
        if isinstance(p, str):
            out.append(p)
        elif isinstance(p, dict):
            # multimodale parts: neem een tekstveld als het er is, sla binaire over
            for key in ("text", "content"):
                v = p.get(key)
                if isinstance(v, str) and v.strip():
                    out.append(v)
                    break
    return "\n".join(s for s in out if s and s.strip())


def ordered_messages(mapping: dict) -> list:
    """Geef de node-messages in tijdsvolgorde (create_time), user/assistant only."""
    rows = []
    for node in mapping.values():
        if not isinstance(node, dict):
            continue
        msg = node.get("message")
        if not isinstance(msg, dict):
            continue
        author = msg.get("author") or {}
        role = (author.get("role") or "").lower()
        if role not in ("user", "assistant"):
            continue
        text = extract_parts_text(msg).strip()
        if not text:
            continue
        ct = msg.get("create_time")
        try:
            ct = float(ct) if ct is not None else 0.0
        except (TypeError, ValueError):
            ct = 0.0
        rows.append((ct, role, text))
    # stabiel op tijd; nodes zonder create_time (0.0) blijven in mapping-volgorde
    rows.sort(key=lambda r: r[0])
    return rows


def parse_conversation(conv: dict) -> dict | None:
    mapping = conv.get("mapping")
    if not isinstance(mapping, dict):
        return None
    rows = ordered_messages(mapping)
    if not rows:
        return None

    first_human_text = None
    human_turns = 0
    assistant_turns = 0
    transcript_lines = []
    for _ct, role, text in rows:
        if role == "user":
            human_turns += 1
            if first_human_text is None:
                first_human_text = text
            transcript_lines.append("**Human:** " + text)
        else:
            assistant_turns += 1
            transcript_lines.append("**Assistant:** " + text)
        transcript_lines.append("")

    if human_turns == 0 or first_human_text is None:
        return None

    ct = conv.get("create_time")
    date_str = ""
    if isinstance(ct, (int, float)) and ct > 0:
        try:
            # datum uit unix-tijd zonder tz-afhankelijkheid: gebruik UTC-kalender
            import datetime
            date_str = datetime.datetime.fromtimestamp(
                ct, datetime.timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, OverflowError, OSError):
            date_str = ""
    if not date_str:
        date_str = _today_iso()

    return {
        "id": conv.get("id") or conv.get("conversation_id") or "",
        "name": (conv.get("title") or "").strip(),
        "date": date_str,
        "first_human_text": first_human_text,
        "human_turns": human_turns,
        "assistant_turns": assistant_turns,
        "transcript": "\n".join(transcript_lines).rstrip() + "\n",
    }


def slug_for(meta: dict) -> str:
    base = meta["name"] if meta["name"] else meta["first_human_text"]
    slug = slugify(base)
    cid = (meta.get("id") or "").strip()
    if cid:
        suffix = re.sub(r"[^a-z0-9]", "", cid.lower())[:8]
    else:
        suffix = ""
    if not suffix:
        seed = f"{meta.get('date','')}{meta.get('name','')}{meta.get('first_human_text','')[:200]}"
        suffix = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{suffix}"


def render_body(meta: dict, source_path: str, imported_at: str) -> str:
    fm_lines = [
        "---",
        f"title: \"Sessie-log {meta['date']}\"",
        "type: raw-sessie",
        "source: chatgpt-export",
        f"source_id: {meta.get('id') or ''}",
        f"source_path: {source_path}",
        f"date: {meta['date']}",
        f"imported_at: {imported_at}",
        f"turns_user: {meta['human_turns']}",
        f"turns_assistant: {meta['assistant_turns']}",
        "tags: [chatgpt-sessie, import-chatgpt]",
        "status: raw",
    ]
    if meta["name"]:
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
        f"Imported from ChatGPT export. "
        f"{meta['human_turns']} human turns, {meta['assistant_turns']} assistant turns."
    )

    body = "\n".join(fm_lines) + "\n\n" + "\n".join([
        f"# Sessie-log {meta['date']}",
        "",
        "## Doel",
        doel,
        "",
        "## Samenvatting",
        samenvatting,
        "",
        "## Nieuwe kennis",
        "_To be compiled by /wiki._",
        "",
        "## Vervolgacties",
        "",
        "## AI-verantwoording",
        "- Bron: ChatGPT data-export",
        f"- Conversation-id: {meta['id'] or 'onbekend'}",
        "",
        "## Transcript",
        "",
        meta["transcript"],
    ])
    return body


def locate_conversations_json(path: Path) -> Path | None:
    if path.is_file() and path.suffix.lower() == ".json":
        return path
    if path.is_dir():
        c = path / "conversations.json"
        if c.exists():
            return c
        for p in path.rglob("conversations.json"):
            return p
    return None


def _extract_zip_safely(src: Path, tmpdir: Path) -> Path | None:
    """Zip-slip + symlink guard (zelfde discipline als de claude.ai-importer)."""
    tmpdir_abs = os.path.abspath(tmpdir)
    with zipfile.ZipFile(src) as zf:
        for member in zf.namelist():
            info = zf.getinfo(member)
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ValueError(f"refused: zip member is a symlink: {member!r}")
            member_path = os.path.abspath(os.path.join(tmpdir_abs, member))
            if not (member_path == tmpdir_abs or member_path.startswith(tmpdir_abs + os.sep)):
                raise ValueError(f"refused: zip member escapes target dir: {member!r}")
        zf.extractall(tmpdir)
    return locate_conversations_json(tmpdir)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Importeer ChatGPT export (zip of conversations.json) naar 01-raw/sessies/.")
    parser.add_argument("--input", type=Path, required=True,
                        help="Pad naar conversations.json of chatgpt-export.zip")
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
            tmpdir = Path(tempfile.mkdtemp(prefix="chatgpt-export-"))
            try:
                conv_json = _extract_zip_safely(src, tmpdir)
            except zipfile.BadZipFile as e:
                print(f"[error] kan zip niet openen: {e}", file=sys.stderr)
                return 2
            except ValueError as e:
                print(f"[error] {e}", file=sys.stderr)
                return 2
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
            if isinstance(data, dict) and isinstance(data.get("conversations"), list):
                data = data["conversations"]
            else:
                print("[error] conversations.json heeft onverwacht formaat", file=sys.stderr)
                return 2

        if args.limit:
            data = data[: args.limit]

        imported = skipped = errors = 0
        files_out: list[str] = []
        errors_detail: list[dict] = []
        imported_at = _utcnow_iso()
        source_path_str = str(src.resolve())

        for conv in data:
            cid = conv.get("id") or conv.get("conversation_id") or "" if isinstance(conv, dict) else ""
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
                    title = conv.get("title", "?") if isinstance(conv, dict) else "?"
                    print(f"[skip] no usable turns: {title}")
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

        print_summary({
            "imported": imported, "skipped": skipped, "errors": errors,
            "files": files_out, "errors_detail": errors_detail,
        }, args.json)
        return 0 if errors == 0 else 1

    finally:
        if tmpdir is not None:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
