---
id: TASK-88
title: 'Wiki provenance in the index + source-overlap ranking experiment (Spoor C)'
status: In Progress
assignee: []
created_date: '2026-07-28 08:00'
labels:
  - retrieval
  - provenance
  - llm-wiki-adoption
dependencies:
  - TASK-86
ordinal: 96200
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
llm_wiki's strongest relevance idea is classical IR: source-overlap = bibliographic coupling (Kessler 1963), Adamic-Adar = best of 9 link predictors (Liben-Nowell & Kleinberg 2007). Their weights (4.0/3.0/1.5/1.0) are unfounded hand-tuning — adopt the signal, not the numbers.

Blocker: provenance is asymmetric. Memory has `source_session`; wiki articles have nothing structured in the index. Decision: derive wiki sources from the existing provenance links (kb-lint's contract: `[[raw-sessie-*]]` + `[[05-bronnen/...]]`) — no second source of truth in frontmatter. Backfill = `build-kb-index.py --rebuild`.

Phases: C1 `scripts/_provenance.py` `doc_sources(path, layer, fm, body)` (memory: basename(source_session); wiki: provenance wikilinks via kb-lint's own regexes imported by importlib so the parsers cannot drift). C2 `doc_sources(doc_id, source)` table in `_kbindex.ensure_schema` + `upsert(sources=)` + batch `sources_for()`; `search()` returns doc_id; prune cleans the table; readers fail-soft on old dbs (kb-index.db is a disposable cache — no migration needed). C3 doctor.sh provenance-coverage counter. C4 (experiment, knob `rank_coupling` env KB_RANK_COUPLING / kennisbank-embed.json, default 0): bounded multiplicative `coupling_factor` in `_rank.rerank` — 1.05 for shared source with 1 other candidate, 1.10 for >=2, never < 1.0, cap equal to usage warmth; without `sources_fn` the ranking is bit-for-bit identical (regression-locked). Constants pinned via knob-consistency test against CONFIGURATION.md.

Known risk: trivial clustering when a few large sources feed many docs — the 1.10 cap bounds it; the A/B decides.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `_provenance.doc_sources` covers memory + wiki incl. 05-bronnen links, dedup, normalization, Windows paths (tests; shared fixture locks parity with kb-lint)
- [x] #2 `doc_sources` table filled by build-kb-index; `--rebuild` backfills; readers fail-soft without the table
- [x] #3 doctor.sh reports provenance coverage per layer; warns when coupling knob on + coverage 0
- [x] #4 `rerank` without `sources_fn` provably identical (regression lock test)
- [ ] #5 EVIDENCE GATE (blocks enabling): kb-eval A/B on >=100-question sets — MRR/recall@3 not worse, single-hop stable, latency delta negligible; adopt/reject note here
- [ ] #6 EVIDENCE OF IMPROVEMENT: measured A/B on the real vault (rank_coupling off vs on) with numbers here — MRR/recall@3 per type; provenance coverage counts from doctor before/after --rebuild; adopt only on demonstrated benefit, otherwise reject and remove
<!-- AC:END -->

## Evidence (2026-07-29, real vault A/B) — REJECT at current weights

Backfill via `build-kb-index.py --rebuild`: provenance coverage
**wiki 146/147, memory 1147/1147** docs with >=1 source (doctor-verified).

`KB_RANK_COUPLING=1` vs off, live sets (35 wiki / 17 memory):

| variant | wiki @1 | wiki MRR | single-hop @1 | memory (all) |
|---|---|---|---|---|
| coupling OFF | 0.886 | 0.943 | 0.895 | unchanged |
| coupling ON  | **0.829** | **0.914** | **0.789** | unchanged |

Verdict: **REJECT** — the bounded 1.05/1.10 boost already *hurts* wiki@1 on
real data: candidates sharing a session log crowd out the exact answer
(the trivial-clustering risk called out in the plan; llm_wiki's "strongest
idea" fails its first honest measurement). Knob stays OFF (default). The
plumbing (C1-C3) stays: provenance coverage is valuable on its own (doctor,
OKF export) and the regression lock proves zero impact with the knob off.
Revisit only after >=100-set curation AND a redesign (e.g. exclude sources
feeding >X% of docs, or lower boost) — with a new A/B.
