---
id: TASK-144
title: >-
  Both judge models read NOOP as "unrelated", and NOOP is the verdict that
  discards knowledge
status: In Progress
assignee: []
created_date: '2026-08-12 19:14'
updated_date: '2026-08-13 18:34'
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
- [x] #1 The reconcile prompt is reworded so "no overlap" cannot reach NOOP, with the ordering of the decision made explicit
- [x] #2 The wire values ADD/SUPERSEDE/NOOP stay unchanged, so no stored data or caller needs migrating
- [x] #3 judge-model-sweep.py is re-run on the same seed and the unrelated-pair NOOP rate is reported before and after
- [x] #4 The JSON slice in _reconcile, _judge and _extract tolerates prose after the object, proven by a test with a trailing-text response
- [ ] #5 python -m pytest tests -q is green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Measured A/B, 2026-08-13, qwen3.5:4b, 20 unrelated pairs, seed 42

Both prompts were run against the SAME pairs in one go. Re-running the old
sweep would have compared two different samples rather than two prompts: the
documented "before" comes from a corpus that has since grown from 1531 to 1595
memories, so the seeded selection no longer draws the same pairs.

    OLD prompt:   ADD=14  NOOP=5  SUPERSEDE=1     NOOP on unrelated pairs 25%
    NEW prompt:   ADD=20                          NOOP on unrelated pairs  0%

The old prompt reproduced the documented failure verbatim, in the model's own
words:

> {"action": "NOOP", "reason": "De twee onderwerpen zijn ongerelateerd:
> Git-commit validatie versus MQTT-reset na flash."}

Unrelated is the definition of ADD, and NOOP is the one action that throws the
new memory away. The new prompt asks "is this even about the same thing?"
first, with ADD as the answer, and puts the destructive action last with what
it costs spelled out. Wire values are untouched, so nothing needs migrating.

Side effect worth recording: the new prompt is also faster (39s against 49s for
the same 20 pairs), presumably because the answers are shorter once the model
stops explaining why two unrelated texts do not overlap.

## The JSON slice

`_llmjson.py` replaces `raw[find("{"):rfind("}")+1]` in five seams (_extract,
_judge, _reconcile, and both judges in _maintenance). It takes the FIRST
complete object or array, counting depth with string and escape awareness, and
falls back to the old wide slice only if that yields nothing.

Two failure shapes, not one. The task described trailing prose; a review of the
first implementation found the mirror case, which is just as silent:

    Ik denk {even} na. {"action": "ADD"}

Taking only the first opening brace picks `{even}`, fails, falls back to the
wide slice which also fails, and the seam returns its fail-safe as if the model
had said nothing at all. `_parse` now walks successive opening delimiters until
one parses. Both directions have tests.

## What still has no trace

`RECONCILE_PROMPT_VERSION` is stamped in the closed-log reason (TASK-150), so
every supersession is traceable to the prompt that caused it. A NOOP leaves
nothing behind: the candidate is discarded and the heartbeat only counts how
often. That is precisely the action models get wrong, so the gap is filed
separately rather than left as an unstated assumption.
<!-- SECTION:NOTES:END -->
