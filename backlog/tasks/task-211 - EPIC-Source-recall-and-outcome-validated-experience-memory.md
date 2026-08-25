---
id: TASK-211
title: >-
  EPIC: Source recall and outcome-validated experience memory
status: To Do
assignee: []
created_date: '2026-08-25 00:00'
updated_date: '2026-08-25 00:00'
labels:
  - epic
  - memory
  - source-recall
  - experience-memory
  - outcome-telemetry
  - evaluation
dependencies:
  - TASK-172
  - TASK-173
  - TASK-175
  - TASK-177
  - TASK-179
ordinal: 175000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Epic: add two deliberately different capabilities to KennisBank:

1. **Source recall**: a local, provenance-first retrieval projection over raw
   transcripts and source material. It is an evidence and reconstruction path,
   not another consolidated memory layer.
2. **Outcome-validated experience memory**: a derived layer that records what
   happened in a task, which approach was tried, what result was observed, and
   what lesson or preventative rule is justified by the evidence.

The current KennisBank index primarily serves wiki and current memory. Raw
source material is preserved and used by focused verification paths, but it is
not yet a general, scoped recall surface. The current retrieval telemetry also
records exposure and some usage, not whether an injected item helped or harmed
the task. The existing L2 scene experiment was rejected on measured grounds;
this epic must not recreate that layer as a blind third vector store.

Target architecture:

    immutable raw sources
        -> rebuildable source-recall index
        -> wiki and memory projections
        -> outcome-linked experience projections
        -> procedure and skill candidates, only after repeated evidence

Source recall and experience recall use separate routes and thresholds. There
is no unified ranking across raw evidence, memory, wiki, and experience until a
dedicated evaluation proves that such a policy is useful. Normal recall keeps
its current behaviour and latency when the new paths are not selected.

Research anchors to read and record in the design:

- Reflexion: feedback plus persistent episodic reflections,
  https://arxiv.org/abs/2303.11366
- ExpeL: extracting reusable knowledge from agent experience,
  https://arxiv.org/abs/2308.10144
- ReasoningBank: success and failure experiences distilled into strategies,
  https://research.google/blog/reasoningbank-enabling-agents-to-learn-from-experience/
- ProjectMem: append-only events, deterministic projections, and advisory
  pre-action warnings, https://arxiv.org/abs/2606.12329
- SWE-Exp: multi-level coding-agent experiences,
  https://arxiv.org/abs/2507.23361
- Memp: repeated experiences becoming procedural abstractions,
  https://arxiv.org/abs/2508.06433
- EverOS: Markdown source truth, SQLite/audit state, and rebuildable vectors,
  https://github.com/EverMind-AI/EverOS/blob/main/docs/how-memory-works.md
- Hindsight and EverMemOS: separating facts, experiences, scenes, and beliefs,
  https://arxiv.org/abs/2512.12818 and https://arxiv.org/abs/2601.02163
- Useful Memories Become Faulty: raw episodic evidence must remain first-class
  and consolidation must be gated,
  https://arxiv.org/abs/2605.12978

Design principles:

- raw sources are immutable evidence; derived indexes are rebuildable;
- every source and experience result has exact provenance;
- `unknown` is a valid outcome and is never silently converted to success or
  failure;
- outcome signals are initially descriptive, not ranking factors;
- source recall is explicit, verification-triggered, or a low-confidence
  fallback, not default prompt injection;
- LLM extraction proposes structured records but cannot invent evidence;
- consolidation is offline, versioned, reversible, and auditable;
- new skills remain human-approved; no autonomous deletion of evidence;
- all core operation remains local-first and fail-open;
- every new retrieval path gets a measured latency and quality gate.

Work breakdown and order:

1. TASK-212: architecture contract, schemas, lifecycle, and invariants.
2. TASK-213: raw-corpus inventory, provenance audit, and golden evaluation
   fixtures.
3. TASK-214: rebuildable raw-source index with exact source locations.
4. TASK-215: source-recall API, scoped routing, and groundcheck integration.
5. TASK-216: persistent injection ledger and weak outcome telemetry; this
   incorporates the open measurement work from TASK-173 and the sensor gap in
   TASK-179.
6. TASK-217: append-only experience event model and derived experience store.
7. TASK-218: evidence-bound experience extraction and offline consolidation;
   TASK-172 supplies the dead-end measurement gate.
8. TASK-219: gated experience recall and advisory failure-prevention checks.
9. TASK-220: paired evaluation, holdout sets, attribution analysis, and
   rollout gates.
10. TASK-221: procedure and skill promotion only after outcome evidence;
    coordinate with TASK-175 and TASK-177.
11. TASK-222: lifecycle maintenance, privacy, setup/doctor, multi-client
    validation, and documentation.

The implementation order is intentionally measurement-first: source recall can
be built as a read-only evidence tool before it enters the hot path, and
experience records can be collected before they influence retrieval.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 All child tasks TASK-212 through TASK-222 exist, have explicit dependencies, and contain testable acceptance criteria
- [ ] #2 The design distinguishes raw source evidence, source-recall projections, wiki/memory, episodes, outcomes, lessons, and procedures
- [ ] #3 Raw source material remains recoverable after every derived-index rebuild, supersession, narrowing, retraction, and failed model run
- [ ] #4 Source recall is additive and gated; normal wiki/memory recall has no new latency or ranking regression when the source route is unused
- [ ] #5 Experience records preserve outcome evidence, provenance, uncertainty, and attribution limits; no unsupported lesson is promoted
- [ ] #6 Outcome telemetry is measured before it is used for ranking, memory promotion, noise marking, or skill evolution
- [ ] #7 A paired evaluation reports source evidence quality, experience usefulness, repeated-failure rate, latency, false warnings, and regressions
- [ ] #8 New skills and autonomous evolution remain owner-approved until their dedicated acceptance gates are met
- [ ] #9 Setup, doctor, rebuild, documentation, and all supported client surfaces describe and validate the new projections
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 TASK-212 through TASK-222 are Done or explicitly Blocked with evidence and owner
- [ ] #2 A design/ADR and research note document the accepted and rejected prior-art patterns
- [ ] #3 Source recall is usable in explicit and verification modes without changing default recall
- [ ] #4 Experience recall is bounded, provenance-labelled, and disabled when evidence or evaluation gates are not met
- [ ] #5 Rebuilds and maintenance are deterministic, local, observable, and reversible
- [ ] #6 The final decision records whether outcome-aware ranking is justified; absence of evidence is not treated as approval
<!-- DOD:END -->

