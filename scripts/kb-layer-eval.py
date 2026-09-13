#!/usr/bin/env python3
"""Build a versioned, content-safe source/experience evidence packet."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _layer_eval  # noqa: E402

SCHEMA_VERSION = 1


def _metrics(value: dict, template: dict) -> dict:
    value = dict(value or {})
    return {key: value.get(key, default) for key, default in template.items()}


def build_report(observations: dict) -> dict:
    """Compose aggregates only; prompts, passages, and answer text are dropped."""
    observations = dict(observations or {})
    arms = _layer_eval.validate_arm_coverage(observations.get("arms") or {})
    source = _metrics(observations.get("source"), _layer_eval.source_gate_input_template())
    experience = _metrics(observations.get("experience"),
                          _layer_eval.experience_gate_input_template())
    latency_input = dict(observations.get("latency_ms") or {})
    latency = {route: _layer_eval.latency_summary(latency_input.get(route) or [])
               for route in ("normal", "source", "experience")}
    decisions = _layer_eval.decision_table(source, experience)
    return {
        "schema_version": SCHEMA_VERSION,
        "arms": arms,
        "source": source,
        "experience": experience,
        "latency_ms": latency,
        "decisions": decisions,
        "claims": {
            "outcome_aware_ranking": "research_only_and_disabled",
            "production_routing": "unchanged_until_both_layers_pass",
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", required=True, type=Path,
                        help="aggregate observations JSON; keep raw cases local")
    parser.add_argument("--output", required=True, type=Path,
                        help="evidence packet JSON path")
    args = parser.parse_args(argv)
    observations = json.loads(args.observations.read_text(encoding="utf-8"))
    with _layer_eval.evaluation_environment():
        report = build_report(observations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    os.replace(temporary, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
