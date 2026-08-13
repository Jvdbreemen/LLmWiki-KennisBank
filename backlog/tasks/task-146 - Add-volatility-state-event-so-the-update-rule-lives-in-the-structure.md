---
id: TASK-146
title: Add volatility (state | event) so the update rule lives in the structure
status: Done
assignee: []
created_date: '2026-08-12 20:32'
updated_date: '2026-08-13 18:55'
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
- [x] #1 _extract emits volatility per candidate and _memory.render persists it, with an absent value read as event
- [x] #2 reconcile never returns SUPERSEDE or NOOP when either side is an event
- [x] #3 supersede_pass skips any pair where either side is an event, proven by a test
- [x] #4 P3 holds on a dry run over the full corpus: zero events would change status
- [x] #5 python -m pytest tests -q is green
- [x] #6 A memory that looks state-shaped but is labelled or defaulted to event is reported by kb-state-audit, so uncertainty is visible rather than permanent
- [x] #7 Config-shaped claims (model tag, threshold, version, path) are classified as state deterministically, without a model call
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

## Implementation, 2026-08-13

Ordering, decided before writing code, because it is what makes the safe default safe:

1. extract says `state` -> state
2. extract says `event` -> event, **never overridden**
3. absent or garbled -> config-shape check: match -> state, else -> event

The deterministic check is a rescue for the cases where the model hesitated, not a second opinion on a label it did give. That keeps the false-positive surface to "no label AND config-shaped body", which is small and, since TASK-150, reversible.

`coerce_volatility(value, body)` is used on WRITE and on READ. The 1595 existing memories carry no field, so reading them applies the same rule, and `supersede_pass` keeps working on the memories where replacing is right (settings) without ever closing an event.

`render()` coerces rather than raising, unlike `memory_type`: a garbled label must cost the label, never the capture.

## Measured on the live vault, 2026-08-13 (AC#4)

The corpus-wide question is trivially "zero events change status" while no memory carries the field, so that number proves nothing. What discriminates is the pairs that actually reach the pass: nine above 0.85, judged one at a time.

- current memories: 1595. Classified `state` by the config-shape fallback: 23. `event`: 1572.
- **9 of 9 pairs skipped.** Judged individually:
  - 5 pairs are near-duplicate captures of one procedure (supersession workflow, untrusted intent, settings layout, docker vhdx move, esptool flash). Skipping leaves a duplicate in place. Nothing is destroyed; a cleanup is missed.
  - 3 pairs are genuinely different facts that merely read alike: the CI-gate fix, the two drip counters, and — the clearest case — the locations of two DIFFERENT skills at cosine 0.867. Closing either of those would have destroyed a true fact. This is the pair that justifies the field.
  - 1 pair (policy.network_allowed) is a config claim beside a description of its inheritance; state/event, so skipped. Safe.

So on today's corpus the guard prevents three potentially wrong closures and blocks zero correct ones, because the pass had no correct closures among these pairs to begin with — they are duplicates, not contradictions.

**State this plainly:** with 1572 of 1595 memories defaulting to event, `supersede_pass` is effectively inert on the legacy corpus until memories carry labels. That is the designed trade and not a regression to be surprised by later.

## Two bugs the live corpus exposed in the classifier

Both found by running the predicate over real bodies rather than invented ones:

1. `re.IGNORECASE` turned the ALL-CAPS key branch `[A-Z][A-Z0-9_]{2,}` into "any word of three letters or more", so `grid-column: 1 / -1` in a CSS explanation read as a setting. It was the only reason a layout memory classified as state. Fixed with a scoped `(?-i:...)`; the corpus-wide state count fell from 54 to 23, i.e. 31 of 54 were false positives.
2. The copula form was missed: `de standaardwaarde voor 'policy.network_allowed' is 'false'` is unmistakably a setting. Added `is` as a separator, plus tolerance for a closing quote after the key — in prose the key is nearly always quoted, and without that the separator never got its turn.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
`volatility: state | event` is now a frontmatter field, set at write time and applied on read, so the update rule lives in the structure rather than in a model's judgement three times a day.

The ordering is what makes the safe default safe: an explicit label always wins, and the deterministic config-shape check only rescues candidates the extractor left unlabelled. `render()` coerces instead of raising, because a garbled label must cost the label, never the capture.

Measured on the live vault: nine pairs above 0.85, all nine skipped. Three of them are genuinely different facts that read alike — including the locations of two DIFFERENT skills at cosine 0.867 — and closing either would have destroyed a true fact. That pair is the argument for the whole field.

Two classifier bugs surfaced only by running the predicate over real bodies: `re.IGNORECASE` turned the ALL-CAPS branch into "any three-letter word", and Dutch hides booleans inside ordinary words ('off' in "officieel"). 54 state classifications fell to 17 real ones.

AC#6 is carried by kb-state-audit (TASK-149), which reports every memory holding a checkable value that counts as an event — a broader and more useful set than "looks state-shaped", because those are exactly the claims that can never be corrected.

Recorded plainly, because it will otherwise be misread later: with 1572 of 1595 memories defaulting to event, supersede_pass is inert on the legacy corpus until new captures bring labels. That is the designed trade, not a regression.
<!-- SECTION:FINAL_SUMMARY:END -->
