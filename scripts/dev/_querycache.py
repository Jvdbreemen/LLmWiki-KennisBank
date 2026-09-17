"""_querycache.py - disk-backed query-embedding cache for the eval harnesses.

Extracted verbatim from the L2 scene experiment (TASK-190), because
rank-factors and rerank-ceiling imported that whole driver solely to borrow
this class. The scene layer itself was removed in ADR-008; this cache
outlived it and is still used by both harnesses. Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class QueryCache:
    """Disk-backed query-embedding cache, keyed by model identity.

    Mixing vectors from two embedding models would compare nonsense while
    looking perfectly healthy, so the model id is part of the cache identity
    and a mismatch discards the file rather than merging with it.
    """

    def __init__(self, path: Path, embed_id: str):
        self.path = Path(path)
        self.embed_id = embed_id
        self.data = {}
        self.hits = 0
        self.misses = 0
        if self.path.exists():
            try:
                blob = json.loads(self.path.read_text(encoding="utf-8"))
                if blob.get("embed_id") == embed_id:
                    self.data = blob.get("vectors", {})
            except Exception:
                self.data = {}

    @staticmethod
    def key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]

    def get_or_embed(self, text: str, embed_fn):
        k = self.key(text)
        vec = self.data.get(k)
        if vec is not None:
            self.hits += 1
            return vec
        self.misses += 1
        vec = embed_fn(text)
        if vec is not None:
            self.data[k] = list(vec)
        return vec

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"embed_id": self.embed_id, "vectors": self.data}),
            encoding="utf-8")
