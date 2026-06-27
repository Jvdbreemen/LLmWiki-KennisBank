---
id: TASK-5.2
title: Agent-geheugen Fase 4b — sweep-orkestratie
status: Done
assignee: []
created_date: '2026-06-27 10:10'
updated_date: '2026-06-27 11:23'
labels:
  - agent-geheugen
milestone: Agent-geheugen
dependencies: []
references:
  - docs/superpowers/plans/2026-06-27-agent-geheugen-fase4b-sweep.md
parent_task_id: TASK-5
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Autonome capture-sweep bovenop de 4a-seams: _sweepstate (.swept-watermark + jsonl-transcript-reader), _sweeputil (chunk lange transcripts + cosine-dedup) + _memory.unique_memory_path (collision-guard), memory-sweep.py orkestrator (extract->chunk->dedup->judge->schrijf met status/evidence_basis=agent/source_session->mark, sweep-breed budget, deterministische expire-pass, heartbeat), sweep-launch.py detached SessionStart-launcher (single-flight lockfile, spawnt sweep detached + daarna build-kb-index, exit 0 fail-open, gegate op memory_capture). Deterministische plumbing unit-getest; alle LLM/embed via mockbare seams.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 .swept-watermark + transcript_text reader (fail-soft)
- [x] #2 chunk lange transcripts + is_duplicate cosine-dedup + unique_memory_path collision-guard
- [x] #3 memory-sweep: extract->dedup->judge->schrijf (status uit verdict, evidence_basis=agent, source_session), mark, budget, expire-pass, heartbeat; gegate op memory_capture
- [x] #4 sweep-launch: single-flight lockfile, detached spawn sweep->index, exit 0 fail-open
- [x] #5 Alle sweep-tests mocken extract/judge/embed (geen echt model)
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fase 4b afgerond. _sweepstate (.swept-watermark + jsonl-reader), _sweeputil (chunk/dedup) + _memory.unique_memory_path, memory-sweep.py orkestrator (extract->dedup->judge->schrijf met status/evidence_basis=agent/source_session->mark, budget, expire-pass, heartbeat), sweep-launch.py detached launcher + lockfile. Commits d80a996, d6242ad, 0a9005f, 3bc2a67 + fix-wave 89e634e + d5adf21. 204 tests groen. Whole-branch review (24 agents): 0 Critical, 2 Important GEFIXT (watermark-burn bij LLM/embed-outage -> upfront chat+embed-probe, niets gemarkeerd bij outage; lockfile stale-reclaim getest) + bug-minors gefixt (expire frontmatter-corruptie -> regex op fm-blok; dedup-skip bij embed-None; lock future-mtime+O_EXCL-first reclaim) + coverage-tests. AC#4 cross-memory: expire (deterministisch) GEDAAN; supersede/cluster/2e-lijn-hercontrole bewust LICHT in v1 -> afgesplitst naar follow-up taak (in het ontwerp, niet gedropt).
<!-- SECTION:FINAL_SUMMARY:END -->
