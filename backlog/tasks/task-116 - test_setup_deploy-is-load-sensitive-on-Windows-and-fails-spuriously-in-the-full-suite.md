---
id: TASK-116
title: >-
  test_setup_deploy is load-sensitive on Windows and fails spuriously in the
  full suite
status: Done
assignee:
  - '@claude'
created_date: '2026-07-30 05:49'
updated_date: '2026-07-30 20:36'
labels: []
dependencies: []
ordinal: 114700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Measured twice on 2026-07-29/30: tests/test_setup_deploy.py produces 4-5 failures (including test_hook_registration_preserves_existing_settings and test_rerun_preserves_user_data_and_refreshes_tooling) during a full local suite run on Windows, while the same file passes 22/22 in isolation (463s) and the whole suite passes on the Linux CI runner. Both failing runs happened while the machine was saturated: two 30-agent workflows with 1500+ tool calls plus an eval over 1550 questions. The file shells out to the real setup.sh, so it spawns bash and python subprocesses and is timing-sensitive in a way the rest of the suite is not. This makes the local gate untrustworthy exactly when a developer is busiest, which is the worst possible moment for a false red. Investigate whether the tests carry an implicit timeout, whether they can be made load-independent (explicit waits rather than fixed sleeps, or a slower budget on Windows), and whether the suite should mark them so a false red is distinguishable from a regression. Do not simply raise a timeout without establishing what actually times out.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Root cause established: what exactly fails under load (which subprocess, which wait, which assertion)
- [x] #2 Fix makes the tests pass in a saturated full-suite run on Windows, or they are explicitly marked and reported as load-sensitive rather than failing silently
- [x] #3 No timeout is raised without evidence of what it is waiting for
- [x] #4 Full suite green locally on Windows under load
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Root cause (reproduced 2026-07-30)

The tests carry NO timeout of their own. The only hard wall-clock budget in the
whole setup.sh path is scripts/install-agent-envs.py:783 validate_mcp_runtime(vault, timeout=15).

Chain:
1. setup.sh:39 defaults AGENTS="claude,codex".
2. setup.sh:453-459 runs install-agent-envs.py --install --validate --skip-models.
3. install-agent-envs.py:1132 gates the MCP check on codex/opencode/copilot being
   present -> TRUE for the default agent list.
4. install-agent-envs.py:1133 calls validate_mcp_runtime(vault) with timeout=15,
   which does two subprocess.run calls (:792 dep-check, :854 nested stdio handshake
   where a python client spawns a python MCP server), each capped at 15s.
5. On TimeoutExpired (:802 / :865) it returns an error string -> main() returns 1 (:1155).
6. setup.sh:24 set -e aborts immediately; AGENT_VALIDATE_RC=$? at :460 is dead code.
7. Test run_setup_in (tests/test_setup_deploy.py:270-274) uses check=True -> CalledProcessError.

--skip-model-check does NOT skip this: it maps to --skip-models, which gates only
validate_models at :1134, not validate_mcp_runtime at :1133.

## Measurements

Idle:        validate_mcp_runtime = 10.03s of the 15s budget (dep-check 2.78s).
             Only 1.5x headroom.
Under load:  16 CPU burners + 4 process-spawn churners on 16 logical cores ->
             dep-check alone exceeded 15s (>5.4x slowdown).
             Production call returned:
               ["KennisBank MCP dependency check timed out: py -3"], main -> 1.

A/B of real setup.sh under identical load:
  A  --yes --skip-model-check                  -> exit 1, validation: FAIL, MCP timeout, 184.8s
  B  --yes --skip-model-check --agents claude  -> exit 0, validation: PASS, no timeout, 380.9s
B was SLOWER and still green, because it has no wall-clock budget to blow.
All four artifacts the tests assert on (settings.json, schema stamp, doctor.sh,
kb-activity.db) were present in BOTH runs.

## Why the full suite and not isolation

No pytest-xdist, no conftest.py, no pytest config: the suite is sequential and
single-process, so the suite does not load itself. The full suite is simply a
~20-minute window versus 463s in isolation, so it is ~2.6x more likely to overlap
a machine-saturation period. That reconciles the clean v0.26.1 run.

