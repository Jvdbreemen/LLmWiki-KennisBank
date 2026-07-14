---
id: TASK-27.13
title: Atlas - Wordcloud-lens (concept-belang via links + gebruik)
status: Done
assignee: []
created_date: '2026-07-12 16:29'
updated_date: '2026-07-12 16:34'
labels:
  - visualization
  - atlas
  - lens
  - wordcloud
dependencies: []
parent_task_id: TASK-27
priority: medium
ordinal: 42000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Een wordcloud/tag-cloud-lens die het belang van kennis in de vault visueel maakt. Belang = hoeveel naar een artikel/concept gelinkt is (graph degree) gecombineerd met hoe vaak het benut wordt (kb-usage warmth). Grotere/prominentere termen = belangrijker.

Databron: sidecar /graph (degree per node) + kb-usage warmth (join op stem). MVP: labels = artikel-namen/community-namen; grootte ∝ genormaliseerde (degree + warmth); kleur per community; klik → inspect-drawer (hergebruik /doc).

Bewust MVP-eerst: simpele flex-tag-cloud (geen d3-cloud) om dep/freeze-risico te vermijden; spiraal-packing als latere upgrade.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De wordcloud toont termen met grootte ge-encodeerd op (degree + warmth), datagedreven en herleidbaar tot de sidecar-data
- [ ] #2 Klik op een term opent het bijbehorende artikel in de inspect-drawer
- [ ] #3 Kleur per community-cluster; leesbaar in dark-mode; geen console-errors
- [ ] #4 Fail-open: lege/ontbrekende data toont nette lege staat
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Wordcloud-lens afgerond (commit c1cb7ca, branch feat/atlas-sidecar). Sidecar: /graph-nodes dragen nu warmth (join kb-usage op file-stem; 50 warme nodes op de echte vault; regressietest test_graph_joins_usage_warmth). Frontend: dependency-lichte flex-tag-cloud (geen layout-lib, bewust na de mermaid/hljs-freezes), font-grootte sqrt-geschaald 12-52px op gewicht = degree + 1.5·warmth, top 150 termen, kleur per community, klik → inspect-drawer (/doc). Live geverifieerd: 88 termen, grootste = otgw-firmware-project (deg 24 + warmth 6), community-kleuren, klik op 'git-worktrees-workflow' opent het artikel. Alle 4 AC gehaald. 25 sidecar-tests groen, tsc schoon, vite build groen. Latere upgrade mogelijk: d3-cloud spiraal-packing; index.md eventueel filteren (hoge degree = ruis).
<!-- SECTION:FINAL_SUMMARY:END -->
