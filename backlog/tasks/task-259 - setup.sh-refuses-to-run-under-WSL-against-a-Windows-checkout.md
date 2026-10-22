---
id: TASK-259
title: setup.sh refuses to run under WSL against a Windows checkout
status: In Progress
assignee: []
created_date: '2026-10-21T22:54:00Z'
updated_date: '2026-10-21T23:21:00Z'
labels:
  - setup
  - windows
dependencies: []
priority: high
ordinal: 193600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Observed 2026-10-21: an agent ran 'bash setup.sh' from a Windows shell where 'bash' resolved to System32 WSL bash. Windows env (HOME, KENNISBANK_VAULT) does not cross into WSL, so setup silently fell back to the WSL default vault /home/robert/KennisBank, refreshed its scripts and ran migrations there, while the intended Windows install did nothing. The docs warn about this, but nothing stops it. Detect WSL (/proc/version names Microsoft) with the checkout on a Windows drive mount (/mnt/<letter>/) and refuse before any write, naming Git Bash; --allow-wsl keeps a deliberate WSL install possible.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 setup.sh exits non-zero before creating or touching any vault path when run under WSL from a /mnt/<letter>/ checkout
- [x] #2 The message names the Git Bash command and the --allow-wsl override
- [x] #3 --allow-wsl and a non-WSL environment are unaffected
- [x] #4 A test covers refuse, override and the non-WSL path; docs mention the guard
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Reproduced 2026-10-21: 'bash' resolved to System32 WSL bash from the agent's Git Bash; setup refreshed scripts and ran migrations in the empty WSL scaffold vault /home/robert/KennisBank. Verified fix under real WSL (Ubuntu): exit 2 with the Git Bash hint, and the WSL vault's scripts dir mtime unchanged. tests/test_setup_wsl_guard.py covers refuse, --allow-wsl, a WSL-native checkout and non-WSL. The test suite itself already rejected the System32 bash in tests/test_setup_deploy.py:_find_bash; users had no such guard.
<!-- SECTION:NOTES:END -->
