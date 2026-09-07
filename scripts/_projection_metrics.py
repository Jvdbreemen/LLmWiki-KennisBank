#!/usr/bin/env python3
"""Allowlist aggregate projection telemetry before it reaches storage."""
from __future__ import annotations

_FIELDS = ("route", "status", "latency_ms", "count")


def sanitize_metric(value: dict) -> dict:
    """Drop every field that is not part of the content-free metric contract."""
    metric = dict(value or {})
    return {field: metric[field] for field in _FIELDS if field in metric}
