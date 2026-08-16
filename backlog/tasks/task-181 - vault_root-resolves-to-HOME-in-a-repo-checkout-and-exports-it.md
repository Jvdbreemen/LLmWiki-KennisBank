---
id: TASK-181
title: vault_root resolves to $HOME in a repo checkout and exports it
status: In Progress
assignee: []
created_date: '2026-08-15 23:30'
updated_date: '2026-08-15 23:30'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by the 2026-08-15 eight-angle /code-review over main...release/v0.31.1,
verified against source before filing. Task IDs 169-179 are reserved by the
open PR #2 branch; this series starts at 180.

_vaultpath._script_vault (line ~31) checks `parents[2]/.claude`, which is
meant to detect the installed layout <vault>/.claude/scripts/. In a plain
checkout, scripts live at <repo>/scripts/, so parents[2] is the repo's
PARENT — typically $HOME, where ~/.claude (Claude Code's own config dir)
exists on nearly every dev machine. vault_root() then returns $HOME and
`os.environ.setdefault(ENV_VAR, ...)` stamps the wrong root into every
child process: kb-index.db, caches and logs land inside ~/.claude and
retrieval scans a nonexistent ~/02-wiki, with no error. Verified live in a
container checkout: vault_root() returned /home/user; this is also the
real cause of the three chronic test_vaultpath failures previously read
as environmental. The guard should verify `parents[1].name == ".claude"`
(the installed layout's actual signature), not that parents[2] merely
contains a .claude directory. Related but distinct from TASK-167 (the
per-script setdefault headers); both stem from the same parents[2] guess.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Guard identifies the installed layout by parents[1].name == '.claude', never by a .claude dir existing at parents[2]
- [ ] #2 In a repo checkout with KENNISBANK_VAULT unset, vault_root() returns DEFAULT_VAULT and exports nothing
- [ ] #3 The three test_vaultpath failures pass in a checkout under $HOME with ~/.claude present
- [ ] #4 Reconciled with TASK-167 so the fix lands once, not per script
<!-- AC:END -->
