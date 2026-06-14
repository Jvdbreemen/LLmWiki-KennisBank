"""Shared helpers for parsing minimal YAML frontmatter from markdown files.

Anchored regex match on the closing '---' fence, which must sit on its own
line. Avoids false-positive detections on horizontal rules in body content.
"""
import re

_FENCE_RE = re.compile(r"^---\s*$", re.MULTILINE)


def split_frontmatter(text: str) -> tuple[str, str]:
    """Split a markdown document into (frontmatter_yaml, body).

    Returns:
        (frontmatter_yaml, body): frontmatter_yaml is the raw YAML lines
        between the opening and closing fences (no fences included).
        body is everything after the closing fence (with leading newline
        stripped).
        If the document has no frontmatter (no opening fence on line 1),
        returns ("", text) unchanged.
    """
    if not text.startswith("---"):
        return "", text
    # Match the closing fence after position 3 (past the opening "---")
    m = _FENCE_RE.search(text, 3)
    if not m:
        return "", text
    fm = text[3:m.start()].lstrip("\n").rstrip()
    body = text[m.end():]
    if body.startswith("\n"):
        body = body[1:]
    return fm, body


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse a markdown document's frontmatter into a dict.

    Returns (data, body). data is a dict of top-level YAML keys. Values are
    kept as strings; lists in the form '[a, b]' are parsed into Python
    lists; otherwise the value is returned as a stripped string with any
    enclosing single or double quotes removed.

    If the document has no parseable frontmatter, returns ({}, text).
    """
    fm_text, body = split_frontmatter(text)
    if not fm_text:
        return {}, body
    data: dict = {}
    for line in fm_text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        key = key.strip()
        raw = raw.strip()
        if raw.startswith("[") and raw.endswith("]"):
            items = [
                item.strip().strip("'\"")
                for item in raw[1:-1].split(",")
                if item.strip()
            ]
            data[key] = items
        else:
            # strip a single layer of matching quotes
            if (raw.startswith('"') and raw.endswith('"')) or (
                raw.startswith("'") and raw.endswith("'")
            ):
                raw = raw[1:-1]
            data[key] = raw
    return data, body
