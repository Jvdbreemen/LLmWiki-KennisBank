#!/usr/bin/env python3
"""graph-scope-prune.py - haal niet-actuele geheugen-nodes uit de kennisgraaf.

Graphify bepaalt zijn scope met `.graphifyignore`, en dat werkt op paden.
De geheugenlaag heeft een scope-criterium dat NIET in een pad zit: de
frontmatter-sleutel `status`. Een memory met status `superseded`, `retracted`
of `expired` is bewust afgevoerde kennis; die hoort niet als graafbuur terug
te komen in retrieval. `unverified` is nog niet bevestigd en telt hier ook
niet mee.

Daarom deze na-stap: bouw de graaf zoals gewoonlijk, en snoei daarna de nodes
weg waarvan het bronbestand een 09-memory-artikel is dat niet `current` is.
De extractiekosten van die bestanden zijn daarmee weggegooid (~6% van de
geheugenlaag), maar dat is aanzienlijk simpeler dan de vault vooraf naar een
staging-map kopieren, en de graaf blijft de enige bron van waarheid.

Snoeit ook de edges die daardoor los komen te hangen; een graaf met verwijzingen
naar verdwenen nodes laat consumenten (auto-crosslink, /brug, de Atlas-lenzen)
op onduidelijke manieren falen.

Idempotent: een tweede run op dezelfde graaf verandert niets.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

MEMORY_DIR = "09-memory"
#: Alleen bevestigde, geldige kennis hoort in de graaf.
KEEP_STATUSES = {"current"}


def _status_of(vault: Path, source_file: str) -> str | None:
    """Lees de frontmatter-status van een vault-relatief pad, of None."""
    path = vault / source_file
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    meta, _ = parse_frontmatter(text)
    value = meta.get("status") if isinstance(meta, dict) else None
    return str(value).strip().lower() if value else None


def prune(graph: dict, vault: Path) -> tuple[dict, dict]:
    """Verwijder niet-actuele geheugen-nodes plus hun edges. Geeft (graaf, stats)."""
    drop_ids: set = set()
    dropped_files: set = set()
    missing = 0

    for node in graph.get("nodes", []):
        source = str(node.get("source_file") or "").replace("\\", "/")
        if not source.startswith(MEMORY_DIR + "/"):
            continue
        status = _status_of(vault, source)
        if status is None:
            # Bronbestand weg of onleesbaar: de node verwijst nergens meer naar.
            missing += 1
            drop_ids.add(node.get("id"))
            dropped_files.add(source)
        elif status not in KEEP_STATUSES:
            drop_ids.add(node.get("id"))
            dropped_files.add(source)

    before_nodes = len(graph.get("nodes", []))
    before_links = len(graph.get("links", []))

    graph["nodes"] = [n for n in graph.get("nodes", []) if n.get("id") not in drop_ids]
    graph["links"] = [
        l for l in graph.get("links", [])
        if l.get("source") not in drop_ids and l.get("target") not in drop_ids
    ]

    stats = {
        "nodes_before": before_nodes,
        "nodes_after": len(graph["nodes"]),
        "nodes_pruned": before_nodes - len(graph["nodes"]),
        "links_before": before_links,
        "links_after": len(graph["links"]),
        "links_pruned": before_links - len(graph["links"]),
        "files_pruned": len(dropped_files),
        "files_missing": missing,
    }
    return graph, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", default=None,
                        help="pad naar graph.json (default <vault>/graphify-out/graph.json)")
    parser.add_argument("--dry-run", action="store_true",
                        help="rapporteer alleen; schrijf niets")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="machine-leesbare uitvoer")
    args = parser.parse_args()

    vault = vault_root()
    graph_path = Path(args.graph) if args.graph else vault / "graphify-out" / "graph.json"
    if not graph_path.exists():
        print(f"geen graph.json op {graph_path}", file=sys.stderr)
        return 1

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    graph, stats = prune(graph, vault)

    if not args.dry_run and stats["nodes_pruned"]:
        graph_path.write_text(
            json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.as_json:
        print(json.dumps(stats, ensure_ascii=False))
    else:
        verb = "zou snoeien" if args.dry_run else "gesnoeid"
        print(f"{verb}: {stats['nodes_pruned']} nodes uit {stats['files_pruned']} "
              f"niet-actuele memories, {stats['links_pruned']} edges "
              f"({stats['nodes_after']} nodes / {stats['links_after']} edges over)")
        if stats["files_missing"]:
            print(f"let op: {stats['files_missing']} nodes verwezen naar een "
                  f"verdwenen bronbestand")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
