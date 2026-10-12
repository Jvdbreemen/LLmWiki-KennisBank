---
id: TASK-255
title: setup.sh deploys a launcher command beside its same-named skill
status: Done
assignee: []
created_date: '2026-10-12 16:51'
updated_date: '2026-10-12 17:10'
labels:
  - setup bug
dependencies: []
priority: low
ordinal: 192600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
/skills in Claude Code listed kennisbank-upgrade, kennisbank-contribute (and opruimen) twice: once as the skill in ~/.claude/skills and once as the root command in ~/.claude/commands that only launches it. Observed 2026-10-12 on v0.39.0. setup.sh now skips a root command whose name matches a skill in skills/ and removes an older copy; install-agent-envs validation checks kennisbank-upgrade as a skill only. commands/ keeps the files: they feed Codex prompts and OpenCode commands.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 setup.sh does not deploy a root command beside a same-named skill
- [x] #2 A re-run removes such a launcher left by an older install
- [x] #3 Codex and OpenCode aliases are unchanged
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
setup.sh install_root_commands skips a root command whose name matches a skill in skills/ and removes an older copy; install-agent-envs validation checks kennisbank-upgrade only as a skill. Two new tests in test_setup_deploy.py fail without the setup.sh change and pass with it. Full suite in four parts: 2088 passed; 20 failures reproduce on the unchanged baseline (17 hermes_install symlink privilege on Windows, opruimen self-test, 2 proc_bounded).
<!-- SECTION:FINAL_SUMMARY:END -->
