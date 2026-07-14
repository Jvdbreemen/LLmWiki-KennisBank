"""TASK-27.18: the /memory/decide write path and the /overview health lens.

decide is Atlas's single deliberate write: it flips the frontmatter status of
one *unverified* 09-memory fragment to current (approve) or retracted
(reject). Everything else must be rejected loudly.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from atlas.sidecar import sources
from atlas.sidecar.app import create_app


def _client(vault: Path) -> TestClient:
    return TestClient(create_app(vault))


def _status_of(vault: Path, stem: str) -> str:
    text = (vault / "09-memory" / f"{stem}.md").read_text(encoding="utf-8")
    return sources._parse_frontmatter(text).get("status", "")


def test_approve_promotes_unverified_to_current(vault_factory):
    vault = vault_factory(memories=[{"stem": "u1", "status": "unverified"}])
    r = _client(vault).post("/memory/decide", json={"stem": "u1", "decision": "approve"})
    assert r.status_code == 200
    assert r.json()["new_status"] == "current"
    assert _status_of(vault, "u1") == "current"


def test_reject_retracts_unverified(vault_factory):
    vault = vault_factory(memories=[{"stem": "u2", "status": "unverified"}])
    r = _client(vault).post("/memory/decide", json={"stem": "u2", "decision": "reject"})
    assert r.status_code == 200
    assert _status_of(vault, "u2") == "retracted"


def test_decide_only_touches_the_status_line(vault_factory):
    vault = vault_factory(memories=[
        {"stem": "u3", "status": "unverified", "importance": 4, "body": "inhoud blijft"}])
    before = (vault / "09-memory" / "u3.md").read_text(encoding="utf-8")
    _client(vault).post("/memory/decide", json={"stem": "u3", "decision": "approve"})
    after = (vault / "09-memory" / "u3.md").read_text(encoding="utf-8")
    assert after == before.replace("status: unverified", "status: current")


def test_decide_rejects_non_unverified(vault_factory):
    vault = vault_factory(memories=[{"stem": "c1", "status": "current"}])
    r = _client(vault).post("/memory/decide", json={"stem": "c1", "decision": "approve"})
    assert r.status_code == 409
    assert _status_of(vault, "c1") == "current"


def test_decide_rejects_unknown_stem_and_bad_decision(vault_factory):
    vault = vault_factory(memories=[{"stem": "u4", "status": "unverified"}])
    c = _client(vault)
    assert c.post("/memory/decide", json={"stem": "nope", "decision": "approve"}).status_code == 404
    assert c.post("/memory/decide", json={"stem": "u4", "decision": "delete"}).status_code == 400


def test_decide_rejects_path_traversal(vault_factory):
    vault = vault_factory(memories=[{"stem": "u5", "status": "unverified"}])
    c = _client(vault)
    for stem in ("../02-wiki/x", "a/b", "..\\evil"):
        assert c.post("/memory/decide", json={"stem": stem, "decision": "approve"}).status_code == 400


def test_overview_aggregates_all_stores(vault_factory):
    vault = vault_factory(
        docs=[
            {"path": "02-wiki/a.md", "layer": "wiki", "status": "actief", "title": "A"},
            {"path": "02-wiki/b.md", "layer": "wiki", "status": "concept", "title": "B"},
        ],
        memories=[
            {"stem": "m1", "status": "current"},
            {"stem": "m2", "status": "unverified"},
        ],
        wiki=[
            {"stem": "a", "body": "---\nstatus: actief\n---\n# A\nBron: x"},
            {"stem": "b", "body": "---\nstatus: concept\n---\n# B"},
        ],
    )
    (vault / "00-inbox").mkdir()
    (vault / "00-inbox" / "todo.txt").write_text("x", encoding="utf-8")
    (vault / "01-raw" / "sessies").mkdir(parents=True)
    (vault / "01-raw" / "sessies" / "raw-1.md").write_text("x", encoding="utf-8")

    body = _client(vault).get("/overview").json()
    assert body["status"] == "ok"
    assert body["wiki"]["total"] == 2
    assert body["wiki"]["by_status"] == {"actief": 1, "concept": 1}
    assert body["memory"]["active"] == 1
    assert body["memory"]["unverified"] == 1
    assert body["raw"]["sessies"] == 1
    assert body["inbox_waiting"] == 1
    assert body["provenance"]["total"] == 2


def test_overview_fail_open_on_empty_vault(tmp_path: Path):
    body = _client(tmp_path).get("/overview").json()
    assert body["status"] == "ok"
    assert body["wiki"]["total"] == 0
    assert body["inbox_waiting"] == 0


def test_supersede_chain_normalises_wikilink_refs_and_flags_missing(vault_factory):
    memories = [
        {"stem": "old", "status": "superseded", "superseded_by": ["[[new]]"]},
        {"stem": "new", "status": "superseded", "superseded_by": ["[[gone]]"]},
    ]
    r = sources.build_memory_health(vault_factory(memories=memories))
    chain = r["supersede_chains"][0]
    assert chain["chain"] == ["old", "new", "gone"]
    assert chain["missing"] == ["gone"]
