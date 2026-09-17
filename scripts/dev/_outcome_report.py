#!/usr/bin/env python3
"""Join exposures and weak outcomes as an association-only aggregate."""
from __future__ import annotations

from collections import defaultdict


def correlate(exposures, outcomes) -> dict:
    states = {(row.get("session_id"), row.get("task_id")): str(row.get("state") or "unknown")
              for row in outcomes or []}
    groups = defaultdict(lambda: defaultdict(int))
    items = defaultdict(lambda: defaultdict(int))
    for exposure in exposures or []:
        key = (exposure.get("session_id"), exposure.get("task_id"))
        state = states.get(key, "unknown")
        layer = str(exposure.get("layer") or "unknown")
        item_id = str(exposure.get("item_id") or "unknown")
        groups[layer][state] += 1
        items[(layer, item_id)][state] += 1
    def normalise(mapping):
        def key_text(key):
            return ":".join(str(part) for part in key) if isinstance(key, tuple) else str(key)
        return {key_text(key): dict(sorted(value.items())) for key, value in sorted(
            mapping.items(), key=lambda item: key_text(item[0]))}
    return {"by_layer": normalise(groups), "by_item": normalise(items),
            "attribution_scope": "association_only",
            "limitations": ["exposure is not use", "use is not helpfulness",
                            "session outcome is not item causality"]}
