"""TASK-27.2 sidecar: /provenance.

Contract (ADR-0004): kb-lint-style provenance coverage over the wiki, rendered
as an overlay on the Graph lens (27.9). A wiki article counts as sourced when
it carries a herkomst wikilink ([[raw-sessie-...]] or [[05-bronnen/...]]).
"""
from pathlib import Path

from fastapi.testclient import TestClient

from atlas.sidecar.app import create_app


def _prov(vault: Path) -> dict:
    return TestClient(create_app(vault)).get("/provenance").json()


def test_provenance_coverage_and_unsourced_list(vault_factory):
    wiki = [
        {"stem": "sourced", "body": "# Sourced\n\nZie [[raw-sessie-2026-07-01-x]]."},
        {"stem": "from-bron", "body": "# Bron\n\n[[05-bronnen/handboek]]"},
        {"stem": "orphan", "body": "# Orphan\n\nGeen herkomst hier."},
    ]
    body = _prov(vault_factory(wiki=wiki))

    assert body["status"] == "ok"
    assert body["coverage"] == {"sourced": 2, "unsourced": 1, "total": 3}

    unsourced = {u["path"]: u["reason"] for u in body["unsourced"]}
    assert set(unsourced) == {"02-wiki/orphan.md"}
    assert unsourced["02-wiki/orphan.md"]


def test_provenance_fail_open_without_wiki(tmp_path: Path):
    body = _prov(tmp_path)
    assert body["status"] == "empty"
    assert body["coverage"] == {"sourced": 0, "unsourced": 0, "total": 0}
