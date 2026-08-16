---
id: TASK-172
title: Audit whether dead ends survive extraction
status: To Do
assignee: []
created_date: '2026-08-15 11:00'
updated_date: '2026-08-15 11:00'
labels: []
dependencies: []
ordinal: 102500
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the field review (docs/research/agent-memory-field-review-and-strategy.md).

`_extract.py` says: capture lessons learned, bug fixes, decisions, durable facts;
IGNORE smalltalk, intermediate steps and transient status. A dead end — the
approach tried for two hours that did not work — is structurally an intermediate
step that failed. The instruction that filters noise may also filter the single
highest-value class of experience knowledge: the one the Reflexion / SWE-Exp /
Live-SWE-agent line of work is built on, and the one PRINCIPLES.md #5 ("niet twee
keer dezelfde fout") names as the point of the system.

This is a hypothesis, not a finding. An articulate dead end can present as a
"lesson learned" and survive extraction. Settle it by counting before changing
anything.

If the ratio is low, the fix is a prompt change plus a distinct type
(`valkuil` / anti-pattern) so recall can answer "you tried this before and it
failed" as a first-class result instead of hoping it hides inside a fact. A new
memory_type also needs a half-life in _rank.HALF_LIFE_DAYS — an anti-pattern
plausibly ages slower than a fact, since a dead end stays a dead end until the
tooling changes.

EXTRACT_PROMPT_VERSION exists precisely so a prompt change is attributable
afterwards; bump it if the prompt changes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A sample of the real memory layer is classified: fragments encoding what did NOT work versus what does, with the sampling method recorded
- [ ] #2 The measurement is written down whichever way it points
- [ ] #3 If the ratio is low: extractor prompt captures failed approaches, EXTRACT_PROMPT_VERSION bumped
- [ ] #4 If a new memory_type lands: half-life assigned, coerce_memory_type accepts it, retrieval can surface it, tests cover it
- [ ] #5 If the ratio is already healthy: task closed as measured-and-rejected, no prompt change
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->

## Close-out (2026-08-16) — parked

Parked, hypothesis still unmeasured: the extractor prompt at scripts/_extract.py:25 still instructs the model to IGNORE intermediate steps — the exact instruction this task suspects filters out dead ends — and EXTRACT_PROMPT_VERSION is still 2, HALF_LIFE_DAYS still lists only the four original types. No sample of the memory layer has been classified and no ratio recorded anywhere. The rationale lives in docs/research/agent-memory-field-review-and-strategy.md (queued in CHANGELOG Unreleased as the dead-end capture audit) and PRINCIPLES/CLAUDE.md north-star #5; the fix design (valkuil type + half-life + prompt bump) lives only in this task's description, so preserve it on archive. Not do-now: a defensible audit needs a recorded sampling method over the deployed vault's real memory layer, and the conditional fix spans prompt, type coercion, ranking, and tests.

**Evidence:** scripts/_extract.py:25 still reads 'NEGEER smalltalk, tussenstappen en vluchtige status'; scripts/_extract.py:46 EXTRACT_PROMPT_VERSION = 2 (unchanged); scripts/_rank.py:32 HALF_LIFE_DAYS has only feit/voorkeur/procedure/beslissing — no valkuil; 'valkuil|anti-pattern|dead end' matches nothing in scripts/; no audit doc in docs/research/.

**Remaining work (when reopened):** Sample the deployed vault's memory layer, classify fragments encoding what-did-NOT-work vs what-works with the method recorded, write the ratio down; if low, extend the extract prompt to capture failed approaches (bump EXTRACT_PROMPT_VERSION to 3) and add a valkuil/anti-pattern memory_type with its own HALF_LIFE_DAYS entry, coerce_memory_type support, retrieval surfacing, and tests.
