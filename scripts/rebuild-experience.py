#!/usr/bin/env python3
"""Rebuild the experience store and optional local vector projection."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util


def _builder():
    spec = importlib.util.spec_from_file_location(
        "build_experience_index", Path(__file__).with_name("build-experience-index.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=None)
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--incremental", action="store_true",
                        help="preserve existing derived records and add new tasks")
    parser.add_argument("--records-only", action="store_true",
                        help="rebuild durable records without embedding vectors")
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args(argv)
    vault = args.vault or Path(os.environ.get("KENNISBANK_VAULT", "."))
    db = args.db or vault / ".claude" / "kb-experience.db"
    embed_fn = None
    embed_id = ""
    if not args.records_only:
        try:
            import _embeddings as emb
            _provider, _model, endpoint, _key = emb._resolve()
            if not emb.endpoint_allowed(emb.provider(), endpoint):
                raise RuntimeError("experience rebuild requires an allowed local embedding endpoint")
            embed_fn = lambda text: emb.embed(text, kind="doc")
            embed_id = emb.embed_id()
        except Exception as exc:
            print(json.dumps({"status": "failed", "reason": str(exc)}), file=sys.stderr)
            return 1
    progress_fn = None
    if args.progress:
        progress_fn = lambda event: print(json.dumps({"progress": event}, sort_keys=True),
                                          file=sys.stderr, flush=True)
    builder = _builder()
    result = builder.rebuild_experience_store(
        db, rebuild=not args.incremental, embed_fn=embed_fn, embed_id=embed_id,
        progress_fn=progress_fn)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
