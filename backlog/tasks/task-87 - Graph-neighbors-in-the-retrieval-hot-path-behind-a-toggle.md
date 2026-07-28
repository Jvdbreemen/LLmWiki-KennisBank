---
id: TASK-87
title: 'Graph neighbors in the retrieval hot path, behind a toggle (Spoor B, experiment)'
status: In Progress
assignee: []
created_date: '2026-07-28 08:00'
labels:
  - retrieval
  - graph
  - llm-wiki-adoption
dependencies:
  - TASK-86
ordinal: 96100
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-67 already established that the graph is not in the retrieval path: `_rank.one_hop_neighbor` regex-reads wikilinks from article bodies inside the 2.0 s prompt budget (N x read_text), 1 hop, wiki-only, unweighted — while `_kbindex.graph_neighbors()` over `kb-graph.db` is weighted, confidence-scored and sub-millisecond, and is called by nothing in retrieval.

Adopt llm_wiki's architectural choice (graph as a retrieval phase with a hard quota) using our own, better substrate. Research caveat (RAG vs GraphRAG, arXiv 2502.11371): graph expansion helps multi-hop but can hurt single-hop — the dominant regime for personal recall. Hence: experiment behind a toggle, hard quota of one neighbor slot, per-type eval breakdown decides.

Design: `graph_retrieval` toggle in `_settings.py` (default OFF). `expand` stays the master switch; the toggle only selects the source (graph vs legacy). `kb-recall.py`: `_open_graph_ro()` (read-only URI open; NOT `graph_connect()`, which opens read-write and creates dirs) and `graph_neighbor(hits)`: `graph_is_current()` stale => None (fail-open); per wiki hit normalize to vault-relative forward-slash path, `graph_neighbors(conn, rel, limit=5)`, sum confidence over hits; filter wiki-only/non-hit/existing-file; deterministic tie-break; top-1 appended exactly like today (`score: 0.0`, `neighbor: True`). Neighbor flag in `_usage.log_injected` (neighbor_log table, TASK-15 counter lesson) and a doctor.sh check: toggle state, graph freshness, neighbors injected (30d); warn on toggle-on + stale graph.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `graph_retrieval` toggle (default off) manageable via /kennisbank:settings; knob-consistency test green (also README/CONFIGURATION toggle tables — fix the "seven behaviours" drift)
- [x] #2 Toggle off => legacy path identical to today; toggle on => neighbor from kb-graph.db
- [x] #3 Fail-open proven by tests: stale fingerprint, missing db, missing files => no neighbor, no exception
- [x] #4 Neighbor never displaces a direct hit; max 1; `contains` relations excluded
- [x] #5 doctor.sh shows toggle state, graph freshness, neighbors-injected (30d); warns on toggle-on + stale
- [ ] #6 EVIDENCE GATE (blocks default-flip): kb-eval A/B on >=100-question sets — wiki recall@5/MRR not worse, single-hop does not drop, wiki-layer latency p95 delta < 50 ms; adopt/reject note with numbers here
- [ ] #7 Default-flip and legacy removal as separate follow-up PRs, only after #6
- [ ] #8 EVIDENCE OF IMPROVEMENT: measured A/B on the real vault (toggle off vs on) with numbers in this task — recall@k/MRR per type + latency p95 delta; adopt only on demonstrated non-regression + measurable benefit (neighbor relevance or latency win); otherwise reject and remove
<!-- AC:END -->

## Evidence (2026-07-29, real vault A/B)

Graph fresh (3455 nodes / 5943 edges). `kb-eval --json --latency`, live wiki
set (n=35), production expand on:

| variant | recall@1 | @3 | @5 | MRR | p50 | p95 |
|---|---|---|---|---|---|---|
| toggle OFF (legacy scan) | 0.886 | 1.000 | 1.000 | 0.943 | 583 ms | 666 ms |
| toggle ON (kb-graph.db)  | 0.886 | 1.000 | 1.000 | 0.943 | 561 ms | 625 ms |

Verdict: **equal-or-better proven** — recall/MRR identical, single-hop stable
(0.895 both), latency slightly better (graph query replaces N x read_text).
Toggle stays OFF pending the formal >=100-question gate (AC#6), but the
preliminary evidence supports adoption; default-flip PR after curation.
