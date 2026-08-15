---
id: TASK-175
title: Promote proven procedures into skills — gated on telemetry
status: To Do
assignee: []
created_date: '2026-08-15 11:00'
updated_date: '2026-08-15 11:00'
labels: []
dependencies: []
ordinal: 102900
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the field review (docs/research/agent-memory-field-review-and-strategy.md).

Memp, SkillWeaver, Agent Workflow Memory, LEGOMem and TokMem converge on one
move: procedures learned from experience should become executable artifacts, not
descriptions retrieved as prose. KennisBank's `memory_type: procedure` stores a
description — when recalled, the agent reads it and re-derives the steps every
time.

The destination already exists (`skills/`, `commands/`) and so does the selection
signal: usage telemetry knows which stems are injected and referenced repeatedly.
A procedure memory recalled and used N times is a skill trying to be written.

A second argument from the baseline: `procedure` is the worst-performing memory
type at recall@1 (0.277 against 0.460 for beslissing, on 411 questions — see
docs/research/recall-baseline-2026-08-13.md). Prose retrieval serves procedures
least well of all four types, which is consistent with the literature's move away
from retrieving procedures as text.

GATE BEFORE BUILDING. Query usage telemetry for procedure-typed memories ranked
by recall frequency. If there is a meaningful head — a handful of procedures
recalled far more than the rest — the promotion path is worth building. If
recalls are uniformly thin, there is nothing to promote and this closes as
measured-and-rejected. Building the machinery first and discovering the
distribution is flat afterwards is the expensive order.

If it proceeds: promotion proposes, the human writes or approves the skill. The
same rule as everywhere else in this vault — the system proposes, the human
merges.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Procedure-typed memories ranked by recall frequency from usage telemetry, distribution reported
- [ ] #2 An explicit go/no-go on whether a meaningful head exists, recorded with the numbers
- [ ] #3 If no-go: closed as measured-and-rejected, nothing built
- [ ] #4 If go: promotion drafts a skill proposal and never writes an active skill without human approval
- [ ] #5 If go: a promoted skill is traceable back to the memory it came from
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->
