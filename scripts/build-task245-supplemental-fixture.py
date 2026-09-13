"""Build a private, source-grounded supplemental TASK-245 fixture.

This is an evaluation utility, not a production importer.  The input spec is
private and the output is required to stay below the configured KennisBank
evaluation vault.  The builder never reads the sealed holdout or any review
database; it only resolves exact spans in the raw sessions named by the spec.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _experience
import _source_ref


STAMP = "2026-09-10T00:00:00Z"
AUDIT = {
    "authority": "test_fixture_auto_audit",
    "label_origin": "AUTO-AUTHORED source-grounded supplemental development probe",
    "human_review": False,
    "owner_canonical_review": False,
    "allowed_destination": "isolated test projection only",
    "production_eligibility": False,
    "automatic_advisory": False,
}


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _private_output(path: Path, vault: Path) -> Path:
    root = (vault / "06-claude" / "evaluations").resolve()
    output = path.resolve()
    if output == root or not output.is_relative_to(root):
        raise ValueError("output must be below the private evaluations root")
    if output.exists():
        raise ValueError("output must be a new directory")
    return output


def _field(value, path: str):
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def _evidence(vault: Path, spec: dict, index: int) -> tuple[dict, dict]:
    relative = "01-raw/transcripts/" + str(spec["source_file"])
    path = vault.joinpath(*Path(relative).parts)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    item = spec["evidence"][index]
    line_number = int(item["line"])
    raw_line = lines[line_number - 1]
    event = json.loads(raw_line)
    block_index = int(item.get("block", 0))
    block = event["message"]["content"][block_index]
    field_name = str(item.get("field", "content"))
    value = _field(block, field_name)
    if not isinstance(value, str):
        raise ValueError(f"evidence field is not text: {spec['id']}#{index}")
    begin = str(item["begin"])
    start = value.index(begin)
    end_marker = item.get("end")
    end = value.index(str(end_marker), start) if end_marker else len(value)
    excerpt = value[start:end]
    if not excerpt or any(str(marker) not in excerpt for marker in item.get("contains", [])):
        raise ValueError(f"evidence assertion failed: {spec['id']}#{index}")
    escaped = next(
        (candidate for candidate in (
            json.dumps(excerpt, ensure_ascii=False)[1:-1],
            json.dumps(excerpt, ensure_ascii=True)[1:-1],
        ) if candidate in raw_line),
        None,
    )
    if escaped is None:
        raise ValueError(f"serialized evidence span not found: {spec['id']}#{index}")
    offset = sum(len(line) for line in lines[: line_number - 1]) + raw_line.index(escaped)
    ref = _source_ref.make_source_ref(
        vault,
        relative,
        start=offset,
        end=offset + len(escaped),
        chunk_id=f"t245-supplemental-{spec['id']}-evidence-{index}",
        captured_at=STAMP,
    )
    resolved = _source_ref.resolve_source_ref(vault, ref)
    if resolved.get("status") != "valid" or resolved.get("passage") != escaped:
        raise ValueError(f"source ref did not resolve exactly: {spec['id']}#{index}")
    proof = {
        "source_ref_id": ref["source_ref_id"],
        "source_path": relative,
        "raw_line_1based": line_number,
        "content_block": block_index,
        "field": field_name,
        "event_role": event["message"]["role"],
        "event_type": block.get("type"),
        "exact_raw_excerpt": escaped,
        "decoded_excerpt": excerpt,
        "literal_assertions": item.get("contains", []),
        "note": "Exact raw JSON string span; evidence remains private and is not a production review.",
    }
    return ref, proof


def build(spec_path: Path, output_path: Path, vault: Path) -> None:
    specs = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(specs, list) or not specs:
        raise ValueError("spec must be a non-empty list")
    output = _private_output(output_path, vault)
    records, cases, sources = [], [], {}
    seen_files = set()
    for spec in specs:
        source_file = str(spec["source_file"])
        relative = "01-raw/transcripts/" + source_file
        if relative in seen_files:
            raise ValueError(f"source file reused by multiple groups: {source_file}")
        seen_files.add(relative)
        source_path = vault.joinpath(*Path(relative).parts)
        raw = source_path.read_bytes()
        lines = raw.decode("utf-8").splitlines()
        root_event = json.loads(lines[0])
        session_id = root_event.get("sessionId")
        if not session_id:
            raise ValueError(f"source has no session id: {source_file}")
        refs, proofs = [], []
        for index in range(len(spec["evidence"])):
            ref, proof = _evidence(vault, spec, index)
            refs.append(ref)
            proofs.append(proof)
        experience_id = "task245-supplemental-" + str(spec["id"]).lower()
        record = {
            "experience_id": experience_id,
            "session_id": session_id,
            "task_id": "supplemental-" + str(spec["id"]),
            "status": "validated",
            "evidence_state": "verified",
            "review_state": "accepted",
            "confidence": 0.0,
            "source_refs": refs,
            "outcome_refs": [],
            "exposed_refs": [],
            "procedure_refs": [],
            "skill_refs": [],
            "superseded_by": None,
            "schema_version": "1",
            "extractor_version": "task245-supplemental-auto-v1",
            "attribution_limits": "Auto-authored supplemental relevance fixture only; no human production review or causal utility claim.",
            "metadata": {"test_fixture_auto_audit": AUDIT, "split": "supplemental_development", "sealed": False},
            "source_proof": {"assertion": spec["assertion"], "excerpts": proofs, "state_scope": spec["observed_result"]},
        }
        for field in ("situation", "goal", "approach", "action", "observed_result", "lesson", "applicability", "attempt_state", "resolution_state", "outcome_state"):
            record[field] = spec[field]
        record["content_hash"] = _experience.experience_content_hash(record)
        records.append(record)
        for sign, entries in (("positive", spec["positive"]), ("negative", spec["negative"])):
            if len(entries) != 3:
                raise ValueError(f"{spec['id']} must contain three {sign} queries")
            for number, entry in enumerate(entries, 1):
                if sign == "positive":
                    query, kind, assertion = entry, None, spec["assertion"]
                    expected = experience_id
                    expected_refs = [ref["source_ref_id"] for ref in refs]
                    expected_attempt = spec["attempt_state"]
                    expected_resolution = spec["resolution_state"]
                    expected_state = spec["outcome_state"]
                else:
                    query, kind, assertion = entry
                    expected = None
                    expected_refs = []
                    expected_attempt = "unknown"
                    expected_resolution = "not_applicable"
                    expected_state = "unknown"
                cases.append({
                    "id": f"{spec['id']}-{sign[0].upper()}{number}",
                    "split": "supplemental_development",
                    "lesson_group": spec["id"],
                    "language": "nl",
                    "query": query,
                    "category": spec["domain"],
                    "polarity": sign,
                    "expected_experience": expected,
                    "expected_attempt_state": expected_attempt,
                    "expected_resolution_state": expected_resolution,
                    "expected_state": expected_state,
                    "expected_outcome_state": expected_state,
                    "expected_reference_ids": expected_refs,
                    "reference_assertion": assertion,
                    "negative_kind": kind,
                    "nearby_record": experience_id,
                    "abstention_scope": "all supplemental records",
                    "metadata": {"test_fixture_auto_audit": AUDIT, "sealed": False},
                })
        sources[relative] = {"path": relative, "sha256": _digest(raw), "bytes": len(raw), "session_id": session_id}
    output.mkdir(parents=True)
    (output / "cases.jsonl").write_text("".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in cases), encoding="utf-8")
    (output / "records.json").write_text(json.dumps(records, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    provenance = {
        "split": "supplemental_development",
        "sealed": False,
        "sources": list(sources.values()),
        "source_selection": "Independent September raw sessions selected by topic diversity; exact evidence spans were resolved before scoring.",
        "holdout_opened": False,
        "cross_split_independence": "not assessed here; the sealed holdout was intentionally not read",
        "lesson_count": len(records),
        "case_count": len(cases),
        "positive_count": sum(row["polarity"] == "positive" for row in cases),
        "negative_count": sum(row["polarity"] == "negative" for row in cases),
        "audit_authority": AUDIT,
        "retrieval_run": False,
        "model_calls": 0,
    }
    (output / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "lesson_count": len(records), "case_count": len(cases), "source_count": len(sources)}, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    vault_text = os.environ.get("KENNISBANK_VAULT", "").strip()
    if not vault_text:
        raise SystemExit("KENNISBANK_VAULT is required")
    build(args.spec, args.output_dir, Path(vault_text).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
