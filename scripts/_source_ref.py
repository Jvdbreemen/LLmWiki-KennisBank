#!/usr/bin/env python3
"""Canonical SourceRef v1 creation and exact local evidence resolution.

A SourceRef identifies one immutable interpretation of a passage. Resolution
never searches for replacement text: changed content is stale evidence. Paths
are vault-relative and restricted to approved raw-source roots.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath

SCHEMA_VERSION = 1
OFFSET_UNIT = "unicode_codepoint"
APPROVED_ROOTS = (
    "01-raw/transcripts",
    "01-raw/sessies",
    "05-bronnen",
    "08-archive",
)
REDACTION_STATES = {"clear", "redacted"}


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _normalise_relative(source_path: str) -> str:
    raw = str(source_path or "").strip()
    if not raw or Path(raw).is_absolute() or PureWindowsPath(raw).is_absolute():
        raise ValueError("source_path must be vault-relative")
    normalised = raw.replace("\\", "/")
    path = PurePosixPath(normalised)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("source_path contains traversal or empty segments")
    result = path.as_posix()
    if not any(result == root or result.startswith(root + "/")
               for root in APPROVED_ROOTS):
        raise ValueError("source_path is outside approved roots")
    return result


def _candidate(vault: Path, source_path: str, *, require_exists: bool) -> Path:
    root = Path(vault).resolve()
    relative = _normalise_relative(source_path)
    unresolved = root.joinpath(*PurePosixPath(relative).parts)
    try:
        resolved = unresolved.resolve(strict=require_exists)
    except (OSError, RuntimeError) as exc:
        if require_exists:
            raise FileNotFoundError(relative) from exc
        resolved = unresolved.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("resolved source escapes the vault") from exc
    approved = False
    for allowed in APPROVED_ROOTS:
        allowed_path = root.joinpath(*PurePosixPath(allowed).parts).resolve(strict=False)
        try:
            resolved.relative_to(allowed_path)
            approved = True
            break
        except ValueError:
            continue
    if not approved:
        raise ValueError("resolved source escapes approved roots")
    return resolved


def _is_redacted(path: Path, text: str) -> bool:
    name = path.name.lower()
    if ".redacted." in name or name.endswith(".redacted"):
        return True
    header = text[:4000].lower()
    return "redacted:" in header and any(
        marker in header for marker in
        ("redacted: true", "redacted: yes", "redacted: 1"))


def _identity_payload(ref: dict) -> dict:
    keys = (
        "schema_version", "source_path", "source_sha256", "chunk_id",
        "start", "end", "offset_unit", "passage_sha256",
    )
    return {key: ref[key] for key in keys}


def source_ref_id(ref: dict) -> str:
    """Return the deterministic content-addressed id for a SourceRef body."""
    encoded = json.dumps(
        _identity_payload(ref), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sr_" + hashlib.sha256(encoded).hexdigest()


def make_source_ref(vault: Path, source_path: str, *, start: int, end: int,
                    chunk_id: str = "", captured_at: str = "",
                    redaction_state: str = "clear") -> dict:
    """Create an exact SourceRef from a current approved local source."""
    relative = _normalise_relative(source_path)
    if redaction_state not in REDACTION_STATES:
        raise ValueError("invalid redaction_state")
    path = _candidate(Path(vault), relative, require_exists=True)
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    start, end = int(start), int(end)
    if start < 0 or end <= start or end > len(text):
        raise ValueError("invalid half-open source offsets")
    passage = text[start:end]
    ref = {
        "schema_version": SCHEMA_VERSION,
        "source_path": relative,
        "source_sha256": _sha256_bytes(raw),
        "chunk_id": str(chunk_id or ""),
        "start": start,
        "end": end,
        "offset_unit": OFFSET_UNIT,
        "passage_sha256": _sha256_bytes(passage.encode("utf-8")),
        "captured_at": str(captured_at or ""),
        "redaction_state": redaction_state,
    }
    ref["source_ref_id"] = source_ref_id(ref)
    return ref


def legacy_source_candidate(source_path: str) -> dict:
    """Preserve a legacy string path without pretending it is exact evidence."""
    return {
        "legacy_source_path": _normalise_relative(source_path),
        "source_ref": None,
        "evidence_state": "unverified",
    }


def _invalid(reason: str) -> dict:
    return {"status": "invalid", "fresh": False, "reason": reason}


def resolve_source_ref(vault: Path, ref: dict) -> dict:
    """Validate and hydrate an exact ref, or return an explicit safe state."""
    if not isinstance(ref, dict):
        return _invalid("source_ref must be an object")
    try:
        if ref.get("schema_version") != SCHEMA_VERSION:
            return _invalid("unsupported schema_version")
        if ref.get("offset_unit") != OFFSET_UNIT:
            return _invalid("unsupported offset_unit")
        if ref.get("redaction_state") not in REDACTION_STATES:
            return _invalid("invalid redaction_state")
        if ref.get("redaction_state") == "redacted":
            return {"status": "redacted", "fresh": False,
                    "source_ref_id": ref.get("source_ref_id", "")}
        if ref.get("source_ref_id") != source_ref_id(ref):
            return _invalid("source_ref_id mismatch")
        relative = _normalise_relative(ref.get("source_path", ""))
        unresolved = Path(vault).resolve().joinpath(*PurePosixPath(relative).parts)
        if not unresolved.exists():
            return {"status": "missing", "fresh": False,
                    "source_ref_id": ref.get("source_ref_id", ""),
                    "source_path": relative}
        path = _candidate(Path(vault), relative, require_exists=True)
    except (KeyError, TypeError, ValueError, OSError) as exc:
        return _invalid(str(exc))
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (UnicodeError, OSError) as exc:
        return {"status": "unreadable", "fresh": False,
                "source_ref_id": ref.get("source_ref_id", ""),
                "source_path": relative, "reason": type(exc).__name__}

    if _is_redacted(path, text):
        return {"status": "redacted", "fresh": False,
                "source_ref_id": ref["source_ref_id"], "source_path": relative}
    if _sha256_bytes(raw) != ref.get("source_sha256"):
        return {"status": "stale", "fresh": False,
                "source_ref_id": ref["source_ref_id"], "source_path": relative,
                "reason": "source hash mismatch"}
    try:
        start, end = int(ref["start"]), int(ref["end"])
    except (KeyError, TypeError, ValueError):
        return _invalid("invalid offsets")
    if start < 0 or end <= start or end > len(text):
        return {"status": "stale", "fresh": False,
                "source_ref_id": ref["source_ref_id"], "source_path": relative,
                "reason": "offsets outside current source"}
    passage = text[start:end]
    if _sha256_bytes(passage.encode("utf-8")) != ref.get("passage_sha256"):
        return {"status": "stale", "fresh": False,
                "source_ref_id": ref["source_ref_id"], "source_path": relative,
                "reason": "passage hash mismatch"}
    return {
        "status": "valid",
        "fresh": True,
        "retrieval_route": "exact_ref",
        "source_ref_id": ref["source_ref_id"],
        "source_path": relative,
        "source_sha256": ref["source_sha256"],
        "chunk_id": ref.get("chunk_id", ""),
        "start": start,
        "end": end,
        "offset_unit": OFFSET_UNIT,
        "passage_sha256": ref["passage_sha256"],
        "passage": passage,
    }
