"""Offline parsers for subtitle and mail source files."""
from __future__ import annotations

import html
import mailbox
import re
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path

from _common import _utcnow_iso, slugify
from _liteparse import file_date, yaml_escape

SUBTITLE_EXTENSIONS = {".srt", ".vtt"}
MAIL_EXTENSIONS = {".eml", ".mbox"}
OFFLINE_EXTENSIONS = SUBTITLE_EXTENSIONS | MAIL_EXTENSIONS
SUPPORTED_SOURCE_EXTENSIONS = OFFLINE_EXTENSIONS

_TIMESTAMP = r"(?:\d{1,2}:)?\d{2}:\d{2}[,.]\d{1,3}"
_CUE_RE = re.compile(
    rf"^\s*({_TIMESTAMP})\s*-->\s*({_TIMESTAMP})(?:\s+.*)?$"
)


class OfflineParseError(RuntimeError):
    """The source cannot be converted into useful offline text."""


@dataclass(frozen=True)
class ParsedOffline:
    text: str
    unit_count: int
    engine: str
    source_format: str
    title: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    message_index: int | None = None


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "head"}:
            self.ignored += 1
        elif tag.lower() in {"br", "p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "head"} and self.ignored:
            self.ignored -= 1
        elif tag.lower() in {"p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def _html_to_text(value: str) -> str:
    parser = _HTMLText()
    try:
        parser.feed(value or "")
        parser.close()
    except Exception as exc:
        raise OfflineParseError(f"HTML-body kon niet worden gelezen: {exc}") from exc
    return re.sub(r"[ \t]+", " ", parser.text()).strip()


def _normalise_timestamp(value: str) -> str:
    value = value.replace(",", ".")
    parts = value.split(":")
    if len(parts) == 2:
        parts.insert(0, "00")
    if len(parts) != 3:
        raise OfflineParseError(f"ongeldige ondertitel-timestamp: {value}")
    hours, minutes, seconds = parts
    seconds, _, millis = seconds.partition(".")
    try:
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}.{millis[:3].ljust(3, '0')}"
    except ValueError as exc:
        raise OfflineParseError(f"ongeldige ondertitel-timestamp: {value}") from exc


def _clean_subtitle_text(lines: list[str], source_format: str) -> list[str]:
    cleaned: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if source_format == ".vtt":
            line = re.sub(
                r"<v(?:\.[^>]*)?\s+([^>]+)>",
                lambda match: f"{html.unescape(match.group(1).strip())}: ",
                line,
                flags=re.IGNORECASE,
            )
            line = re.sub(r"</v>|<[^>]+>", "", line, flags=re.IGNORECASE)
        line = html.unescape(line).strip()
        if line:
            cleaned.append(line)
    return cleaned


def parse_subtitle(path: Path) -> list[ParsedOffline]:
    source_format = path.suffix.lower()
    try:
        raw = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        raise OfflineParseError(f"ondertitel kon niet worden gelezen: {exc}") from exc
    blocks = re.split(r"\n\s*\n", raw.replace("\r\n", "\n").replace("\r", "\n"))
    cues: list[str] = []
    saw_candidate = False
    for block in blocks:
        lines = block.splitlines()
        if not lines:
            continue
        first = lines[0].strip().upper()
        if source_format == ".vtt" and first.startswith("WEBVTT"):
            continue
        if first.startswith(("NOTE", "STYLE", "REGION")):
            continue
        timestamp_index = None
        for index, line in enumerate(lines):
            if _CUE_RE.match(line):
                timestamp_index = index
                break
        if timestamp_index is None:
            if any(line.strip() for line in lines):
                saw_candidate = True
            continue
        match = _CUE_RE.match(lines[timestamp_index])
        assert match is not None
        start = _normalise_timestamp(match.group(1))
        text_lines = _clean_subtitle_text(lines[timestamp_index + 1:], source_format)
        if not text_lines:
            saw_candidate = True
            continue
        cues.append(f"[{start}] " + "\n".join(text_lines))
    if not cues:
        detail = "geen bruikbare cues" if saw_candidate else "lege of onleesbare ondertitel"
        raise OfflineParseError(f"{path.name}: {detail}")
    return [ParsedOffline(
        text="\n\n".join(cues),
        unit_count=len(cues),
        engine="stdlib-subtitle",
        source_format=source_format.lstrip("."),
        title=path.stem,
    )]


def _header(message, name: str) -> str:
    values = message.get_all(name, []) or []
    return ", ".join(str(value).strip() for value in values if str(value).strip())


def _message_body(message) -> str:
    plain: list[str] = []
    html_parts: list[str] = []
    if message.is_multipart():
        parts = message.walk()
    else:
        parts = [message]
    for part in parts:
        if part.is_multipart():
            continue
        if part.get_content_disposition() == "attachment":
            continue
        content_type = part.get_content_type().lower()
        if content_type == "text/plain":
            try:
                value = part.get_content()
            except Exception:
                value = part.get_payload(decode=True) or ""
            plain.append(value if isinstance(value, str) else value.decode("utf-8", "replace"))
        elif content_type == "text/html":
            try:
                value = part.get_content()
            except Exception:
                value = part.get_payload(decode=True) or ""
            html_parts.append(value if isinstance(value, str) else value.decode("utf-8", "replace"))
    if plain:
        body = "\n\n".join(plain)
    elif html_parts:
        body = _html_to_text("\n".join(html_parts))
    else:
        body = ""
    return body.replace("\r\n", "\n").replace("\r", "\n").strip()


def _parse_message(message, source: Path, index: int) -> ParsedOffline:
    metadata = {
        "from": _header(message, "From"),
        "to": _header(message, "To"),
        "cc": _header(message, "Cc"),
        "subject": _header(message, "Subject"),
        "date": _header(message, "Date"),
        "message_id": _header(message, "Message-ID"),
    }
    body = _message_body(message)
    subject = metadata["subject"] or source.stem
    return ParsedOffline(
        text=body,
        unit_count=1,
        engine="stdlib-email",
        source_format=source.suffix.lower().lstrip("."),
        title=subject,
        metadata={key: value for key, value in metadata.items() if value},
        message_index=index,
    )


def parse_mail(path: Path) -> list[ParsedOffline]:
    try:
        if path.suffix.lower() == ".mbox":
            box = mailbox.mbox(str(path), create=False)
            try:
                messages = [box[key] for key in box.keys()]
            finally:
                box.close()
        else:
            messages = [BytesParser(policy=policy.default).parsebytes(path.read_bytes())]
    except (OSError, ValueError, mailbox.Error) as exc:
        raise OfflineParseError(f"mail kon niet worden gelezen: {exc}") from exc
    if not messages:
        raise OfflineParseError(f"{path.name}: mailbox bevat geen berichten")
    return [_parse_message(message, path, index) for index, message in enumerate(messages, 1)]


def parse_offline_source(path: Path) -> list[ParsedOffline]:
    suffix = path.suffix.lower()
    if suffix in SUBTITLE_EXTENSIONS:
        return parse_subtitle(path)
    if suffix in MAIL_EXTENSIONS:
        return parse_mail(path)
    raise OfflineParseError(f"niet-ondersteunde offline bron: {suffix}")


def offline_output_path(vault: Path, source: Path, *, prefix: str = "",
                        message_index: int | None = None) -> Path:
    base = slugify(f"{prefix}-{source.stem}" if prefix else source.stem)
    base += f"-{source.suffix.lower().lstrip('.') or 'source'}"
    if message_index is not None:
        base += f"-message-{int(message_index):03d}"
    return vault / "05-bronnen" / "liteparse" / f"bron-{file_date(source)}-{base}.md"


def render_offline_markdown(source: Path, parsed: ParsedOffline, *,
                            title: str | None = None, prefix: str = "") -> str:
    resolved = str(source.resolve())
    doc_title = title or parsed.title or source.stem
    source_id = parsed.metadata.get("message_id") or resolved
    if parsed.message_index is not None and source.suffix.lower() == ".mbox":
        source_id = f"{source_id}#message-{parsed.message_index:03d}"
    tags = ["bron", "document", parsed.source_format]
    frontmatter = {
        "title": doc_title,
        "type": "bron",
        "source": "offline-parser",
        "source_id": source_id,
        "source_path": resolved,
        "source_format": parsed.source_format,
        "parse_engine": parsed.engine,
        "parse_engine_version": "stdlib",
        "unit_count": str(parsed.unit_count),
        "created": file_date(source),
        "parsed_at": _utcnow_iso(),
        "tags": tags,
        "status": "raw",
    }
    if parsed.message_index is not None:
        frontmatter["message_index"] = str(parsed.message_index)
    for key in ("from", "to", "cc", "subject", "date", "message_id"):
        value = parsed.metadata.get(key)
        if value:
            frontmatter[key] = value
    if prefix:
        frontmatter["import_prefix"] = prefix
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(yaml_escape(str(item)) for item in value)}]")
        else:
            lines.append(f"{key}: {yaml_escape(str(value))}")
    lines.extend([
        "---",
        "",
        f"# {doc_title}",
        "",
        "## Source",
        f"- Original: `{resolved}`",
        f"- Parsed with: {parsed.engine}",
        "",
        "## Content",
        parsed.text.strip(),
    ])
    text = "\n".join(lines)
    return text if text.endswith("\n") else text + "\n"
