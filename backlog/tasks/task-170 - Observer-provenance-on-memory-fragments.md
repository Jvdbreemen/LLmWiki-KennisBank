---
id: TASK-170
title: Observer provenance on memory fragments
status: To Do
assignee: []
created_date: '2026-08-15 10:00'
updated_date: '2026-08-15 10:00'
labels: []
dependencies: []
ordinal: 102200
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Adopted from the Honcho review (see docs/research/honcho-memory-architecture.md).

Honcho keys every stored observation by an (observer, observed) pair, so "what
Claude concluded about this project" is a different record from "what Codex
concluded". KennisBank's memory frontmatter records `evidence_basis`, which
answers *what kind of origin* a fragment has — `agent` is one of six values —
but not *which* agent produced it. With Claude Code, Codex and the Copilot CLI
all writing into one vault, `evidence_basis: agent` is now ambiguous at exactly
the moment it starts to matter.

The TASK-160 decomposition made this concrete: all 1732 current memories carry
`evidence_basis: agent`, so `trust_factor` is a constant multiplier that cannot
reorder anything — a single-valued field is no field. `observer` is the
dimension that actually varies across captures today, and TASK-162's
corroboration proposal (count *distinct sessions* asserting a memory) gets
strictly stronger when the sessions can also be distinguished by client.

Proposal: one optional `observer` frontmatter field on memory fragments,
carrying the writing client's identifier (`claude-code`, `codex`, `copilot`,
`human`). Free-text, no enum enforcement beyond normalisation — an unknown
client should record its name, not fail validation.

This is deliberately narrower than Honcho's model. KennisBank has exactly one
*observed* subject (the vault owner's work), so the pair collapses to a single
field. Do not build the second half until a second subject actually exists.

Value: attribution in the memory review UI, per-client recall quality
measurement in the eval harness, and the ability to distrust one client's
extractions without discarding the layer. Cost: one optional field; absent on
every existing fragment, which readers must tolerate.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `observer` is an optional memory frontmatter field, documented in the _memory.py contract docstring
- [ ] #2 memory-sweep records the writing client; unknown or unset yields no field rather than a wrong one
- [ ] #3 Fragments without the field keep parsing and ranking exactly as before (no migration required)
- [ ] #4 The field is queryable from the index for per-client recall measurement
- [ ] #5 Tests cover: present, absent, and unknown-client cases
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->
