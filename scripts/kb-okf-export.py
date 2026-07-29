#!/usr/bin/env python3
"""kb-okf-export.py - render the vault as an OKF v0.2 bundle (TASK-92).

OKF (Open Knowledge Format, GoogleCloudPlatform/knowledge-catalog, Apache-2.0
spec) is a vendor-neutral interchange format: markdown + YAML frontmatter,
`type` as the only required key. Adoption decision (owner-approved): OKF as an
EXPORT — a rendered view of the vault — never as internal storage.
Bi-temporality (valid_from/valid_until) has no OKF equivalent and the vault
lives on wikilinks+Obsidian; converting at export time costs nothing,
converting internally would degrade both.

The E1 principle applies: views are rendered deterministically, never
prompted. Two runs over an unchanged vault produce byte-identical output
(no run timestamps, sorted iteration, content-derived fields only).

Trust mapping (the 1:1 fit that motivated adoption):
    no verified key            <- memory status unverified  (+ status: draft)
    verified by process:*      <- judge-promoted current    (machine-confirmed)
    verified by human:*        <- review-log approve        (human-reviewed)
    status: deprecated         <- retracted/superseded/expired
    generated: {by, at}        <- model_id (+ prompt_version) from TASK-90 E5
    sources: [{id, resource}]  <- _provenance.doc_sources (TASK-88 C1)
    stale_after                <- expires frontmatter

Spec conformance (v0.2 par. 11): every non-reserved .md carries parseable
frontmatter with a non-empty `type`; `index.md` has no frontmatter except the
bundle root's `okf_version`; wikilinks become bundle-root-absolute markdown
links (broken targets stay as links and are counted — "consumers MUST
tolerate broken links"). `Attested Computation` (par. 10) is not applicable
to this vault and deliberately absent. Per-claim footnote attribution
(par. 5.1) is out of scope for v1 (needs claim-level provenance).

Exit: 0 = bundle written (summary on stdout), 1 = nothing to export.
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
import _provenance  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

OKF_VERSION = "0.2"
RESERVED = {"index.md", "log.md"}
WIKILINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")

STATUS_MAP = {
    "unverified": "draft",
    "current": "stable",
    "retracted": "deprecated",
    "superseded": "deprecated",
    "expired": "deprecated",
}


def _yaml_str(s: str) -> str:
    s = str(s)
    if not s or any(c in s for c in ":#[]{}'\"\n") or s.strip() != s:
        return "'" + s.replace("'", "''") + "'"
    return s


def _first_sentence(body: str) -> str:
    text = " ".join(body.split())
    for sep in (". ", "? ", "! "):
        i = text.find(sep)
        if 0 < i < 200:
            return text[:i + 1]
    return text[:160]


def collect_docs(vault: Path) -> list:
    """(vault-relatief pad, laag) voor alle te exporteren docs, gesorteerd."""
    out = []
    wiki = vault / "02-wiki"
    if wiki.exists():
        for f in sorted(wiki.glob("**/*.md")):
            if f.name not in RESERVED:
                out.append((f.relative_to(vault).as_posix(), "wiki"))
    mem = vault / "09-memory"
    if mem.exists():
        for f in sorted(mem.glob("**/*.md")):
            out.append((f.relative_to(vault).as_posix(), "memory"))
    return out


def _approvals_from_review_log(vault: Path) -> dict:
    """{stem: iso-ts} van menselijke approves uit het review-audit-log."""
    out: dict = {}
    log = vault / ".claude" / "memory-review-log.jsonl"
    try:
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                if e.get("decision") == "approve" and e.get("stem"):
                    out[e["stem"]] = str(e.get("ts", ""))
            except Exception:
                continue
    except OSError:
        pass
    return out


def convert_links(body: str, stem_map: dict, counter: dict) -> str:
    """[[wikilinks]] -> bundle-root-absolute markdown-links (aanbevolen vorm
    par. 6.1). Onbekende targets worden ook links (consumers MUST tolerate
    broken links) maar geteld in counter['broken']."""
    def repl(m):
        raw = m.group(1)
        target = raw.split("|", 1)[0].split("#", 1)[0].strip()
        alias = raw.split("|", 1)[1].strip() if "|" in raw else target
        stem = target.replace("\\", "/").rsplit("/", 1)[-1]
        if stem.endswith(".md"):
            stem = stem[:-3]
        rel = stem_map.get(stem)
        if rel is None:
            counter["broken"] = counter.get("broken", 0) + 1
            guess = target.replace("\\", "/")
            if not guess.endswith(".md"):
                guess += ".md"
            return f"[{alias}](/{guess.lstrip('/')})"
        return f"[{alias}](/{rel})"
    return WIKILINK_RE.sub(repl, body)


def concept_frontmatter(rel: str, layer: str, fm: dict, body: str,
                        approvals: dict) -> list:
    """OKF-frontmatterregels voor één concept (zonder ---fences)."""
    stem = Path(rel).stem
    if layer == "memory":
        okf_type = f"Memory ({fm.get('memory_type', 'feit')})"
    else:
        okf_type = "Wiki Article"
    raw_type = str(fm.get("type", "")).strip()
    if raw_type and raw_type not in ("memory", "wiki"):
        okf_type = raw_type
    lines = [f"type: {_yaml_str(okf_type)}"]
    title = str(fm.get("title", "")).strip().strip("'\"") or stem.replace("-", " ")
    lines.append(f"title: {_yaml_str(title)}")
    desc = _first_sentence(body)
    if desc:
        lines.append(f"description: {_yaml_str(desc)}")
    tags = fm.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.strip("[]").split(",") if t.strip()]
    if tags:
        lines.append("tags: [" + ", ".join(_yaml_str(t) for t in tags) + "]")

    # lifecycle
    status = STATUS_MAP.get(str(fm.get("status", "")).strip(), "stable")
    if status != "stable":  # stable is de spec-default; niet dubbel opschrijven
        lines.append(f"status: {status}")
    expires = str(fm.get("expires", "")).strip()
    if expires:
        lines.append(f"stale_after: {expires}")

    # trust: generated (producent-provenance, E5) + verified (judge/mens)
    model_id = str(fm.get("model_id", "")).strip()
    gen_at = str(fm.get("updated", fm.get("created", ""))).strip()
    if model_id:
        pv = str(fm.get("prompt_version", "")).strip()
        by = f"{model_id}@p{pv}" if pv else model_id
        lines.append(f"generated: {{ by: {_yaml_str(by)}, at: {_yaml_str(gen_at)} }}")
    verified = []
    if layer == "memory" and str(fm.get("status", "")).strip() == "current":
        verified.append(("process:kb-judge", gen_at))
    if stem in approvals:
        verified.append(("human:owner", approvals[stem]))
    if len(verified) == 1:
        by, at = verified[0]
        lines.append(f"verified: {{ by: {by}, at: {_yaml_str(at)} }}")
    elif verified:
        lines.append("verified:")
        for by, at in verified:
            lines.append(f"  - {{ by: {by}, at: {_yaml_str(at)} }}")

    # provenance (C1): dezelfde sleutels als de coupling-index
    sources = _provenance.doc_sources(Path(rel), layer, fm, body)
    if sources:
        lines.append("sources:")
        for s in sources:
            if s.startswith("05-bronnen/"):
                resource = f"/{s}.md"
            elif s.startswith("raw-sessie-"):
                resource = f"/01-raw/sessies/{s}.md"
            else:
                resource = f"/01-raw/transcripts/{s}"
            lines.append(f"  - {{ id: {_yaml_str(s)}, resource: {_yaml_str(resource)} }}")
    return lines


def render_index(entries: list, is_root: bool) -> str:
    """index.md voor één directory (par. 8): secties met lijstregels;
    frontmatter alleen op de bundle-root (okf_version, par. 12)."""
    lines = []
    if is_root:
        lines += ["---", f'okf_version: "{OKF_VERSION}"', "---", ""]
    lines.append("# Contents")
    lines.append("")
    for title, url, desc in entries:
        suffix = f" - {desc}" if desc else ""
        lines.append(f"* [{title}]({url}){suffix}")
    return "\n".join(lines) + "\n"


def render_log(vault: Path) -> str:
    """log.md uit kb-activity.db-dagtellingen (par. 9); "" als er geen data is.
    Deterministisch: puur een projectie van de database-inhoud."""
    import sqlite3
    db = vault / ".claude" / "kb-activity.db"
    if not db.exists():
        return ""
    try:
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT substr(event_time, 1, 10) AS day, count(*) FROM activity_events "
            "GROUP BY day ORDER BY day DESC LIMIT 90").fetchall()
        conn.close()
    except Exception:
        return ""
    if not rows:
        return ""
    lines = ["# Update Log", ""]
    for day, n in rows:
        lines.append(f"## {day}")
        lines.append(f"* **Update**: {n} recorded activity event(s).")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def export(vault: Path, out_dir: Path) -> dict:
    docs = collect_docs(vault)
    if not docs:
        return {"written": 0, "broken_links": 0, "empty": True}
    stem_map = {Path(rel).stem: rel for rel, _ in docs}
    approvals = _approvals_from_review_log(vault)
    counter: dict = {}
    by_dir: dict = {}
    written = 0
    for rel, layer in docs:
        src = vault / rel
        try:
            fm, body = parse_frontmatter(src.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        fm_lines = concept_frontmatter(rel, layer, fm, body, approvals)
        new_body = convert_links(body.strip(), stem_map, counter)
        content = "---\n" + "\n".join(fm_lines) + "\n---\n\n" + new_body + "\n"
        dest = out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        title = str(fm.get("title", "")).strip().strip("'\"") or Path(rel).stem
        by_dir.setdefault(Path(rel).parent.as_posix(), []).append(
            (title, f"/{rel}", _first_sentence(body)))
        written += 1

    # per-directory index.md + root-index met okf_version
    root_entries = []
    for d in sorted(by_dir):
        entries = sorted(by_dir[d])
        (out_dir / d).mkdir(parents=True, exist_ok=True)
        (out_dir / d / "index.md").write_text(
            render_index(entries, is_root=False), encoding="utf-8")
        root_entries.append((d, f"/{d}/index.md", f"{len(entries)} concept(s)"))
    (out_dir / "index.md").write_text(
        render_index(sorted(root_entries), is_root=True), encoding="utf-8")

    log = render_log(vault)
    if log:
        (out_dir / "log.md").write_text(log, encoding="utf-8")

    return {"written": written, "broken_links": counter.get("broken", 0),
            "dirs": len(by_dir), "empty": False}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="exporteer de vault als OKF v0.2-bundle (gerenderde view)")
    parser.add_argument("--out", default=None,
                        help="doeldirectory (default: <vault>/okf-out)")
    args = parser.parse_args()
    vault = vault_root()
    out_dir = Path(args.out) if args.out else vault / "okf-out"
    r = export(vault, out_dir)
    if r["empty"]:
        print("kb-okf-export: niets te exporteren (geen wiki/memory-docs)")
        return 1
    print(f"kb-okf-export: {r['written']} concepten -> {out_dir} "
          f"({r['dirs']} directories, {r['broken_links']} niet-resolvende links)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
