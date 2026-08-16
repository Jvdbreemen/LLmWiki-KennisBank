---
id: TASK-191
title: Maintenance efficiency: the sweep recomputes what it just computed
status: In Progress
assignee: []
created_date: '2026-08-15 23:30'
updated_date: '2026-08-15 23:30'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by the 2026-08-15 eight-angle /code-review over main...release/v0.31.1,
verified against source before filing. Task IDs 169-179 are reserved by the
open PR #2 branch; this series starts at 180.

Wasted work on the maintenance path, relevant because the sweep shares
one GPU/IO budget with retrieval (TASK-158's accounting):

- _maintenance.py: supersede_pass, recheck_pass and cluster_promote_pass
each reload the full ~1600-file corpus and full vector table per sweep
(~4800 file reads, three vector loads for one snapshot), and
neighbor_counts re-runs the widening KNN probe similar_pairs just ran —
compute the neighbour map once at 0.75 and filter for 0.80.
- _maintenance.py:33 _index_vectors duplicates _index_conn's entire
connect/gate ritual and already missed the unit_norm check the other
copy gained; it also returns vectors by path with no hash check, so an
edited memory is judged with its previous content's embedding (the
get_cached path it replaced verified content hashes).
- _embeddings.py: embed_id()/embed() re-read kennisbank-embed.json per
call (~5000 redundant reads per index build) — memoize with mtime
invalidation.
- kb-session-start.py:136: the status line pays a blocking network probe
(up to 2x100ms on a down Ollama) every session start; a residency marker
written by the warm child would cost a file read.
- kb-state-audit.py:207: value_claims recompiles the same per-key regexes
for each of ~1700 files; precompile once.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Sweep passes share one corpus snapshot and one neighbour map per run
- [ ] #2 _index_vectors reuses _index_conn and verifies content hashes before serving a vector
- [ ] #3 Config reads memoized; index build performs O(1) config reads
- [ ] #4 Session-start residency check reads a marker, not the network
- [ ] #5 state-audit precompiles per-key patterns once
<!-- AC:END -->