## Proposed fix (removes the budget, does not widen it)

Add --agents claude to the three setup.sh invocations in tests/test_setup_deploy.py:
  :96  _installeer_eenmalig
  :149 run_setup
  :271 run_setup_in
(:434 test_interactive_decline already does this.)

This deletes the nested python-spawns-python stdio handshake from every run in the
file, and also skips the mcp==1.28.1 pip install at setup.sh:290-292 (a network call).
No coverage is lost: the file has zero assertions on codex/opencode/copilot/MCP
artifacts, and validate_mcp_runtime logic is covered deterministically with mocked
subprocesses in tests/test_agent_envs_install.py:264-302.

Prerequisite diagnostic fix: run_setup_in (:270-274) uses check=True, whose
CalledProcessError carries no stdout/stderr. That is why the original failures
reported only "non-zero exit status 1". Mirror run_setup (:153-157) and embed
STDOUT/STDERR so any recurrence self-reports.

## Not ruled out

A second path produces an identical outer symptom: register_hooks (setup.sh:409-410)
and _migrations.py (:436-437) are fail-soft via || echo, so a partial failure lets
setup.sh continue to validate_files (:1131), which then reports the inconsistency ->
same exit 1. Mechanism A is reproduced at the exact production budget; B has not
been observed. The diagnostic fix above is what distinguishes them in future.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Root cause is a single hard wall-clock budget, not the load-sensitivity the title assumed.

validate_mcp_runtime(vault, timeout=15) at scripts/install-agent-envs.py:783 is the only wall-clock limit in the whole setup.sh path. It runs two subprocess calls, one of them a nested stdio handshake in which a Python client spawns a Python MCP server. Idle it consumes 10.03 of its 15 seconds. When it blows, main() returns 1 at :1155, set -e aborts setup.sh, and the test fails on check=True with an exit status and nothing else.

Three parts of the original premise did not hold, and saying so matters more than the fix. There is no timeout, sleep or shared tempdir in the test file; every test gets its own mkdtemp. It is not suite parallelism: there is no xdist, no conftest and no pytest config, so the suite is sequential and single-process. The full suite is simply a twenty-minute window against 463 seconds in isolation, so it is far likelier to overlap machine-wide saturation. That also explains the clean v0.26.1 run, and it is why one green run could never have settled this.

A quiet trap sits next to it: --skip-model-check looks like it covers this and does not. It maps to --skip-models, which gates validate_models at :1134, not the MCP validation at :1133.

Fix removes the budget rather than widening it: the three setup.sh invocations at :96, :149 and :271 now pass --agents claude, as :434 already did. No coverage is lost. The file asserts nothing about codex, opencode, copilot or MCP artifacts, and validate_mcp_runtime is tested deterministically with mocked subprocesses at tests/test_agent_envs_install.py:264-302. It also removes the mcp pip install from every run, which is why the full suite dropped from 23m23 to 9m36.

Two additions the task did not ask for. run_setup_in used check=True, whose exception carries no stdout or stderr, which is exactly why the original failures reported only 'non-zero exit status 1' with no cause; it now mirrors run_setup and embeds both. And SetupInvocationGuardTest fails the moment any setup.sh invocation in this file drops --agents, because for an intermittent defect a green run proves nothing while the absence of the cause does. The guard was verified by reverting one invocation and confirming it fails, then restoring it.

Evidence: the flake reproduced on this machine during the TASK-119 validation run (2 failed, 1119 passed, 23m23), which is what confirmed the diagnosis rather than a lucky green. Under a deliberate load harness of 16 CPU burners plus 4 spawn churners on 16 logical cores, the production dep-check exceeded its 15 s budget and returned the timeout error. An A/B against real setup.sh under identical load: current flags exit 1 with validation FAIL, --agents claude exit 0 with validation PASS while doing strictly more work and taking longer. Final full suite after the fix: 1122 passed, 2 skipped, zero failures.

Not ruled out: register_hooks (setup.sh:409-410) and _migrations.py (:436-437) are fail-soft via || echo, so a partial failure there would reach validate_files and produce the same exit 1. That path was never observed. The diagnostic change is what will tell the two apart next time.
<!-- SECTION:FINAL_SUMMARY:END -->
