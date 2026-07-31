---
id: TASK-124
title: 'Perf: setup.sh --skip-doctor takes 90 s off the test suite'
status: In Progress
assignee: []
created_date: '2026-07-31 20:48'
labels:
  - perf
  - tests
dependencies: []
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
- [ ] #1 setup.sh accepts --skip-doctor, documented in the header comment and in usage()
- [ ] #2 With --skip-doctor the trailing doctor.sh is skipped, the skip is printed, and DOCTOR_RC is 0 so the exit status stays honest
- [ ] #3 Per-test setup.sh invocations in tests/test_setup_deploy.py pass --skip-doctor; the shared installation still runs the full doctor gate
- [ ] #4 SetupInvocationGuardTest asserts at least one invocation runs WITHOUT --skip-doctor, so the self-validating path stays covered
- [ ] #5 python -m pytest tests -q is green and measurably faster than the 550 s baseline
<!-- AC:END -->
