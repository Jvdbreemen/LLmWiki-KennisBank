#!/usr/bin/env python3
"""
auto-crosslink.py -- voeg automatisch backlinks toe aan wiki-artikelen
op basis van de kennisgraaf (graphify-out/graph.json).

Gebruik:
    python3 auto-crosslink.py wiki-artikel-1.md wiki-artikel-2.md
    python3 auto-crosslink.py --dry-run wiki-artikel-1.md

Paden zijn relatief aan de vault of absoluut.
Met --dry-run wordt alleen getoond wat er zou veranderen; er wordt niets geschreven.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

# --- configuratie -----------------------------------------------------------

VAULT_ROOT = vault_root()
GRAPH_PATH = VAULT_ROOT / "graphify-out" / "graph.json"
WIKI_DIR_PREFIX = "02-wiki/"
MIN_CONFIDENCE = 0.75
MAX_NEW_LINKS = 5
# Auto-gegenereerde meta-files: nooit zinvolle "Zie ook"-targets. De index
# referenceert elk artikel, wat anders een [[index]]-backlink op alles oplevert.
EXCLUDE_TARGET_STEMS = {"index", "log"}

# ---------------------------------------------------------------------------


def load_graph(path: Path) -> tuple[dict, dict, list]:
    """Laad graph.json, geef (node_map, links) terug."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    node_map = {n["id"]: n for n in data["nodes"]}
    links = data["links"]
    return node_map, links


def normalize_path(raw: str) -> str:
    """Zet een pad (relatief of absoluut) om naar vault-relatief pad."""
    p = Path(raw).resolve()
    try:
        # as_posix() geeft altijd forward slashes, ongeacht het OS (Windows
        # levert anders backslashes). graph.json node source_file gebruikt altijd
        # "/", dus zonder dit faalt de node-matching op Windows. Idempotent.
        return p.relative_to(VAULT_ROOT.resolve()).as_posix()
    except ValueError:
        return Path(raw).as_posix()


def existing_stems(content: str) -> set[str]:
    """Geef alle [[stem]] of [[stem|...]] waarden terug die al in content staan."""
    return set(re.findall(r"\[\[([^\]|#]+)", content))


def find_section_insert(lines: list[str]) -> tuple[int, int]:
    """
    Zoek de ## Verbanden sectie.
    Geeft (verbanden_start_lno, insert_lno) terug:
      - verbanden_start_lno: regelindex van de ## Verbanden header (-1 als afwezig)
      - insert_lno: regelindex waar nieuwe links ingevoegd worden
    Als ## Verbanden ontbreekt: maak aan voor ## Sessie-herkomst of aan het einde.
    """
    verbanden_idx = -1
    sessie_idx = -1
    for i, line in enumerate(lines):
        stripped = line.rstrip()
        if re.match(r"^## Verbanden\s*$", stripped):
            verbanden_idx = i
        if re.match(r"^## Sessie-herkomst\s*$", stripped):
            sessie_idx = i

    if verbanden_idx != -1:
        # Zoek het einde van de sectie: volgende ## header of EOF
        insert = verbanden_idx + 1
        # Sla bestaande bullets over, zodat nieuwe achteraan de sectie komen
        while insert < len(lines):
            stripped = lines[insert].rstrip()
            if re.match(r"^##\s", stripped):
                break
            insert += 1
        # Stap terug over lege regels zodat we direct na de laatste bullet zitten
        # maar behoud een lege regel als scheidingsteken naar de volgende sectie
        return verbanden_idx, insert

    # Geen ## Verbanden: bepaal waar we hem aanmaken
    if sessie_idx != -1:
        create_at = sessie_idx
    else:
        create_at = len(lines)

    return -1, create_at


