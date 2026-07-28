#!/usr/bin/env python3
"""kb-eval-gen.py - generate CANDIDATE eval questions for human curation (TASK-86).

The evidence rule for feature adoption demands eval sets of at least 100
questions per layer. Hand-writing those from scratch does not happen in
practice (north star: automate over manual discipline), so this generator
proposes candidates and the human curates — "system proposes, human decides".

Two layers of generation:

1. Deterministic (default): per document, questions derived from the title,
   tags and first heading. No model involved; two runs over the same vault
   produce byte-identical drafts. This layer carries the bulk of the volume.
2. Optional local-LLM paraphrases (``--llm``): one reworded question per
   document via the _llm router, labeled ``type: paraphrase``. Fail-soft —
   an unreachable provider skips the layer, it never fails the run.

SAFETY: output goes to ``kb-eval-set.draft.json`` / ``kb-memory-eval-set.draft.json``
(in <vault>/06-claude by default). The live sets are NEVER written; moving
curated entries into them is deliberately a human act. ``write_draft`` refuses
any path that does not end in ``.draft.json``.

Question types follow the harness conventions: ``single-hop`` / ``keyword`` /
``paraphrase`` for wiki; the memory layer uses the memory_type itself
(feit/voorkeur/procedure/beslissing), matching the existing memory eval set.

Scope mirrors build-kb-index._collect: wiki = every ``02-wiki/**/*.md`` except
index/log; memory = only ``status: current`` (a question whose target recall
refuses to serve can never hit, and would poison the metrics as a fake miss).

Exit: 0 = drafts written (count on stdout), 1 = nothing to generate.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

WIKI_SKIP = {"index.md", "log.md"}
MEMORY_TYPES = ("feit", "voorkeur", "procedure", "beslissing")

# Vraagsjablonen per memory_type: de vraag die je aan de agent zou stellen
# als je dit fragment nodig had. Bewust kort en natuurlijk, geen quiz-toon.
_MEMORY_TEMPLATES = {
    "feit": "Wat is er vastgelegd over {t}?",
    "voorkeur": "Welke voorkeur geldt er rond {t}?",
    "procedure": "Hoe pak ik {t} aan?",
    "beslissing": "Wat is er besloten over {t}?",
}

_HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")


def _clean_title(fm: dict, path: Path) -> str:
    """Titel uit frontmatter, of afgeleid uit de bestandsnaam (datum-prefix eraf)."""
    title = str(fm.get("title", "")).strip().strip("'\"")
    if title:
        return title
    stem = _DATE_PREFIX_RE.sub("", path.stem)
    return stem.replace("-", " ").strip()


def _tags_of(fm: dict) -> list:
    tags = fm.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.strip("[]").split(",") if t.strip()]
    return [str(t).strip() for t in tags if str(t).strip()]


def wiki_candidates(path: Path, fm: dict, body: str) -> list:
    """Deterministische kandidaat-vragen voor één wiki-artikel."""
    stem = path.stem
    title = _clean_title(fm, path)
    if not title:
        return []
    out = [{"q": f"Wat weet ik over {title}?", "expect": [stem], "type": "single-hop"}]
    tags = _tags_of(fm)
    if tags:
        # Keyword-vraag: terse zoektermen zoals je ze in een prompt zou tikken.
        terms = " ".join(dict.fromkeys(tags[:3] + [title]))
        out.append({"q": terms, "expect": [stem], "type": "keyword"})
    else:
        m = _HEADING_RE.search(body)
        if m and m.group(1).strip():
            out.append({"q": f"{m.group(1).strip()} bij {title} — hoe zit dat?",
                        "expect": [stem], "type": "single-hop"})
    return out


def memory_candidates(path: Path, fm: dict, body: str) -> list:
    """Deterministische kandidaat-vraag voor één memory-fragment (status current)."""
    if str(fm.get("status", "")).strip() != "current":
        return []
    stem = path.stem
    title = _clean_title(fm, path)
    if not title:
        return []
    mtype = str(fm.get("memory_type", fm.get("type", ""))).strip()
    if mtype not in MEMORY_TYPES:
        mtype = "feit"
    return [{"q": _MEMORY_TEMPLATES[mtype].format(t=title), "expect": [stem],
             "type": mtype}]


def _paraphrase(title: str, snippet: str) -> str:
    """Eén LLM-parafrasevraag; lege string bij elke fout (fail-soft)."""
    try:
        import _llm
        prompt = (
            "Formuleer precies één natuurlijke vraag (één zin, Nederlands) die "
            f"iemand aan een assistent zou stellen als hij dit nodig had, ZONDER de "
            f"titel letterlijk te herhalen.\nTitel: {title}\nFragment: {snippet}\n"
            "Antwoord met alleen de vraag, geen toelichting.")
        out = _llm.generate(prompt, timeout=60.0)
        if out:
            q = str(out).strip().splitlines()[0].strip().strip('"')
            if q.endswith("?") and 10 <= len(q) <= 200:
                return q
    except Exception:
        pass
    return ""


def generate(vault: Path, layer: str, llm: bool = False) -> list:
    """Genereer kandidaat-entries voor één laag, deterministisch gesorteerd op pad."""
    src = vault / ("02-wiki" if layer == "wiki" else "09-memory")
    if not src.exists():
        return []
    entries = []
    seen_q = set()
    for f in sorted(src.glob("**/*.md")):
        if layer == "wiki" and f.name in WIKI_SKIP:
            continue
        try:
            fm, body = parse_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        cands = (wiki_candidates(f, fm, body) if layer == "wiki"
                 else memory_candidates(f, fm, body))
        if llm and cands:
            title = _clean_title(fm, f)
            q = _paraphrase(title, body.strip().replace("\n", " ")[:400])
            if q:
                cands.append({"q": q, "expect": [f.stem], "type": "paraphrase"})
        for c in cands:
            if c["q"] not in seen_q:
                seen_q.add(c["q"])
                entries.append(c)
    return entries


def draft_path(out_dir: Path, layer: str) -> Path:
    name = "kb-eval-set.draft.json" if layer == "wiki" else "kb-memory-eval-set.draft.json"
    return out_dir / name


def write_draft(path: Path, entries: list) -> None:
    """Schrijf een draft. Weigert elk pad dat niet op .draft.json eindigt —
    de live sets zijn mensendomein en worden hier per constructie nooit geraakt."""
    if not path.name.endswith(".draft.json"):
        raise ValueError(f"weiger te schrijven naar niet-draft pad: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="genereer kandidaat-eval-vragen (drafts) voor menselijke curatie")
    parser.add_argument("--layer", choices=("wiki", "memory", "both"), default="both")
    parser.add_argument("--out-dir", default=None,
                        help="doelmap voor drafts (default: <vault>/06-claude)")
    parser.add_argument("--llm", action="store_true",
                        help="voeg per doc één lokale-LLM-parafrasevraag toe (fail-soft)")
    args = parser.parse_args()

    vault = vault_root()
    out_dir = Path(args.out_dir) if args.out_dir else vault / "06-claude"
    layers = ("wiki", "memory") if args.layer == "both" else (args.layer,)

    total = 0
    for layer in layers:
        entries = generate(vault, layer, llm=args.llm)
        if not entries:
            print(f"kb-eval-gen [{layer}]: geen kandidaten (map leeg of ontbreekt)")
            continue
        p = draft_path(out_dir, layer)
        write_draft(p, entries)
        total += len(entries)
        print(f"kb-eval-gen [{layer}]: {len(entries)} kandidaten -> {p}")
    if total:
        print("Curatie: verplaats goedgekeurde entries handmatig naar de echte sets "
              "(kb-eval-set.json / kb-memory-eval-set.json); doel >=100 per laag.")
    return 0 if total else 1


if __name__ == "__main__":
    sys.exit(main())
