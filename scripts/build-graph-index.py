#!/usr/bin/env python3
"""build-graph-index.py - laad graphify-out/graph.json in kb-index.db.

Waarom: graph.json is 4,2 MB. Dat per prompt parsen om te weten welke bestanden
aan een treffer grenzen past niet in het hot-path-budget van kb-retrieve (2,0s
inclusief de embed-call). In SQLite met een index op source/target is dezelfde
vraag een lookup.

Draait OFF de hot path, naast build-kb-index.py: SessionStart, of handmatig na
een graphify-run. Idempotent - een tweede run met dezelfde graaf doet niets
behalve opnieuw dezelfde rijen wegschrijven.

Versheid staat los van de embedding-index. is_valid_for() bewaakt het
embedmodel; de graaf krijgt een eigen vingerafdruk (mtime+grootte) in meta.
Een verouderde graaf naast een verse embedding-index levert daardoor GEEN buur
op in plaats van een verkeerde.

Exit: 0 = geladen of niets te doen, 1 = graaf onleesbaar.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _kbindex  # noqa: E402
from _vaultpath import vault_root  # noqa: E402


def graph_json_path() -> Path:
    return vault_root() / "graphify-out" / "graph.json"


def load_graph(path: Path) -> "tuple[list, list]":
    data = json.loads(path.read_text(encoding="utf-8"))
    nodes = data.get("nodes") or []
    # graphify schrijft edges als "links" (node-link-formaat); een enkele
    # tussenvorm gebruikt "edges". Beide accepteren, anders laadt de ene helft
    # van de pijplijn wel en de andere stil niet.
    edges = data.get("links")
    if edges is None:
        edges = data.get("edges") or []
    return nodes, edges


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", default=None,
                        help="pad naar graph.json (default <vault>/graphify-out/graph.json)")
    parser.add_argument("--db", default=None, help="pad naar kb-index.db (voor tests)")
    parser.add_argument("--force", action="store_true",
                        help="herladen ook als de vingerafdruk ongewijzigd is")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    gpath = Path(args.graph) if args.graph else graph_json_path()
    if not gpath.exists():
        # Geen graaf is een geldige toestand: graphify is een externe skill en
        # hoeft niet geinstalleerd te zijn. Niets doen, niet klagen.
        msg = {"status": "geen-graaf", "path": str(gpath)}
        print(json.dumps(msg) if args.as_json else f"geen graph.json op {gpath}; niets te doen")
        return 0

    try:
        conn = _kbindex.connect(args.db) if args.db else _kbindex.connect()
    except Exception as exc:
        print(f"kan de index niet openen: {exc}", file=sys.stderr)
        return 1

    try:
        _kbindex.ensure_graph_schema(conn)
        fp = _kbindex.graph_fingerprint(gpath)
        if not args.force and _kbindex.meta_get(conn, "graph_fingerprint") == fp:
            n, e = _kbindex.graph_count(conn)
            msg = {"status": "ongewijzigd", "nodes": n, "edges": e, "fingerprint": fp}
            print(json.dumps(msg) if args.as_json
                  else f"graaf ongewijzigd ({n} nodes, {e} edges); niets herladen")
            return 0

        try:
            nodes, edges = load_graph(gpath)
        except Exception as exc:
            print(f"graph.json onleesbaar: {exc}", file=sys.stderr)
            return 1

        n, e = _kbindex.replace_graph(conn, nodes, edges)
        # Vingerafdruk PAS na een geslaagde vervanging: bij een crash halverwege
        # blijft de oude afdruk staan, zodat de volgende run opnieuw laadt in
        # plaats van een halve graaf als actueel te beschouwen.
        _kbindex.set_graph_fingerprint(conn, fp)
        msg = {"status": "geladen", "nodes": n, "edges": e, "fingerprint": fp}
        print(json.dumps(msg) if args.as_json
              else f"graaf geladen: {n} nodes, {e} edges")
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
