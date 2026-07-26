#!/usr/bin/env python3
"""graph-link-layer.py - deterministische edge-laag over de kennisgraaf.

LLM-extractie gebeurt per chunk, en een subagent kan alleen edges leggen tussen
bestanden die hij zelf ziet. Bij 1185 memories in chunks van 75 is een edge
tussen memory #3 en memory #900 - of tussen een memory en een wiki-artikel -
principieel onmogelijk. Het resultaat is een graaf met een goed verbonden
wiki-kern en honderden losse eilanden eromheen.

Dit script repareert dat met structuur die al in de vault ligt, zonder een
enkele LLM-aanroep:

1. DOCUMENTNODES. Per bronbestand een node `doc:<vault-relatief pad>`, met een
   `contains`-edge naar elke concept-node uit dat bestand. Daarmee verdwijnt
   isolatie per constructie: een concept hangt altijd minstens aan zijn eigen
   document.

2. DOC-DOC-EDGES uit drie deterministische bronnen, elk met een eigen relatie
   zodat de herkomst van een edge herleidbaar blijft:
   - `same_session`: documenten met dezelfde `source_session` in de frontmatter;
   - `references`: een `[[wikilink]]` in de tekst die naar een ander bestand wijst;
   - `shares_tag`: documenten die een zeldzame tag delen.

Ster in plaats van kliek: bij een groep van n documenten (sessie of tag) worden
n-1 edges gelegd naar een vaste representant, niet n*(n-1)/2 onderling. Dat
geeft dezelfde samenhang tegen lineaire kosten; een kliek van 50 memories uit
een sessie zou 1225 edges opleveren die niets extra's zeggen.

Zeldzame tags alleen: een tag die tientallen documenten deelt is een categorie,
geen verband. Boven TAG_MAX_DOCS levert de tag geen edges.

Idempotent: nodes en edges krijgen deterministische ids en bestaande ids worden
overgeslagen, dus een tweede run verandert niets.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

#: Boven dit aantal documenten is een tag een categorie, geen verband.
TAG_MAX_DOCS = 25

#: Documentnode-prefix. Bewust met dubbele punt: concept-ids uit de extractie
#: bestaan uit [a-z0-9_], dus een botsing is uitgesloten.
DOC_PREFIX = "doc:"

_WIKILINK_RE = re.compile(r"\[\[([^\[\]|#]+)")


def doc_id(rel_path: str) -> str:
    return DOC_PREFIX + str(rel_path).replace("\\", "/")


def _norm(rel_path) -> str:
    return str(rel_path or "").replace("\\", "/")


def _title_of(meta: dict, rel_path: str) -> str:
    title = str(meta.get("title") or "").strip() if isinstance(meta, dict) else ""
    return title or Path(rel_path).stem


def read_documents(graph: dict, vault: Path, read_fn=None) -> dict:
    """Verzamel per bronbestand: titel, frontmatter en wikilink-targets.

    Alleen bestanden die de graaf al noemt; dit script voegt geen corpus toe,
    het verbindt wat er is.
    """
    read = read_fn or (lambda p: (vault / p).read_text(encoding="utf-8", errors="replace"))
    docs: dict[str, dict] = {}
    for node in graph.get("nodes", []):
        rel = _norm(node.get("source_file"))
        if not rel or rel.startswith(DOC_PREFIX):
            continue
        if rel in docs:
            continue
        try:
            text = read(rel)
        except OSError:
            continue
        meta, body = parse_frontmatter(text)
        meta = meta if isinstance(meta, dict) else {}
        tags = meta.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.strip("[]").split(",") if t.strip()]
        docs[rel] = {
            "title": _title_of(meta, rel),
            "session": str(meta.get("source_session") or "").strip(),
            "tags": [str(t).strip().lower() for t in tags if str(t).strip()],
            "links": [str(t).strip() for t in _WIKILINK_RE.findall(body or text)],
        }
    return docs


def _stem_index(docs: dict) -> dict:
    """stem -> vault-relatief pad, voor het oplossen van [[wikilinks]]."""
    index: dict[str, str] = {}
    for rel in docs:
        index.setdefault(Path(rel).stem, rel)
    return index


def _star(members: list) -> list:
    """Ster-edges binnen een groep: elk lid naar de eerste (deterministisch)."""
    ordered = sorted(members)
    hub = ordered[0]
    return [(hub, m) for m in ordered[1:]]


def build_layer(graph: dict, docs: dict) -> tuple[list, list, dict]:
    """Geef (nieuwe nodes, nieuwe edges, statistiek) terug. Muteert niets."""
    existing_nodes = {n.get("id") for n in graph.get("nodes", [])}
    existing_edges = {(l.get("source"), l.get("target"), l.get("relation"))
                      for l in graph.get("links", [])}

    new_nodes, new_edges = [], []
    stats = defaultdict(int)

    for rel, info in sorted(docs.items()):
        nid = doc_id(rel)
        if nid not in existing_nodes:
            new_nodes.append({
                "id": nid, "label": info["title"], "file_type": "document",
                "source_file": rel, "source_location": None, "source_url": None,
                "captured_at": None, "author": None, "contributor": None,
            })
            existing_nodes.add(nid)
            stats["doc_nodes"] += 1

    def add_edge(src, tgt, relation, confidence, score):
        if src == tgt:
            return
        key = (src, tgt, relation)
        if key in existing_edges or (tgt, src, relation) in existing_edges:
            return
        existing_edges.add(key)
        new_edges.append({
            "source": src, "target": tgt, "relation": relation,
            "confidence": confidence, "confidence_score": score,
            "source_file": None, "source_location": None, "weight": 1.0,
        })
        stats[relation] += 1

    # 1) contains: elk concept aan zijn document.
    for node in graph.get("nodes", []):
        rel = _norm(node.get("source_file"))
        if not rel or rel not in docs:
            continue
        add_edge(doc_id(rel), node.get("id"), "contains", "EXTRACTED", 1.0)

    # 2a) same_session: de frontmatter noemt de herkomst expliciet.
    per_session: dict[str, list] = defaultdict(list)
    for rel, info in docs.items():
        if info["session"]:
            per_session[info["session"]].append(rel)
    for members in per_session.values():
        if len(members) < 2:
            continue
        for a, b in _star(members):
            add_edge(doc_id(a), doc_id(b), "same_session", "EXTRACTED", 1.0)

    # 2b) references: een wikilink is een expliciete verwijzing.
    stems = _stem_index(docs)
    for rel, info in docs.items():
        for target in info["links"]:
            stem = target.replace("\\", "/").rsplit("/", 1)[-1]
            if stem.endswith(".md"):
                stem = stem[:-3]
            other = stems.get(stem)
            if other and other != rel:
                add_edge(doc_id(rel), doc_id(other), "references", "EXTRACTED", 1.0)

    # 2c) shares_tag: alleen zeldzame tags; een brede tag is een categorie.
    per_tag: dict[str, list] = defaultdict(list)
    for rel, info in docs.items():
        for tag in set(info["tags"]):
            per_tag[tag].append(rel)
    for tag, members in per_tag.items():
        if not 2 <= len(members) <= TAG_MAX_DOCS:
            if len(members) > TAG_MAX_DOCS:
                stats["tags_te_breed"] += 1
            continue
        for a, b in _star(members):
            add_edge(doc_id(a), doc_id(b), "shares_tag", "INFERRED", 0.65)

    return new_nodes, new_edges, dict(stats)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", default=None,
                        help="pad naar graph.json (default <vault>/graphify-out/graph.json)")
    parser.add_argument("--dry-run", action="store_true", help="rapporteer alleen")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="machine-leesbare uitvoer")
    args = parser.parse_args()

    vault = vault_root()
    graph_path = Path(args.graph) if args.graph else vault / "graphify-out" / "graph.json"
    if not graph_path.exists():
        print(f"geen graph.json op {graph_path}", file=sys.stderr)
        return 1

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    docs = read_documents(graph, vault)
    new_nodes, new_edges, stats = build_layer(graph, docs)

    if not args.dry_run and (new_nodes or new_edges):
        backup = graph_path.with_suffix(".pre-linklayer.json")
        if not backup.exists():
            backup.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
        graph["nodes"].extend(new_nodes)
        graph["links"].extend(new_edges)
        graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2),
                              encoding="utf-8")

    result = {"documenten": len(docs), "nieuwe_nodes": len(new_nodes),
              "nieuwe_edges": len(new_edges), **stats}
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        verb = "zou toevoegen" if args.dry_run else "toegevoegd"
        print(f"{len(docs)} documenten | {verb}: {len(new_nodes)} documentnodes, "
              f"{len(new_edges)} edges")
        for key in ("contains", "same_session", "references", "shares_tag"):
            if stats.get(key):
                print(f"  {key}: {stats[key]}")
        if stats.get("tags_te_breed"):
            print(f"  tags overgeslagen (> {TAG_MAX_DOCS} documenten): "
                  f"{stats['tags_te_breed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
