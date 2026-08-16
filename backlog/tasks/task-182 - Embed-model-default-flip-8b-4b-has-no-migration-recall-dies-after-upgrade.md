---
id: TASK-182
title: Embed model default flip (8b to 4b) has no migration — recall dies after upgrade
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

_embeddings.py:58 changed the default to qwen3-embedding:4b. A vault that
relied on the old default upgrades into silently dead recall: kb-recall
gates on is_valid_for(conn, embed_id()) — index meta says :8b, code says
:4b — so recall returns [] until a rebuild, and the rebuild needs the 4b
model present, which nothing provides: setup.sh contains zero `ollama
pull` commands (verified). Every embed fails soft to None; the outage is
visible only as a failed counter. Companion gap: the judge-model default
got a named constant plus a stale-literal guard test in the same release,
but the embedding default stays a bare literal in three places
(_embeddings.py:58, install-agent-envs.py:180 and :968) with no constant
and no guard — the exact drift the judge-model test's docstring warns
about.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Upgrade path detects the embed_id mismatch and tells the user what to run (pull + rebuild), instead of returning [] silently
- [ ] #2 setup/upgrade pulls or verifies the configured embedding model before the index gate can trip
- [ ] #3 A named default-model constant, aliased by the installer, added to the stale-literal guard test
- [ ] #4 A vault pinning its model in config is untouched by all of the above
<!-- AC:END -->
