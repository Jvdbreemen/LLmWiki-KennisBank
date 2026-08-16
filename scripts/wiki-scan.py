#!/usr/bin/env python3
"""wiki-scan.py - deterministic wiki-candidate proposals for /wiki (TASK-89 D2).

/wiki step 2 (candidate identification) was the last free-form LLM decision
point in the pipeline: four prose criteria, no enum, no script. Precedent for
closing it: /wiki step 4.5 was "a model prompt with an escape hatch" until the
kb-lint gate replaced it. This scanner does the same for step 2, following the
intake-scan/conflict-scan pattern: deterministic candidates in, a closed
``suggested_action`` out, and the human (via the command) stays the authority —
the action is a proposal, deviation requires motivation.

Candidate sources, all deterministic:
  (a) marker    — explicit ``wiki-kandidaat: <onderwerp>`` lines in recent
                  session logs (the /sessielog convention);
  (b) cluster   — memories flagged ``promote_candidate: true`` by the sweep
                  (a cluster of >=2 related current memories by construction);
  (c) recurrent — H2 headings that appear in >=2 distinct session logs within
                  the window (template headings excluded).

Per candidate a find-similar probe supplies ``{path, score, above_threshold}``.
Action mapping (validated against ACTIONS, fail-safe default ``overslaan``):
  above_threshold          -> herschrijf   (article exists: update it)
  marker/cluster/>=2 logs  -> nieuw        (evidence enough for a new article)
  otherwise                -> overslaan    (deterministic conservatism)

Silent-empty guard (TASK-15 lesson): the JSON carries ``scanned_logs`` so the
caller can tell "0 candidates out of 12 logs" (a real outcome) from "0 out of
0" (a configuration problem).

Exit: 0 with JSON on stdout; the JSON has ``empty: true`` when nothing scanned.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

#: Gesloten actieset (memory-sweep-conventie): gevalideerd tegen deze tuple,
#: alles daarbuiten wordt de fail-safe default.
ACTIONS = ("herschrijf", "nieuw", "overslaan")
DEFAULT_ACTION = "overslaan"

MARKER_RE = re.compile(r"wiki-kandidaat:\s*\[?([^\]\n]+?)\]?\s*$", re.IGNORECASE)
H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")

#: Template-koppen die in elk sessielog staan en dus nooit een onderwerp zijn.
GENERIC_HEADINGS = {
    "sessie-herkomst", "verbanden", "kernpunten", "context", "resultaat",
    "samenvatting", "vervolg", "open loops", "geleerd", "nieuwe kennis",
    "beslissingen", "acties", "notities",
}


def _norm_topic(t: str) -> str:
    return " ".join(str(t).strip().strip("'\"").split())


def _log_date(path: Path) -> date:
    """Datum van een sessielog: uit de bestandsnaam, anders mtime."""
    m = DATE_RE.search(path.stem)
    if m:
        try:
            return datetime.fromisoformat(m.group(1)).date()
        except ValueError:
            pass
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).date()
    except OSError:
        return date.today()


def recent_session_logs(vault: Path, days: int) -> list:
    sdir = vault / "01-raw" / "sessies"
    if not sdir.exists():
        return []
    cutoff = date.today() - timedelta(days=max(1, days))
    return sorted(f for f in sdir.glob("*.md") if _log_date(f) >= cutoff)


def marker_candidates(logs: list) -> dict:
    """{genormaliseerd onderwerp: {topic, evidence}} uit expliciete markers."""
    out: dict = {}
    for f in logs:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            m = MARKER_RE.search(line)
            if m:
                topic = _norm_topic(m.group(1))
                if topic:
                    out.setdefault(topic.lower(), {"topic": topic, "evidence": []})
                    out[topic.lower()]["evidence"].append(str(f))
    return out


def cluster_candidates(vault: Path) -> dict:
    """{onderwerp: {topic, evidence}} uit promote_candidate-memories (sweep-cluster)."""
    mdir = vault / "09-memory"
    out: dict = {}
    if not mdir.exists():
        return out
    for f in sorted(mdir.glob("**/*.md")):
        try:
            raw = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "promote_candidate:" not in raw:
            continue
        try:
            fm, _ = parse_frontmatter(raw)
        except Exception:
            continue
        if str(fm.get("promote_candidate", "")).strip().lower() != "true":
            continue
        if str(fm.get("status", "")).strip() != "current":
            continue
        topic = _norm_topic(fm.get("title", "")) or f.stem
        out.setdefault(topic.lower(), {"topic": topic, "evidence": []})
        out[topic.lower()]["evidence"].append(str(f))
    return out


def recurrent_candidates(logs: list) -> dict:
    """H2-koppen die in >=2 verschillende logs voorkomen (template-koppen niet)."""
    seen: dict = {}
    for f in logs:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for h in {_norm_topic(h) for h in H2_RE.findall(text)}:
            if not h or h.lower() in GENERIC_HEADINGS:
                continue
            seen.setdefault(h.lower(), {"topic": h, "evidence": []})
            seen[h.lower()]["evidence"].append(str(f))
    return {k: v for k, v in seen.items() if len(v["evidence"]) >= 2}


def _default_similar_fn(topic: str):
    """find-similar-probe via subprocess; None bij elke fout (fail-soft).
    Off-path tool: één embed per kandidaat is acceptabel; een onbereikbaar
    model degradeert deterministisch — /wiki stap 3.5 hervalideert sowieso."""
    script = Path(__file__).resolve().parent / "find-similar.py"
    try:
        r = subprocess.run(
            [sys.executable, str(script), topic, "--json"],
            capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None
        return json.loads(r.stdout.strip() or "null")
    except Exception:
        return None


def suggest_action(source_kind: str, evidence_count: int, similar) -> "tuple[str, str]":
    """(suggested_action, reason) — gesloten set, fail-safe overslaan.

    ``similar is None`` betekent: probe overgeslagen of gefaald. Een marker/
    cluster stelt dan alsnog "nieuw" voor — /wiki stap 3.5 draait find-similar
    sowieso opnieuw vóór er geschreven wordt, dus dubbel-artikel-risico wordt
    daar gevangen; hier conservatief zwijgen zou expliciete menselijke
    markers stil laten verdampen.
    """
    if similar and similar.get("above_threshold"):
        action, reason = "herschrijf", (
            f"bestaand artikel boven drempel ({similar.get('score', 0):.2f})")
    elif source_kind in ("marker", "cluster") or evidence_count >= 2:
        reason = {
            "marker": "expliciete wiki-kandidaat-marker",
            "cluster": "sweep-cluster van verwante memories",
            "recurrent": f"onderwerp in {evidence_count} sessielogs",
        }.get(source_kind, "voldoende evidence")
        if similar is None:
            reason += "; similar-check onbeschikbaar — stap 3.5 hervalideert"
        action = "nieuw"
    else:
        action, reason = DEFAULT_ACTION, "te weinig evidence voor een nieuw artikel"
    if action not in ACTIONS:  # gesloten set, altijd (memory-sweep-conventie)
        action = DEFAULT_ACTION
    return action, reason


def scan(vault: Path, days: int = 7, topic_filter: str = "",
         similar_fn=_default_similar_fn) -> dict:
    logs = recent_session_logs(vault, days)
    merged: dict = {}
    for kind, cands in (("marker", marker_candidates(logs)),
                        ("cluster", cluster_candidates(vault)),
                        ("recurrent", recurrent_candidates(logs))):
        for key, c in cands.items():
            if key in merged:
                merged[key]["evidence"].extend(
                    e for e in c["evidence"] if e not in merged[key]["evidence"])
                continue  # eerste bron wint als source_kind (marker > cluster > recurrent)
            merged[key] = {"topic": c["topic"], "source_kind": kind,
                           "evidence": list(c["evidence"])}

    flt = topic_filter.strip().lower()
    candidates = []
    for key in sorted(merged):
        c = merged[key]
        if flt and flt not in key:
            continue
        similar = similar_fn(c["topic"]) if similar_fn else None
        action, reason = suggest_action(c["source_kind"], len(c["evidence"]), similar)
        candidates.append({
            "topic": c["topic"],
            "source_kind": c["source_kind"],
            "evidence": c["evidence"],
            "similar": similar,
            "suggested_action": action,
            "reason": reason,
        })
    return {
        "candidates": candidates,
        "total": len(candidates),
        "scanned_logs": len(logs),
        "window_days": days,
        "empty": not logs and not candidates,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="deterministische wiki-kandidaten voor /wiki stap 2")
    parser.add_argument("--days", type=int, default=7,
                        help="venster in dagen voor sessielogs (default 7)")
    parser.add_argument("--topic", default="", help="filter op onderwerp (substring)")
    parser.add_argument("--no-similar", action="store_true",
                        help="sla de find-similar-probe over (sneller; stap 3.5 hervalideert)")
    args = parser.parse_args(argv)
    fn = None if args.no_similar else _default_similar_fn
    result = scan(vault_root(), days=args.days, topic_filter=args.topic,
                  similar_fn=fn)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
