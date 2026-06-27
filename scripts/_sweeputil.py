#!/usr/bin/env python3
"""_sweeputil.py - chunking + dedup voor de capture-sweep. Stdlib + _embeddings."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _embeddings import cosine  # noqa: E402


def chunk(text: str, max_chars: int = 6000, overlap: int = 200) -> list:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    paras = text.split("\n\n")
    chunks, cur = [], ""
    for p in paras:
        if cur and len(cur) + len(p) + 2 > max_chars:
            chunks.append(cur)
            cur = (cur[-overlap:] + "\n\n" + p) if overlap else p
        else:
            cur = (cur + "\n\n" + p) if cur else p
    if cur.strip():
        chunks.append(cur)
    # harde splitsing voor een enkele te lange alinea
    out = []
    for c in chunks:
        while len(c) > max_chars + overlap:
            out.append(c[:max_chars])
            c = c[max_chars - overlap:]
        out.append(c)
    return out


def is_duplicate(vec, existing_vecs, threshold: float = 0.92) -> bool:
    if not vec or not existing_vecs:
        return False
    for ev in existing_vecs:
        if ev and cosine(vec, ev) > threshold:
            return True
    return False
