---
id: TASK-5.2
title: Agent-geheugen Fase 4b — sweep-orkestratie
status: In Progress
assignee: []
created_date: '2026-06-27 10:10'
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
- [ ] #1 .swept-watermark + transcript_text reader (fail-soft)
- [ ] #2 chunk lange transcripts + is_duplicate cosine-dedup + unique_memory_path collision-guard
- [ ] #3 memory-sweep: extract->dedup->judge->schrijf (status uit verdict, evidence_basis=agent, source_session), mark, budget, expire-pass, heartbeat; gegate op memory_capture
- [ ] #4 sweep-launch: single-flight lockfile, detached spawn sweep->index, exit 0 fail-open
- [ ] #5 Alle sweep-tests mocken extract/judge/embed (geen echt model)
<!-- AC:END -->
