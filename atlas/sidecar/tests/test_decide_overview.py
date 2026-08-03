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


def test_approve_is_reflected_on_the_next_overview_fetch(vault_factory):
    """TASK-91 AC#8: /overview is TTL-cached (sources._OVERVIEW_CACHE); a
    decide must invalidate it or the dashboard would serve stale counts for
    up to the TTL after an approve/reject."""
    vault = vault_factory(memories=[{"stem": "u1b", "status": "unverified"}])
    client = _client(vault)
    before = client.get("/overview").json()
    assert before["memory"]["unverified"] == 1
    assert before["memory"].get("active", 0) == 0
    client.post("/memory/decide", json={"stem": "u1b", "decision": "approve"})
    after = client.get("/overview").json()
    assert after["memory"]["unverified"] == 0
    assert after["memory"]["active"] == 1


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
def test_decide_uses_shared_memory_helper_when_deployed(vault_factory, monkeypatch):
    """TASK-89: een vault met gedeployede scripts beslist via _memory.decide
    (gedeelde codepath) — bewijs: het audit-log dat alleen de helper schrijft."""
    import shutil
    vault = vault_factory(memories=[{"stem": "u9", "status": "unverified"}])
    repo_scripts = Path(__file__).resolve().parents[3] / "scripts"
    dest = vault / ".claude" / "scripts"
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("_memory.py", "_common.py", "_frontmatter.py", "_vaultpath.py"):
        shutil.copy(repo_scripts / name, dest / name)
    monkeypatch.setenv("KENNISBANK_VAULT", str(vault))
    r = _client(vault).post("/memory/decide", json={"stem": "u9", "decision": "approve"})
    assert r.status_code == 200
    assert _status_of(vault, "u9") == "current"
    log = vault / ".claude" / "memory-review-log.jsonl"
    assert log.exists(), "gedeelde helper niet gebruikt: geen audit-log geschreven"
    assert '"via": "atlas"' in log.read_text(encoding="utf-8")


def test_decide_falls_back_inline_without_vault_scripts(vault_factory):
    """Oudere vault zonder .claude/scripts: inline-fallback blijft werken en
    schrijft geen audit-log (dat is helper-gedrag)."""
    vault = vault_factory(memories=[{"stem": "u10", "status": "unverified"}])
    r = _client(vault).post("/memory/decide", json={"stem": "u10", "decision": "approve"})
    assert r.status_code == 200
    assert _status_of(vault, "u10") == "current"
    assert not (vault / ".claude" / "memory-review-log.jsonl").exists()
