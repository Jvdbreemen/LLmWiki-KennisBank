---
id: TASK-8
title: Agent-geheugen — Cross-memory onderhoud v2 (supersede/cluster/hercontrole)
status: Done
assignee: []
created_date: '2026-06-27 11:24'
updated_date: '2026-06-27 18:05'
labels:
  - agent-geheugen
milestone: Agent-geheugen
dependencies:
  - TASK-5.2
ordinal: 10000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Uit het ontwerp (spec component 7), bewust LICHT in fase 4b v1 (alleen deterministische expire-pass gebouwd). V2 voegt toe: (1) SUPERSEDE - een nieuwe current die een bestaande current tegenspreekt -> oude status superseded + superseded_by-link (LLM-oordeel of high-cosine + judge); (2) CLUSTER - markeer gerelateerde current memories als promotie-kandidaat voor /wiki; (3) 2e-VERDEDIGINGSLINIE - hercontroleer recent gepromote current memories, kan alsnog retracten/superseden. Allemaal via de mockbare _judge/_llm-seams; deterministische plumbing unit-getest. Draait in de sweep (memory-sweep.py) als extra onderhoudspas, off hot path.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Cross-memory onderhoud v2 afgerond. _maintenance.py: deterministische primitieven (current_items/similar_pairs/neighbor_counts) + _memory.set_status (robuuste frontmatter-mutatie) + drie passes via mockbare seams: supersede_pass (nieuwer spreekt ouder tegen -> ouder superseded + superseded_by-link, fail-safe), recheck_pass (dedicated judge_recheck, FAIL-SAFE-TO-KEEP: retract alleen bij expliciete noise=true), cluster_promote_pass (promote_candidate-vlag voor /wiki). Bedraad in memory-sweep run_sweep ná capture+expire, achter onvoorwaardelijke reachability-gate, elke pass fail-soft. Commits 588c852, 9ae94c0, 9310846, bdb86ae + CRITICAL-fix 7435757. 250 tests groen. Whole-branch review (sonnet) ving een CRITICAL data-integriteit-bug (recheck retracte op _judge's model-down 'unverified' + reachability-probe gegate op todo -> stille mass-retract); gefixt met judge_recheck fail-safe-to-keep + onvoorwaardelijke gate + model-down-regressietest. E2E-bewezen met echte modellen: supersede (oud JSON-cache -> superseded door nieuw sqlite-vec). Beschermt #1 (geen foute recall) + houdt de pool vers.
<!-- SECTION:FINAL_SUMMARY:END -->
