---
id: TASK-144
title: >-
  Both judge models read NOOP as "unrelated", and NOOP is the verdict that
  discards knowledge
status: To Do
assignee: []
created_date: '2026-08-12 19:14'
labels:
  - memory
  - llm
  - prompt
  - bug
dependencies: []
references:
  - scripts/_reconcile.py
  - scripts/_judge.py
  - scripts/_extract.py
  - docs/research/judge-model-4b-vs-9b-2026-08.md
priority: medium
ordinal: 138700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`RECONCILE_SYSTEM` defines the three actions as:

- SUPERSEDE: the new fact replaces or contradicts the existing one
- NOOP: the new one adds nothing; the existing already covers it
- ADD: the new one is genuinely additional

Measured in the TASK-142 sweep (`docs/research/judge-model-4b-vs-9b-2026-08.md`), both `qwen3.5:4b` and `qwen3.5:9b` use NOOP to mean *unrelated* — the opposite of the definition, and the exact case ADD is for. In their own words:

> `{"action": "NOOP", "reason": "De nieuwe tekst gaat over lwIP en timing, de bestaande tekst over exit codes; geen overlap."}` (4b)

> `{"action": "NOOP", "reason": "De nieuwe tekst over git-commando's heeft geen enkel verband met de technische beperkingen ..."}` (9b)

On 20 deliberately unrelated pairs: 4b answered NOOP 6 times, 9b 18 times. NOOP is the one action that causes the new memory NOT to be written, so a confused model defaults to silent knowledge loss.

Live blast radius is smaller than that suggests: `reconcile()` only asks about neighbours above `RECONCILE_THRESHOLD` (cosine 0.75), so genuinely unrelated pairs do not reach this prompt in production. The concern is what it reveals about behaviour near the boundary, where pairs are similar but not equivalent — precisely the hard cases the seam exists for.

Directions:

- Make the prompt's decision order explicit and put the destructive action last, e.g. "Is the new fact about the SAME thing? If no -> ADD." as a first step, so "no overlap" cannot reach NOOP.
- Consider renaming the action in the prompt (NOOP is jargon; "SKIP_DUPLICATE" states what it does) while keeping the wire value stable.
- The fallback ("Bij twijfel: ADD") is right and should stay: ADD is the recoverable error, NOOP is not.
- Re-measure with the same harness and the same seed. The pairs are cheap to regenerate and the arms are ~2 s per call now.

Second, independent finding from the same rows: all three seams parse with `find("{")` … `rfind("}")`. A model that continues in prose *after* the JSON object makes that slice span the trailing text, and the parse fails. The 4b never triggered it in 54 calls; the 9b did twice in 20. A brace-matching scan or a first-object parse would be more robust than the current widest-possible slice.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The reconcile prompt is reworded so "no overlap" cannot reach NOOP, with the ordering of the decision made explicit
- [ ] #2 The wire values ADD/SUPERSEDE/NOOP stay unchanged, so no stored data or caller needs migrating
- [ ] #3 judge-model-sweep.py is re-run on the same seed and the unrelated-pair NOOP rate is reported before and after
- [ ] #4 The JSON slice in _reconcile, _judge and _extract tolerates prose after the object, proven by a test with a trailing-text response
- [ ] #5 python -m pytest tests -q is green
<!-- AC:END -->
