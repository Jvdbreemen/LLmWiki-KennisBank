---
id: TASK-27.16
title: Atlas - memory-fragmenten als nodes in /graph (opt-in twee-lagen-graaf)
status: Done
assignee: []
created_date: '2026-07-12 20:38'
updated_date: '2026-07-12 20:50'
labels:
  - visualization
  - atlas
  - graph
  - memory
  - sidecar
  - frontend
dependencies: []
parent_task_id: TASK-27
priority: high
ordinal: 45000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Voeg memory-fragmenten (09-memory) als nodes toe aan /graph via een opt-in param (?include_memory=1), naast de bestaande wiki-nodes en de overlay. Memory-nodes dragen hun frontmatter-velden (memory_type, importance, status, valid_from, valid_until, created) + warmth; edges = fragment→doel-artikel uit de memory-links (TASK-27.14). Default /graph blijft wiki-only (snel/schoon; overlay intact). Dit ontsluit in één klap: de valid-tijd-as van de Time-slider (27.5), memory-encoding op de Graph-lens (27.4: kleur=memory_type, rand=status), supersede-overgangen (valid_until), en de satelliet-structuur (design optie 2). Frontend: Graph-lens-toggle 'toon memory-fragmenten (nodes)'. Read-only, fail-open, getest.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 /graph?include_memory=1 voegt memory-nodes toe (kind=memory) met frontmatter-velden + warmth; default blijft wiki-only
- [ ] #2 Edges fragment→doel-artikel uit memory-links; memory-node verbindt met z'n wiki-artikel
- [ ] #3 Graph-lens-toggle toont/verbergt memory-nodes; memory-encoding (kleur=type, rand=status) werkt; valid-tijd-as filtert nu echte memory-vensters
- [ ] #4 Hermetische test: include_memory voegt nodes+edges toe met correcte velden; read-only, fail-open
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Memory-fragmenten als nodes in /graph afgerond (commit ddb7d33). /graph krijgt opt-in ?include_memory=1 dat 09-memory-fragmenten als nodes toevoegt (kind=memory) met frontmatter (memory_type, importance, status, valid_from/valid_until, created) + warmth, en een fragment→artikel-edge each (uit build_memory_links). Default blijft wiki-only (basiskaart + overlay snel/schoon). Graph-lens-toggle 'toon memory-fragmenten (nodes)' herlaadt de graaf met memory erin.

Sluit de terugkerende data-scope-gap (27.4/27.5/27.9): op echte data werken nu memory-encoding (kleur=type, rand=status), de Time-slider valid-tijd-as + supersede-overgangen (48 memory-nodes met valid_until), en de satelliet-structuur (design-optie 2) die vanzelf ontstaat.

AC-dekking: #1 include_memory voegt memory-nodes toe met velden+warmth, default wiki-only ✓; #2 fragment→artikel-edges (rel=entry-point) ✓; #3 toggle toont/verbergt, memory-encoding werkt ✓; #4 hermetische test (memory-node-velden + edge via monkeypatch) + read-only + fail-open ✓. Live: toggle → 937 nodes (95 wiki-kern + 842 memory-halo) met 671 entry-point-edges, rendert als zonnestelsel. 33 sidecar + 22 vitest groen, tsc schoon, build groen.
<!-- SECTION:FINAL_SUMMARY:END -->
