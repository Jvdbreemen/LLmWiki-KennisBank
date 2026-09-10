"""Generate private BGE-reranker score maps for TASK-245 development data.

This deliberately lives outside the production recall path.  It requires an
already-cached local model and writes only opaque score maps; queries, lessons,
and source references remain in the private fixture vault.  The accompanying
applicability evaluator performs threshold selection and reports aggregates.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "evaluate-experience-applicability.py"
spec = importlib.util.spec_from_file_location("task245_applicability", RUNNER_PATH)
if spec is None or spec.loader is None:
    raise ImportError(f"cannot load {RUNNER_PATH}")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def score(cases, records, model_path: Path, batch_size: int = 16):
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    runner.validate_cases(cases, records)
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_path, local_files_only=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    pairs = []
    ids = [runner._record_id(record) for record in records]
    for case in cases:
        for record in records:
            pairs.append((case["query"], runner.scoring_text(record)))
    values = []
    started = time.perf_counter()
    with torch.inference_mode():
        for start in range(0, len(pairs), batch_size):
            batch = pairs[start:start + batch_size]
            encoded = tokenizer(batch, padding=True, truncation=True,
                                max_length=512, return_tensors="pt")
            encoded = {key: value.to(device) for key, value in encoded.items()}
            logits = model(**encoded).logits.reshape(-1).detach().cpu().tolist()
            values.extend(float(value) for value in logits)
    scores = {}
    offset = 0
    for case in cases:
        scores[case["id"]] = dict(zip(ids, values[offset:offset + len(ids)]))
        offset += len(ids)
    return scores, {"model_path_sha256": _sha(model_path / "model.safetensors"),
                    "device": str(device), "pairs": len(pairs),
                    "batch_size": batch_size,
                    "scoring_ms": (time.perf_counter() - started) * 1000}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args(argv)
    if os.environ.get("HF_HUB_OFFLINE") != "1" or os.environ.get("TRANSFORMERS_OFFLINE") != "1":
        raise ValueError("offline model loading must be explicitly enabled")
    if args.batch_size < 1:
        raise ValueError("batch size must be positive")
    if not args.model_path.is_dir() or not (args.model_path / "model.safetensors").is_file():
        raise ValueError("model path must point to a local cached safetensors model")
    output = runner.validate_private_output(args.output)
    metadata_path = output.with_name(output.stem + "-metadata.json")
    if metadata_path.exists():
        raise ValueError("refusing to overwrite score metadata")
    cases = runner._read_jsonl(args.cases)
    records = runner._read_records(args.records)
    scores, info = score(cases, records, args.model_path.resolve(), args.batch_size)
    output.write_text(json.dumps(scores, indent=2) + "\n", encoding="utf-8")
    metadata_path.write_text(json.dumps({"schema_version": 1,
                                     "input_sha256": {"cases": _sha(args.cases),
                                                       "records": _sha(args.records)},
                                     **info}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
