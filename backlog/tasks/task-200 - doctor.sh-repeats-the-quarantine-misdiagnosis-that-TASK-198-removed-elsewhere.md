---
id: TASK-200
title: doctor.sh repeats the quarantine misdiagnosis that TASK-198 removed elsewhere
status: Done
assignee: []
created_date: '2026-08-17 21:58'
updated_date: '2026-08-18'
labels:
  - memory
  - follow-up
dependencies: []
references:
  - scripts/doctor.sh
  - scripts/memory-doctor.py
  - scripts/memory-notify.py
priority: medium
type: bug
ordinal: 168700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found while verifying the v0.34.0 deploy on a live vault.

`scripts/doctor.sh:592` still reads:

```sh
rot="$(python3 "$SCRIPTS_DIR/memory-doctor.py" rot 2>/dev/null)"
if [ "${rot:-0}" -gt 0 ] 2>/dev/null; then
  report_warn "geheugen quarantaine" "$rot unverified memories ouder dan 48u (sweep/judge hangt?)"
```

That is the same defect TASK-198 was about, in a place TASK-198 did not touch. On the vault that produced it the sweep was not hanging at all: heartbeat clean, `errors: 0`, every memory already judged and graded `partial` by a whole-transcript read. `(sweep/judge hangt?)` points the reader at a component that is fine, and the check reports one number where there are now two meanings.

TASK-198 corrected `memory-notify.py`, the `rot_breakdown` docstring, the design spec and the task file. It missed this one. Correcting some occurrences and leaving the rest is worse than leaving them all, because the remaining ones now look current.

## What it should do

Use `memory-doctor.py rot_breakdown` (added in v0.34.0) and report the two buckets separately, each with advice that applies:

- `waiting` -> genuinely points at the sweep or the model.
- `undecided` -> judged and undecidable; only a person moves those, via `memory-doctor.py pending` and `decide <stem> approve|reject|skip`. Not `/kennisbank:review`, which is the audit-view and offers only `demote`/`reopen`.

`rot_breakdown` has no CLI subcommand yet — `memory-doctor.py rot` still prints the total only. Either add a `--json` breakdown to the `rot` subcommand or add a `rot-breakdown` one; doctor.sh is a shell script and needs a parseable surface.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 memory-doctor.py exposes the waiting/undecided split on its CLI in a form a shell script can parse
- [x] #2 doctor.sh reports the two buckets separately and names an action that applies to each
- [x] #3 doctor.sh no longer claims or implies that the sweep or judge is hanging when the heartbeat says otherwise
- [x] #4 A test covers the doctor output for a vault with only undecided memories, asserting it does not blame the sweep
- [x] #5 python -m pytest tests -q is green
<!-- AC:END -->
