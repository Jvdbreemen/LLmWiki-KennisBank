"""TASK-187: the /overview TTL cache must key on the effective date.

`today` shapes freshness buckets, memory-health ages and the heatmap cutoff;
a cache keyed on vault alone serves one date's payload for another.
"""
from datetime import date
from pathlib import Path

from atlas.sidecar import sources


def _vault_with_article(vault_factory) -> Path:
    return vault_factory(wiki=[{
        "stem": "art",
        "body": "---\ntitle: A\nstatus: actief\nupdated: 2026-08-01\n---\nx\n",
    }])


def test_two_dates_within_ttl_get_distinct_payloads(vault_factory):
    vault = _vault_with_article(vault_factory)
    r1 = sources.build_overview(vault, today=date(2026, 8, 2))
    r2 = sources.build_overview(vault, today=date(2026, 12, 1))
    assert r1["freshness"] == {"d7": 1, "d30": 0, "d90": 0, "older": 0, "unknown": 0}
    assert r2["freshness"] == {"d7": 0, "d30": 0, "d90": 0, "older": 1, "unknown": 0}


def test_same_date_within_ttl_still_hits_the_cache(vault_factory):
    vault = _vault_with_article(vault_factory)
    r1 = sources.build_overview(vault, today=date(2026, 8, 2))
    sources.build_overview(vault, today=date(2026, 12, 1))
    r3 = sources.build_overview(vault, today=date(2026, 8, 2))
    assert r3 is r1  # same cached object: the date key did not break the TTL cache


def test_invalidate_drops_every_date_entry_for_the_vault(vault_factory):
    vault = _vault_with_article(vault_factory)
    r1 = sources.build_overview(vault, today=date(2026, 8, 2))
    sources.build_overview(vault, today=date(2026, 12, 1))
    sources._invalidate_overview_cache(vault)
    assert sources.build_overview(vault, today=date(2026, 8, 2)) is not r1
