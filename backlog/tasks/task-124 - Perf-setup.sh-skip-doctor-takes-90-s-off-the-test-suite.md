---
id: TASK-124
title: 'Perf: setup.sh --skip-doctor takes 90 s off the test suite'
status: In Progress
assignee: []
created_date: '2026-07-31 20:48'
updated_date: '2026-07-31 21:23'
labels:
  - perf
  - tests
dependencies: []
modified_files:
  - setup.sh
  - tests/test_setup_deploy.py
  - README.md
  - README.nl.md
priority: medium
ordinal: 120700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The local gate `python -m pytest tests -q` costs 550 s. Measured with `--durations=25`: `tests/test_setup_deploy.py` alone accounts for 363 s (66%). A gate that expensive is skipped in practice, which pushes quality assurance to after-the-fact CI.

Traced one `setup.sh` run with `PS4='+[${SECONDS}s] '`:

```
 0-17s  copy_force loop over ~100 scripts/templates/commands/skills
17-19s  register-hooks + migrations + activity-index + agent-envs
19-34s  doctor.sh          <-- runs at the END of every setup.sh
34-35s  agent-status + closing lines
```

The suite invokes `setup.sh` six times, so it pays that trailing `doctor.sh` six times (~90 s) for validation no test asserts on: all three doctor tests call `scripts/doctor.sh` directly through `run_doctor_in` (tests/test_setup_deploy.py:283).

Fix: a `--skip-doctor` flag on `setup.sh`, passed by the per-test invocations. The shared installation (`_installeer_eenmalig`, line 97) keeps running the full gate, so a doctor regression still fails the suite — every read-only test depends on that install returning 0, and `setup.sh` exits 1 when `DOCTOR_RC != 0`.

Out of scope, follow-ups if this pays off: batching the 45 separate `python3` invocations inside `doctor.sh` (helps real users too — `/kennisbank:doctor` is 15 s), and the `copy_force` loop (~130 ms per file, touches every real install).

Watch out for `SetupInvocationGuardTest` (line 474): it parses this test file for `setup.sh` argument lists and enforces `--agents claude` on each. The new flag has to be covered there too, otherwise a future call site silently pays the 15 s again.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 setup.sh accepts --skip-doctor, documented in the header comment, in usage() and in both READMEs
- [x] #2 With --skip-doctor the trailing doctor.sh is skipped, the skip is printed, DOCTOR_RC is 0, and the closing summary no longer claims doctor ran
- [x] #3 Per-test setup.sh invocations in tests/test_setup_deploy.py pass --skip-doctor; the shared installation still runs the full doctor gate
- [x] #4 SetupInvocationGuardTest asserts exactly one invocation runs WITHOUT --skip-doctor, so the self-validating path stays covered
- [x] #5 python -m pytest tests -q is green on the branch (1123 passed, 2 skipped)
- [x] #6 tests/test_setup_deploy.py measurably faster in a back-to-back comparison against main on the same machine
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
setup.sh: SKIP_DOCTOR flag, guarded doctor block (skip prints a line and sets DOCTOR_RC=0), conditional closing summary so it does not claim validation that did not run. Documented in the header, usage() and the "useful flags" block of README.md and README.nl.md.

tests/test_setup_deploy.py: --skip-doctor added to run_setup(), run_setup_in() and the interactive-decline invocation. _installeer_eenmalig deliberately keeps the full gate. SetupInvocationGuardTest gained a shared _setup_aanroepen() helper plus test_exactly_one_invocation_still_runs_the_doctor_gate.

Measurement notes for whoever picks up the follow-ups:

- Back to back on the same machine, tests/test_setup_deploy.py alone: main 314.87 s (23 tests) -> branch 221.94 s (24 tests). -92.9 s, matching the predicted 6 x 15 s.
- The full suite does NOT show this in a single before/after pair (550 s -> 560 s). Run-to-run spread swamps it: unchanged main measured 621.47 s and 549.82 s. Measure per file, not per suite, when judging the follow-ups.
- One full-suite run reported 45 failures. That was two concurrent pytest runs colliding, not a regression: run alone, the same commit is green at 1123 passed, 2 skipped. Do not run two suites against this repo at once.
<!-- SECTION:NOTES:END -->
