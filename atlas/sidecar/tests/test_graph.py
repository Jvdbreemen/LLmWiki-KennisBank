"""TASK-27.2 sidecar: /graph.

Contract (ADR-0004): collapse the graphify graph to file-level wiki/memory
nodes joined on file path with kb-index (layer, status, title) and degree, plus
file-level links. Serves the Graph lens, Time-slider, and Provenance overlay.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from atlas.sidecar.app import create_app

WIKI_A = "02-wiki/alpha.md"
WIKI_B = "02-wiki/beta.md"


def _graph(vault: Path) -> dict:
    return TestClient(create_app(vault)).get("/graph").json()


def test_graph_collapses_fragments_to_file_nodes(vault_factory):
    nodes = [
        {"id": "wiki_alpha", "label": "alpha.md", "source_file": WIKI_A},
        {"id": "wiki_alpha_frag", "label": "a fragment", "source_file": WIKI_A},
        {"id": "wiki_beta", "label": "beta.md", "source_file": WIKI_B},
    ]
    links = [
        # fragment -> file edge collapses to an A<->B file edge
        {"source": "wiki_alpha_frag", "target": "wiki_beta",
         "relation": "references", "weight": 2.0},
        # self-loop within one file is dropped
        {"source": "wiki_alpha", "target": "wiki_alpha_frag",
         "relation": "contains", "weight": 1.0},
    ]
    docs = [
        {"path": WIKI_A, "layer": "wiki", "status": "current", "title": "Alpha"},
        {"path": WIKI_B, "layer": "wiki", "status": "current", "title": "Beta"},
    ]
    vault = vault_factory(nodes=nodes, links=links, docs=docs)

    body = _graph(vault)

    assert body["status"] == "ok"
    ids = {n["id"]: n for n in body["nodes"]}
    assert set(ids) == {WIKI_A, WIKI_B}  # fragment folded into its file
    assert ids[WIKI_A]["kind"] == "wiki"
    assert ids[WIKI_A]["label"] == "alpha.md"
    assert ids[WIKI_A]["layer"] == "wiki"
    assert ids[WIKI_A]["node_status"] == "current"

    # exactly one file-level link A<->B, self-loop dropped
    assert len(body["links"]) == 1
    link = body["links"][0]
    assert {link["source"], link["target"]} == {WIKI_A, WIKI_B}
    assert link["rel"] == "references"

    # degree counts file-level links
    assert ids[WIKI_A]["degree"] == 1
    assert ids[WIKI_B]["degree"] == 1


def test_graph_joins_absolute_docs_path_to_relative_node(vault_factory):
    # kb-index stores absolute OS paths; graphify stores vault-relative POSIX.
    # The join must normalise both to vault-relative before matching.
    nodes = [{"id": "wiki_alpha", "label": "alpha.md", "source_file": WIKI_A}]
    vault = vault_factory(nodes=nodes, links=[], docs=[])
    abs_path = str(vault / "02-wiki" / "alpha.md")  # absolute, OS separators
    import sqlite3

    conn = sqlite3.connect(vault / ".claude" / "kb-index.db")
    conn.execute(
        "INSERT INTO docs (path, layer, status, hash, title, created) "
        "VALUES (?,?,?,?,?,?)",
        (abs_path, "wiki", "current", "h", "Alpha", "2026-01-01"),
    )
    conn.commit()
    conn.close()

    ids = {n["id"]: n for n in _graph(vault)["nodes"]}
    assert ids[WIKI_A]["node_status"] == "current"
    assert ids[WIKI_A]["layer"] == "wiki"


def test_graph_joins_usage_warmth(vault_factory):
    nodes = [{"id": "wiki_alpha", "label": "alpha.md", "source_file": WIKI_A}]
    docs = [{"path": WIKI_A, "layer": "wiki", "status": "current", "title": "Alpha"}]
    vault = vault_factory(nodes=nodes, links=[], docs=docs,
                          usage=[{"stem": "alpha", "used": 7, "last_used": "2026-07-10"}])
    ids = {n["id"]: n for n in _graph(vault)["nodes"]}
    assert ids[WIKI_A]["warmth"] == 7.0


def test_graph_include_memory_adds_typed_nodes(vault_factory, monkeypatch):
    from atlas.sidecar import sources

    nodes = [{"id": "wiki_alpha", "label": "alpha.md", "source_file": WIKI_A}]
    docs = [{"path": WIKI_A, "layer": "wiki", "status": "current", "title": "Alpha"}]
    memories = [{"stem": "m-1", "status": "current", "memory_type": "procedure",
                 "importance": 4, "valid_until": "2026-08-01"}]
    vault = vault_factory(nodes=nodes, links=[], docs=docs, memories=memories)

    # default: wiki-only, no memory nodes
    assert all(n["kind"] == "wiki" for n in sources.build_graph(vault)["nodes"])

    # link m-1 -> the wiki article so an entry-point edge forms
    monkeypatch.setattr(sources, "build_memory_links",
                        lambda v: {"status": "ok", "links": {"m-1": WIKI_A},
                                   "counts": {WIKI_A: 1}, "types": {"m-1": "procedure"}})
    g = sources.build_graph(vault, include_memory=True)
    mem = {n["id"]: n for n in g["nodes"]}.get("09-memory/m-1.md")
    assert mem is not None
    assert mem["kind"] == "memory" and mem["memory_type"] == "procedure"
    assert mem["importance"] == 4 and mem["valid_until"] == "2026-08-01"
    assert any(l["source"] == "09-memory/m-1.md" and l["target"] == WIKI_A
               for l in g["links"])


def test_graph_fail_open_without_stores(tmp_path: Path):
    body = _graph(tmp_path)
    assert body["status"] == "empty"
    assert body["nodes"] == []
    assert body["links"] == []
