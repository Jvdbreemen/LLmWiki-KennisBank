---
id: TASK-146
title: Add volatility (state | event) so the update rule lives in the structure
status: To Do
assignee: []
created_date: '2026-08-12 20:32'
updated_date: '2026-08-12 20:42'
labels:
  - memory
  - schema
  - llm
dependencies: []
references:
  - scripts/_extract.py
  - scripts/_memory.py
  - scripts/_reconcile.py
  - scripts/_maintenance.py
  - docs/superpowers/specs/2026-08-12-self-correcting-memory-layer-design.md
priority: high
ordinal: 140700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`memory_type` (`feit` / `voorkeur` / `procedure` / `beslissing`) is a subject axis. None of those four values says "replace me when the value changes", so every reconcile and supersede decision re-derives volatility from prose. Measured quality of that derivation: 7/20 (`qwen3.5:4b`), 5/20 (`qwen3.5:9b`), 4/20 (`claude -p --model haiku`) against the vault's own supersede decisions.

The `second-brain-audit` skill states the principle this task implements:

> Structure carries this rule, not an instruction. Asking a model, or a person, to remember to update the old entry fails quietly and constantly.

Add one frontmatter field:

```
event     -> is NEVER superseded and NEVER supersedes
state     -> may replace and be replaced
absent or uncertain -> event
```

`event` is the default because destroying history is the irreversible error, and because an absent field then degrades safely — no migration is required for existing memories. Backfill is a later gain, not a precondition.

What it buys today: `supersede_pass` at threshold 0.85 can currently pit two events against each other and close one. Two log entries about different sessions can read as near-duplicates. That becomes structurally impossible rather than a judgment the model has to get right every time.

Touches: `_extract` (one field in the prompt and the parsed schema), `_memory.render` (persist), `_reconcile.reconcile` (event -> always ADD), `_maintenance.supersede_pass` (skip pairs where either side is an event).

Design context: `docs/superpowers/specs/2026-08-12-self-correcting-memory-layer-design.md`, step 2.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 _extract emits volatility per candidate and _memory.render persists it, with an absent value read as event
- [ ] #2 reconcile never returns SUPERSEDE or NOOP when either side is an event
- [ ] #3 supersede_pass skips any pair where either side is an event, proven by a test
- [ ] #4 P3 holds on a dry run over the full corpus: zero events would change status
- [ ] #5 python -m pytest tests -q is green
- [ ] #6 A memory that looks state-shaped but is labelled or defaulted to event is reported by kb-state-audit, so uncertainty is visible rather than permanent
- [ ] #7 Config-shaped claims (model tag, threshold, version, path) are classified as state deterministically, without a model call
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Adversarial review, 2026-08-12. The safe default contradicts the goal, and that has to be handled rather than waved away.

`absent or uncertain -> event` protects history, but an event is NEVER superseded. A weak local model that hesitates therefore labels memories 'never correct me', and the layer goes on rotting with a clean conscience. The user asked for a memory layer that corrects itself; this default systematically opts out of exactly that whenever the model is unsure.

The default itself stays -- destroying history is the irreversible error, and an absent field must degrade safely so 1661 existing memories need no migration. Three mitigations instead, in order of confidence:

1. kb-state-audit reports every memory that LOOKS state-shaped (carries a model tag, threshold, version, path) but is labelled or defaulted to event. Uncertainty becomes visible.
2. Config-shaped claims are classified deterministically, with no model call, because their shape is recognisable by pattern.
3. Volatility is metadata, not history, so a later pass may relabel. Getting it wrong at first costs nothing permanent.

Also note from P1c: with only 11 candidate pairs above 0.85 in the entire corpus, the immediate protective value of this field (stopping supersede_pass from closing an event) is small today. Its value grows with TASK-145, when intake starts delivering the material that reconcile will judge at write time.
<!-- SECTION:NOTES:END -->
