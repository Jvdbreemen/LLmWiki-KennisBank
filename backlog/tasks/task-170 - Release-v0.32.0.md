---
id: TASK-170
title: Release v0.32.0
status: Done
assignee: []
created_date: '2026-08-16 06:54'
labels: []
dependencies: []
ordinal: 163700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Carries TASK-161 (freshness eval set + research) and TASK-169 (coverage-requiring closure prompts v3 + 64 healed closures), plus the backlog-format repairs from PR #122/#123.

Minor, not patch: both closing judges change behaviour — a memory that would have been closed under v2 stays open under v3 when coverage is partial — and every closure now stamps prompt version 3 into the closed-log. The healing itself (64 reopened memories) was a vault data operation and is already live; this release ships the prompts that stop the loss from recurring.

The urgency is the gap: the vault runs v0.31.1 scripts, so every sweep until this release deploys still closes memories under the v2 rule while the fix already exists on main.
<!-- SECTION:DESCRIPTION:END -->
