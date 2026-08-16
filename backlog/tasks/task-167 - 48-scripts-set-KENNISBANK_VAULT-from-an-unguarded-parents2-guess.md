---
id: TASK-167
title: '48 scripts set KENNISBANK_VAULT from an unguarded parents[2] guess'
status: Done
assignee: []
created_date: '2026-08-15 16:00'
labels:
  - hygiene
  - adr-0002
  - scripts
dependencies: []
ordinal: 160700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Every script but two opens with:

    os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))

In a deployed vault that is right: `$VAULT/.claude/scripts/x.py` → `parents[2]` is the vault. In a repo checkout it points at the directory **above the repo**, and because it is `setdefault` on a process-wide variable, every later caller in that process inherits it — including pytest, which imports these modules at collection time.

`_vaultpath._script_vault()` already makes the same guess and **guards it**:

    candidate = Path(__file__).resolve().parents[2]
    if (candidate / ".claude").is_dir():
        return candidate

So the bare setdefault is redundant where it is correct and wrong where it is not. It is also the thing ADR-0002 exists to prevent — a vault path decided outside `_vaultpath.py`.

Found by Copilot on PR #121, as a *suppressed* comment (they appear only in the review body, never in `pulls/<n>/comments`). Two scripts new in that PR were fixed there; these 48 were left because changing every script's import preamble during a release is a large blast radius for a correctness issue nobody has hit yet.

Why it has not bitten: in practice `KENNISBANK_VAULT` is set — by the hooks, by `setup.sh`, by the user's environment — so `setdefault` is a no-op. The exposure is a bare `python3 scripts/x.py` from a checkout, and tests.

The work is mechanical but wants care in one place: `vault_root()` sets the variable itself when it identifies a real vault, specifically so detached child processes stay on the same vault when the harness did not propagate the environment. Removing the setdefault must not remove that, and a test should pin it — a detached warm-up child landing on a different vault would be silent and awful.

<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The unguarded setdefault is gone from every script, with vault resolution left to _vaultpath
- [ ] #2 A test pins that a detached child process still resolves the same vault as its parent
- [ ] #3 Running any script directly from a repo checkout does not create or write to a path outside the repo
- [ ] #4 python -m pytest tests -q is green
<!-- AC:END -->

## Close-out (2026-08-16)

Shipped in PR #135 (commit series on fix/silent-failure-cluster): the bare setdefault header is deleted from 47 scripts, resolution flows through vault_root() only, the pattern is banned by test_no_script_guesses_the_vault_from_parents, and a subprocess test pins the detached-child export.
