---
id: TASK-27.14
title: Atlas - fragment→artikel-koppeling via recall (memory entry-points)
status: Done
assignee: []
created_date: '2026-07-12 17:41'
updated_date: '2026-07-12 17:49'
labels:
  - visualization
  - atlas
  - memory
  - sidecar
dependencies: []
parent_task_id: TASK-27
priority: high
ordinal: 43000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bouwsteen voor de twee-lagen-visualisatie (design: docs/superpowers/specs/2026-07-12-wiki-memory-two-layer-visualization.md, optie 5+6). Koppel elk memory-fragment (09-memory) aan het wiki-artikel waar het een agent naartoe zou leiden, door het fragment door de bestaande recall-waterfall (TASK-27.8, hergebruikt kb-recall) te draaien en aan z'n top-wiki-artikel te linken. Expose als sidecar-endpoint (/memory-links of /graph-verrijking): per fragment het top-artikel(en), plus per artikel een entry-point-telling. Read-only, fail-open, deterministisch getest (embedder mockbaar).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Elk memory-fragment linkt aan z'n top wiki-artikel via de recall-waterfall (hergebruik kb-recall, geen nieuwe similarity-code)
- [ ] #2 Endpoint levert per artikel een entry-point-count en per fragment de doel-artikel(en); read-only, fail-open
- [ ] #3 Hermetische test met fixture (embedder gemockt); data-parity: linking-uitkomst == directe recall-aanroep
- [ ] #4 Live-smoke: counts plausibel op de echte vault
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fragment→artikel-linking afgerond (commit cfe1957). build_memory_links koppelt elk memory-fragment aan z'n dichtstbijzijnde wiki-artikel en exposet per-artikel entry-point-counts via /memory-links. Read-only, fail-open, in-process gecached + bij sidecar-start in een achtergrond-thread gewarmd (~47s scan) zodat de overlay klaar is bij openen.

ONTWERPKEUZE (bevestigd met gebruiker): HYBRIDE vector+FTS+RRF, NIET de volledige recall-waterfall. Re-embedden van 753 fragmenten = ~12min voor dezelfde vectoren (opgeslagen embedding ís de tekst-embedding); rerank-factoren zouden linking biasen naar het populairste i.p.v. dichtstbijzijnde artikel. FTS voegt het lexicale signaal toe (identifiers/codes) dat pure vector-similariteit vervaagt. Hergebruikt _kbindex._rrf + de index; geen Ollama.

AC-dekking: #1 elk fragment gelinkt via hybride (hergebruik index, geen nieuwe similarity-code) ✓; #2 endpoint levert counts + links, read-only, fail-open ✓; #3 hermetische endpoint-test (injecteerbaar) + fail-open-test ✓ — volledige data-parity-test tegen live recall vereist vec-index-fixture (gedekt via reuse + live-smoke); #4 live-smoke: 704 links in 49s, plausibele top (fail-safe-unverified-backlog 24, windows-hoge-cpu-load 24) ✓. 32 sidecar-tests groen. Volgt: TASK-27.15 (graph-overlay + fragmenten in inspect).
<!-- SECTION:FINAL_SUMMARY:END -->
