#!/usr/bin/env python3
"""_sweepstate.py - watermark + transcript-reader voor de capture-sweep.

Spiegelt distill-notify's .distilled-pattern met een EIGEN .swept-watermark, zodat
de geheugen-sweep onafhankelijk van de destillatie bijhoudt welke transcripts al
tot memory verwerkt zijn. transcript_text() reduceert een CC-.jsonl tot platte
user/assistant-tekst (fail-soft).

Stdlib only.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

WATERMARK = ".swept"


def _tdir(vault=None) -> Path:
    return (vault or vault_root()) / "01-raw" / "transcripts"


def _watermark(vault=None) -> set:
    f = _tdir(vault) / WATERMARK
    try:
        return {ln.strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()}
    except OSError:
        return set()


def pending(vault=None) -> list:
    d = _tdir(vault)
    if not d.exists():
        return []
    done = _watermark(vault)
    return [p for p in sorted(d.glob("*.jsonl")) if p.stem not in done]


def mark(stems, vault=None) -> int:
    done = _watermark(vault)
    new = [s for s in dict.fromkeys(stems) if s and s not in done]
    if not new:
        return 0
    f = _tdir(vault) / WATERMARK
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            for s in new:
                fh.write(s + "\n")
    except OSError as e:
        print(f"[sweepstate] kan watermark niet schrijven: {e}", file=sys.stderr)
        return 0
    return len(new)


def _block_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "\n".join(parts)
    return ""


def transcript_text(jsonl_path) -> str:
    """Reduceer een CC-transcript-jsonl tot platte user/assistant-tekst. Fail-soft."""
    out = []
    try:
        with Path(jsonl_path).open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                msg = rec.get("message") if isinstance(rec, dict) else None
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role")
                if role in ("user", "assistant"):
                    t = _block_text(msg.get("content")).strip()
                    if t:
                        out.append(f"{role}: {t}")
    except Exception:
        return ""
    return "\n\n".join(out)
