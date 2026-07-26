#!/usr/bin/env python3
"""graph-provenance-ring.py - sessies vindbaar maken zonder ze te extraheren.

01-raw/sessies telt honderden transcript-logs. Ze semantisch laten extraheren
zou het duurste deel van de vault zijn EN het minst opleveren: de concepten die
eruit komen zijn echo's van de wiki-artikelen die er al uit gedestilleerd zijn.
Die near-duplicate buren verwateren juist het buursignaal waarvoor de graaf
bedoeld is.

Wat je wél wilt weten is herkomst: "welk transcript zit achter dit artikel" en
"in welke sessie deed ik X". Dat is geen semantische vraag maar een
verwijzingsvraag, en het antwoord ligt al in de frontmatter.

Dit script bouwt daarom een RING van bladeren rond de bestaande graaf:

  - één node per sessie, `sessie:<vault-relatief pad>`, met file_type
    "provenance" zodat ranking ze kan onderscheiden van kennis-nodes;
  - een `captured_in`-edge van elk document dat naar die sessie verwijst.

Twee verwijsvormen, allebei deterministisch uit bestaande velden:

  1. `source_session` in memory-frontmatter -- de bestandsnaam van het
     transcript. Die matcht op de basename van `source_path` in de
     sessie-frontmatter. Bewust via source_path en niet via het parsen van
     bestandsnamen: het veld staat er, en een parser op naamconventies breekt
     zodra iemand een sessie hernoemt.
  2. `[[raw-sessie-...]]` wikilinks, zoals wiki-artikelen ze onder
     "Sessie-herkomst" zetten.

Nul LLM-aanroepen, nul extern verkeer.

BLAD, geen knooppunt: er worden GEEN edges tussen sessies onderling gelegd.
Sessies verbinden zou een tweede hub-structuur opleveren naast de
same_session-ster uit graph-link-layer, en die bleek in TASK-71 al te grof om
als buursignaal te dienen.

Idempotent: deterministische ids, bestaande ids worden overgeslagen.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

#: Node-prefix voor een sessie. Net als DOC_PREFIX met een dubbele punt: de
#: concept-ids uit de extractie bestaan uit [a-z0-9_], dus botsen kan niet.
PROV_PREFIX = "sessie:"

#: file_type waarop ranking provenance kan herkennen en anders kan wegen.
PROV_FILE_TYPE = "provenance"

#: Map met de sessielogs, vault-relatief.
SESSIE_DIR = "01-raw/sessies"

DOC_PREFIX = "doc:"
_WIKILINK_RE = re.compile(r"\[\[([^\[\]|#]+)")


def prov_id(rel_path: str) -> str:
    return PROV_PREFIX + str(rel_path).replace("\\", "/")


def _norm(p) -> str:
    return str(p or "").replace("\\", "/")


def _basename(pad: str) -> str:
    """Bestandsnaam uit een pad dat van Windows OF POSIX kan komen.

    source_path is opgeslagen zoals de importeur hem zag -- op Windows met
    backslashes. Path() op een POSIX-machine ziet die niet als scheidingsteken,
    dus eerst normaliseren.
    """
    return _norm(pad).rsplit("/", 1)[-1]


def read_sessions(vault: Path, read_fn=None) -> dict:
    """Sessies uit 01-raw/sessies: pad -> {titel, transcript, stem, datum}.

    Alleen bestanden met `type: raw-sessie`. Een sessie zonder source_path komt
    er wel in maar zonder transcriptnaam; die kan alleen nog via een wikilink
    gevonden worden, en wordt apart geteld.
    """
    read = read_fn or (lambda p: (vault / p).read_text(encoding="utf-8", errors="replace"))
    mdir = vault / SESSIE_DIR
    out: dict[str, dict] = {}
    if not mdir.exists():
        return out
    for f in sorted(mdir.glob("*.md")):
        rel = f"{SESSIE_DIR}/{f.name}"
        try:
            meta, _body = parse_frontmatter(read(rel))
        except OSError:
            continue
        meta = meta if isinstance(meta, dict) else {}
        if str(meta.get("type") or "").strip() != "raw-sessie":
            continue
        out[rel] = {
            "titel": str(meta.get("title") or "").strip() or f.stem,
            "transcript": _basename(str(meta.get("source_path") or "")),
            "stem": f.stem,
            "datum": str(meta.get("date") or "").strip(),
        }
    return out


def read_referrers(graph: dict, vault: Path, read_fn=None) -> dict:
    """Documenten uit de graaf met hun verwijzingen naar sessies.

    Per vault-relatief pad: de source_session uit de frontmatter en de
    [[wikilink]]-stems uit de tekst. Alleen bestanden die de graaf al kent --
    dit script voegt geen corpus toe, het legt herkomst vast.
    """
    read = read_fn or (lambda p: (vault / p).read_text(encoding="utf-8", errors="replace"))
    docs: dict[str, dict] = {}
    for node in graph.get("nodes", []):
        rel = _norm(node.get("source_file"))
        if not rel or rel in docs or rel.startswith(SESSIE_DIR):
            continue
        try:
            text = read(rel)
        except OSError:
            continue
        meta, body = parse_frontmatter(text)
        meta = meta if isinstance(meta, dict) else {}
        docs[rel] = {
            "session": _basename(str(meta.get("source_session") or "").strip()),
            "links": {str(t).strip() for t in _WIKILINK_RE.findall(body or text)},
        }
    return docs


def build_ring(graph: dict, sessies: dict, docs: dict,
               include_unreferenced: bool = False) -> tuple[list, list, dict]:
    """Bouw de provenance-nodes en hun edges. Geeft (nodes, edges, rapport).

    ALLEEN SESSIES MET EEN VERWIJZING, standaard. Gemeten op een echte vault:
    van 772 sessies wordt er naar 48 verwezen; de overige 724 zou dit script als
    losse bladeren toevoegen. Dat is geen ring maar ruis -- en het zou de
    isolatie-winst van graph-link-layer (437 -> 2 geisoleerde nodes) in een klap
    ongedaan maken.

    De ongekoppelde sessies verdwijnen niet stilzwijgend: ze staan geteld in het
    rapport, met voorbeelden. Wie ze toch in de graaf wil, zet
    include_unreferenced aan; de kosten staan dan in hetzelfde rapport.
    """
    bestaand_ids = {n.get("id") for n in graph.get("nodes", [])}
    bestaande_edges = {
        (e.get("source"), e.get("target"), e.get("relation"))
        for e in (graph.get("links") or graph.get("edges") or [])
    }
    per_transcript: dict[str, str] = {}
    per_stem: dict[str, str] = {}
    for rel, s in sessies.items():
        if s["transcript"]:
            per_transcript.setdefault(s["transcript"], rel)
        per_stem.setdefault(s["stem"], rel)

    nieuwe_edges = []
    verbonden: set[str] = set()

    def add_edge(bron_rel: str, sessie_rel: str) -> None:
        src, tgt = DOC_PREFIX + bron_rel, prov_id(sessie_rel)
        sleutel = (src, tgt, "captured_in")
        if sleutel in bestaande_edges:
            return
        bestaande_edges.add(sleutel)
        nieuwe_edges.append({
            "source": src,
            "target": tgt,
            "relation": "captured_in",
            "confidence": "EXTRACTED",
            "confidence_score": 1.0,
        })
        verbonden.add(sessie_rel)

    via_session, via_link = 0, 0
    for rel, d in sorted(docs.items()):
        doel = per_transcript.get(d["session"]) if d["session"] else None
        if doel:
            voor = len(nieuwe_edges)
            add_edge(rel, doel)
            via_session += len(nieuwe_edges) - voor
        for stem in sorted(d["links"]):
            doel = per_stem.get(stem)
            if doel:
                voor = len(nieuwe_edges)
                add_edge(rel, doel)
                via_link += len(nieuwe_edges) - voor

    zonder_transcript = sorted(r for r, s in sessies.items() if not s["transcript"])
    ongekoppeld = sorted(set(sessies) - verbonden)

    # Nodes PAS hier, nu bekend is welke sessies daadwerkelijk hangen.
    opnemen = set(sessies) if include_unreferenced else verbonden
    nieuwe_nodes = []
    for rel in sorted(opnemen):
        nid = prov_id(rel)
        if nid in bestaand_ids:
            continue
        bestaand_ids.add(nid)
        nieuwe_nodes.append({
            "id": nid,
            "label": sessies[rel]["titel"],
            "source_file": rel,
            "file_type": PROV_FILE_TYPE,
            "community": None,
        })

    rapport = {
        "sessies": len(sessies),
        "nodes_toegevoegd": len(nieuwe_nodes),
        "edges_toegevoegd": len(nieuwe_edges),
        "edges_via_source_session": via_session,
        "edges_via_wikilink": via_link,
        "sessies_zonder_source_path": len(zonder_transcript),
        "sessies_zonder_enige_verwijzing": len(ongekoppeld),
        # Bewust de eerste paar bij naam: "62 sessies ongekoppeld" is een getal
        # waar niemand iets mee doet, een voorbeeld maakt het onderzoekbaar.
        "voorbeeld_ongekoppeld": ongekoppeld[:5],
    }
    return nieuwe_nodes, nieuwe_edges, rapport


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", default=None,
                        help="pad naar graph.json (default <vault>/graphify-out/graph.json)")
    parser.add_argument("--dry-run", action="store_true",
                        help="alleen rapporteren, niets schrijven")
    parser.add_argument("--include-unreferenced", action="store_true",
                        help="ook sessies zonder enige verwijzing als losse node "
                             "opnemen (standaard uit: dat zijn bladeren zonder tak)")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    vault = vault_root()
    graph_path = Path(args.graph) if args.graph else vault / "graphify-out" / "graph.json"
    if not graph_path.exists():
        msg = {"status": "geen-graaf", "path": str(graph_path)}
        print(json.dumps(msg) if args.as_json else f"geen graph.json op {graph_path}")
        return 0

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    sessies = read_sessions(vault)
    docs = read_referrers(graph, vault)
    nodes, edges, rapport = build_ring(graph, sessies, docs,
                                      include_unreferenced=args.include_unreferenced)

    if not args.dry_run and (nodes or edges):
        # Back-up voor het schrijven, zodat de vorige topologie vergelijkbaar
        # blijft -- dezelfde afspraak als graph-link-layer.
        backup = graph_path.with_suffix(".pre-provenance.json")
        if not backup.exists():
            backup.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
        graph.setdefault("nodes", []).extend(nodes)
        sleutel = "links" if "links" in graph else "edges"
        graph.setdefault(sleutel, []).extend(edges)
        graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    rapport["geschreven"] = bool(not args.dry_run and (nodes or edges))

    if args.as_json:
        print(json.dumps(rapport, ensure_ascii=False))
    else:
        print(f"provenance-ring: {rapport['nodes_toegevoegd']} sessie-nodes, "
              f"{rapport['edges_toegevoegd']} edges "
              f"({rapport['edges_via_source_session']} via source_session, "
              f"{rapport['edges_via_wikilink']} via wikilink)")
        print(f"  sessies totaal: {rapport['sessies']}, "
              f"zonder source_path: {rapport['sessies_zonder_source_path']}, "
              f"zonder enige verwijzing: {rapport['sessies_zonder_enige_verwijzing']}")
        if rapport["voorbeeld_ongekoppeld"]:
            print("  voorbeeld ongekoppeld: "
                  + ", ".join(Path(p).name for p in rapport["voorbeeld_ongekoppeld"]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # fail-open, zoals de andere graaf-scripts
        print(f"provenance-ring: overgeslagen ({exc})", file=sys.stderr)
        sys.exit(0)
