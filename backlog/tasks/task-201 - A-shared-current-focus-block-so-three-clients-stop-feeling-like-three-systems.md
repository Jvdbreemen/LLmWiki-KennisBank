---
id: TASK-201
title: >-
  A shared current_focus block, so three clients stop feeling like three systems
status: To Do
assignee: []
created_date: '2026-08-16 12:00'
updated_date: '2026-08-16 12:00'
labels: []
dependencies:
  - TASK-202
ordinal: 167900
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the Eaves review (docs/research/eaves-memory-architecture.md), adopted
with its scoping deliberately inverted.

Eaves keeps small core-memory blocks that are always in the agent's context
and edited by the agent itself, separate from the searchable archive. Two are
seeded by default: `human` (who you are working with) and `current_focus`
(what is active right now — projects, threads, decisions in flight, next
steps). They are capped at 2000 characters, and there is no read tool for
them, only `core_memory_replace` and `core_memory_append`: the block is
already in the prompt, so reading it would waste a turn.

Eaves scopes those blocks per agent because its agents are different personas
with different jobs. KennisBank has one subject — the vault owner's work — so
the same tier is more valuable *shared*: "what is being worked on right now"
has the same answer for Claude Code, Codex and the Copilot CLI, and each of
them currently rediscovers it from scratch at every session start. A shared
block is both cheaper than per-client blocks and more useful; it is the
mechanism by which the three clients stop behaving like three systems over one
vault.

We already have the manual version. `/checkpoint` writes markdown into
01-raw/checkpoints/ and `kb-checkpoint.py --notify` surfaces pending
checkpoints at SessionStart, in front of the freshness gate. What is missing
is the automatic sibling — and per PRINCIPLES #3, what needs manual discipline
does not happen in practice.

Mechanism, KennisBank-native:

- One small block, hard character cap, one file. Not a layer, not a table.
- Written off the hot path by the existing sweep (never at session start,
  never on the interactive path). Local model only.
- Injected at SessionStart through the existing notification payload — which
  is why this depends on TASK-195, since today a second client inside the
  window would not receive it.
- Replaced wholesale rather than appended, like Eaves' `focus`: a running
  summary that grows is a log, and we already have a log.
- Silent when there is nothing active (principle #4).

Scope discipline is the risk. This must not become a second memory layer: no
retrieval, no index entry, no rank factor. If it needs a rank factor it has
become something else and this task is the wrong home for it. Related but
distinct: TASK-174 (dreaming into wiki drafts) and TASK-178 (autonomous
memory lifecycle) both consolidate *durable* knowledge; this block is
deliberately transient working state that is overwritten, not curated.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 One shared focus block with a hard character cap, written off the interactive path
- [ ] #2 Surfaced at SessionStart to every client, through the existing notification payload
- [ ] #3 Replaced wholesale on each write; no unbounded growth and no history kept in the block
- [ ] #4 Empty or absent yields no output at all, in every client
- [ ] #5 Not indexed, not retrievable, and carries no rank factor
- [ ] #6 The manual /checkpoint path keeps working unchanged alongside it
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->
