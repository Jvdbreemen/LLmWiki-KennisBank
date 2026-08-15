---
id: TASK-131
title: Split the hot-path budget into embed, search and rank
status: To Do
assignee: []
created_date: '2026-08-15 11:00'
updated_date: '2026-08-15 11:00'
labels: []
dependencies: []
ordinal: 102600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the field review (docs/research/agent-memory-field-review-and-strategy.md).

Published latency profiles for the field: vector-only retrieval 10-50ms, graph
traversal 50-150ms, multi-strategy 100-600ms, LLM synthesis 800-3000ms.
KennisBank budgets 2.0s for the UserPromptSubmit hook, and the comment in
kb-retrieve.py attributes the cost to the embedding call rather than to search.

If that attribution is right, the entire retrieval and ranking architecture
executes inside the noise of one Ollama round-trip, and every future ranking
refinement optimises a term that does not matter. That would make the next
performance lever a smaller or quantised embed model, or a prompt-embedding
cache — not anything in _rank.py or _kbindex.py.

Cheap to settle: instrument the three phases of the hot path and report the
split. The measurement decides whether performance work is worth doing at all,
so it belongs before, not after, the next optimisation.

Constraint: the instrumentation must not itself cost hot-path time in normal
operation — measure behind a flag or in a bench script, never unconditionally in
the hook.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Embed, search and rank timed separately on a realistic vault, over enough prompts to see spread rather than one sample
- [ ] #2 Result written down as a share of the 2.0s budget, cold and warm model
- [ ] #3 Instrumentation costs nothing on the hot path when not explicitly enabled
- [ ] #4 An explicit conclusion recorded: which phase the next performance work should target, or that none is warranted
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->
