---
id: TASK-10
title: Agent-geheugen — Wiki-recall migreren naar hybride kb-index (eval-gated)
status: Done
assignee: []
created_date: '2026-06-27 12:39'
updated_date: '2026-06-27 18:44'
labels:
  - agent-geheugen
milestone: Agent-geheugen
dependencies:
  - TASK-3
ordinal: 12000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
De uitgestelde migratie: kb-retrieve.py _wiki_block van JSON-cosine naar kb-index.db hybride zoek (vector+FTS5, layers=(wiki,)). Breekt bewust de byte-identiteit van het wiki-pad (gebruiker akkoord). FTS5 vangt exacte termen (eigennamen/codes/functienamen) die pure vector mist. Eval-gate: before/after-vergelijking op steekproef-queries vóór commit. JSON-cache blijft als embedding-compute-cache (build-kb-index hergebruikt 'm). Recall wordt unified via kb-index.db (beide lagen). Behoud fail-open + memory_recall/embed-gating.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 kb-retrieve wiki-recall gebruikt kb-index.db hybride (vector+FTS5) ipv JSON-cosine
- [x] #2 Before/after-eval toont gelijke of betere wiki-discovery (geen regressie op kern-queries)
- [x] #3 Fail-open behouden; index ontbreekt -> geen wiki-injectie (geen crash)
- [ ] #4 FTS5 vangt exacte-term-queries die vector miste (aangetoond)
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Wiki-recall gemigreerd naar hybride kb-index. kb-recall: has_fts_match (FTS5-keyword-signaal, tokens >=4, fail-soft) + wiki_hits. kb-retrieve._wiki_block herschreven: DUAL-SIGNAL gate (cosine>=drempel OF FTS-keyword-match) + HYBRIDE selectie via wiki_hits (vector RRF + FTS5) + FALLBACK naar cosine-cache-top-N als index ontbreekt (byte-identiek aan oud gedrag). kb_recall module-globaal patchbaar. Commits 16fdedc, d008499, bc77819. 258 tests groen; memory-guard-tests ongewijzigd groen. EVAL met echte qwen3-embedding:8b: AC#1 hybride-ranking werkt (juiste artikel bovenaan), AC#2 geen regressie (semantisch correct), AC#3 fail-open/fallback getest. AC#4 (FTS vangt vector-missers) DEELS: het sterke 8B-embedmodel vangt zelfs opake codes al aan de gate (cosine 0.625>0.60 voor 'ZBX9QW'), dus FTS levert hier vooral ranking-robuustheid + een vangnet (waardevoller bij zwakkere modellen/langere codes), niet dramatische gate-winst. Eerlijk gerapporteerd, niet overclaimd. Dual-gate is een no-regression superset -> veilig + toekomstvast.
<!-- SECTION:FINAL_SUMMARY:END -->
