#!/usr/bin/env python3
"""Atomically rebuild the reviewed experience projection from its ledger."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _experience  # noqa: E402
import _settings  # noqa: E402


def _builder():
    spec = importlib.util.spec_from_file_location(
        "build_experience_index", Path(__file__).with_name("build-experience-index.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _optional_embedding(records_only: bool):
    if records_only:
        return None, ""
    try:
        import _embeddings as emb
        _provider, _model, endpoint, _key = emb._resolve()
        if not emb.endpoint_allowed(emb.provider(), endpoint):
            return None, ""
        return (lambda text: emb.embed(text, kind="doc")), emb.embed_id()
    except Exception:
        return None, ""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=None)
    parser.add_argument("--ledger", type=Path, default=None)
    parser.add_argument("--projection", "--db", dest="projection", type=Path,
                        default=None)
    parser.add_argument("--incremental", action="store_true",
                        help="deprecated: production projections always rebuild atomically")
    parser.add_argument("--records-only", action="store_true",
                        help="build a lexical-only projection without embeddings")
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args(argv)
    configured = str(args.vault or os.environ.get("KENNISBANK_VAULT") or "").strip()
    if not configured:
        print(json.dumps({"status": "invalid", "mutated": False,
                          "reason": "--vault or KENNISBANK_VAULT is required"},
                         sort_keys=True))
        return 2
    root = Path(configured).expanduser().resolve()
    # Build authority belongs to the selected vault, not to ambient settings
    # or a custom output path. Refuse before loading embeddings or a builder.
    if not _settings.get("experience_projection", False, vault=root):
        print(json.dumps({"status": "disabled", "mutated": False,
                          "experiences": 0,
                          "reason": "experience_projection is disabled"},
                         sort_keys=True))
        return 0
    ledger = args.ledger or _experience.ledger_path(root)
    projection = args.projection or _experience.projection_path(root)
    embed_fn, embed_id = _optional_embedding(args.records_only)
    progress_fn = None
    if args.progress:
        progress_fn = lambda event: print(
            json.dumps({"progress": event}, sort_keys=True),
            file=sys.stderr, flush=True)
    result = _builder().rebuild_experience_projection(
        ledger, projection, embed_fn=embed_fn, embed_id=embed_id,
        progress_fn=progress_fn)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