def process_file(filepath: Path, node_map: dict, links: list, dry_run: bool = False) -> None:
    rel_path = normalize_path(str(filepath))

    # Nodes die bij dit bestand horen
    own_nodes = {
        nid
        for nid, n in node_map.items()
        if n.get("source_file") == rel_path
    }

    if not own_nodes:
        print(f"{filepath.name}: geen nodes gevonden in graph.json")
        return

    # Verzamel cross-file kandidaten
    candidates: list[tuple[float, str, str]] = []  # (score, target_stem, relation)
    seen_targets: set[str] = set()

    for link in links:
        src, tgt = link["source"], link["target"]
        if src not in own_nodes and tgt not in own_nodes:
            continue

        score = link.get("confidence_score", 0.0)
        if score < MIN_CONFIDENCE:
            continue

        other_id = tgt if src in own_nodes else src
        other_node = node_map.get(other_id)
        if not other_node:
            continue

        other_file = other_node.get("source_file", "")
        if not other_file.startswith(WIKI_DIR_PREFIX):
            continue
        if other_file == rel_path:
            continue

        # Stem = bestandsnaam zonder .md
        stem = Path(other_file).stem
        if stem in EXCLUDE_TARGET_STEMS:
            continue
        relation = link.get("relation", "zie_ook")

        # Per stem de hoogste score bewaren
        if stem not in seen_targets:
            seen_targets.add(stem)
            candidates.append((score, stem, relation))
        else:
            # Vervang als hogere score
            for i, (s, st, r) in enumerate(candidates):
                if st == stem and score > s:
                    candidates[i] = (score, stem, relation)
                    break

    # Sorteer op score descending, max MAX_NEW_LINKS
    candidates.sort(key=lambda x: x[0], reverse=True)
    candidates = candidates[:MAX_NEW_LINKS]

    if not candidates:
        print(f"{filepath.name}: geen nieuwe backlinks")
        return

    # Lees bestand
    content = filepath.read_text(encoding="utf-8")
    already = existing_stems(content)

    new_links = [
        (score, stem, relation)
        for score, stem, relation in candidates
        if stem not in already
    ]

    if not new_links:
        print(f"{filepath.name}: geen nieuwe backlinks")
        return

    # Bouw nieuwe regels op
    new_lines_to_add = [
        f"- Zie ook: [[{stem}]] -- {relation}\n"
        for _, stem, relation in new_links
    ]

    lines = content.splitlines(keepends=True)
    verbanden_idx, insert_idx = find_section_insert(lines)

    if verbanden_idx == -1:
        # Maak ## Verbanden sectie aan
        block: list[str] = []
        # Zorg voor lege regel voor de sectie (als insert_idx > 0)
        if insert_idx > 0 and lines and lines[insert_idx - 1].strip() != "":
            block.append("\n")
        block.append("## Verbanden\n")
        block.extend(new_lines_to_add)
        block.append("\n")
        lines[insert_idx:insert_idx] = block
    else:
        # Voeg toe aan bestaande sectie
        # Zorg voor lege regel voor de nieuwe bullets als de vorige regel niet leeg is
        prefix: list[str] = []
        if insert_idx > 0 and lines[insert_idx - 1].strip() != "":
            prefix = []  # geen extra lege regel binnen sectie
        lines[insert_idx:insert_idx] = prefix + new_lines_to_add

    if dry_run:
        print(f"{filepath.name}: zou {len(new_links)} backlink(s) toevoegen (dry-run, niets geschreven)")
        for line in new_lines_to_add:
            print(f"  + {line.rstrip()}")
        return

    filepath.write_text("".join(lines), encoding="utf-8")
    print(f"{filepath.name}: {len(new_links)} backlink(s) toegevoegd")


def resolve_path(arg: str) -> Path:
    """Zet CLI-argument om naar absoluut Path."""
    p = Path(arg)
    if p.is_absolute():
        return p
    # Probeer relatief aan vault
    candidate = VAULT_ROOT / p
    if candidate.exists():
        return candidate
    # Probeer relatief aan wiki dir
    wiki_candidate = VAULT_ROOT / WIKI_DIR_PREFIX / p
    if wiki_candidate.exists():
        return wiki_candidate
    # Fallback: relatief aan CWD
    return p.resolve()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Voeg automatisch backlinks toe aan wiki-artikelen op basis van graph.json."
    )
    parser.add_argument("files", nargs="+", metavar="bestand", help="wiki-artikel(en), relatief aan de vault of absoluut")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="toon welke backlinks zouden worden toegevoegd zonder iets te schrijven",
    )
    args = parser.parse_args()

    if not GRAPH_PATH.exists():
        print(f"graph.json niet gevonden ({GRAPH_PATH}) — crosslink overgeslagen")
        sys.exit(0)

    node_map, links = load_graph(GRAPH_PATH)

    for arg in args.files:
        fp = resolve_path(arg)
        if not fp.exists():
            print(f"{arg}: bestand niet gevonden ({fp})")
            continue
        process_file(fp, node_map, links, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
