---
id: TASK-129
title: Release v0.28.0
status: In Progress
assignee: []
created_date: '2026-08-03 16:12'
labels:
  - release
dependencies: []
priority: high
ordinal: 124700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Release v0.28.0 from origin/main. Minor: new production functionality (instruction prefixes in _embeddings) plus three behaviour changes users will notice.

Carried work:

- PR #96, TASK-126 — nine embedding models measured on the vault's own eval sets; default moves from qwen3-embedding:8b to qwen3-embedding:4b. Thresholds measured rather than inherited: retrieve_threshold 0.60 -> 0.50, MEMORY_MIN_COS 0.60 -> 0.45. Instruction prefix support (query/doc side) with embed_id folding in the doc prefix. New tooling: embed-sweep.py, recall-ablation.py, rerank-eval.py.
- PR #97, TASK-127 — /sessiestart no longer claims a relationship to third-party context tooling.
- PR #98, TASK-128 — the memory layer drops its lexical arm. recall@5 0.658 -> 0.794 on the production route.

Upgrade note that must be prominent: `validate_models` runs `ollama show` and does not pull, so a vault without qwen3-embedding:4b fails setup loudly. Users need `ollama pull qwen3-embedding:4b`, and the first index build after the switch re-embeds the whole vault because embed_id changes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Full suite green on the code being released, before the documentation edits
- [ ] #2 CHANGELOG.md has a dated 0.28.0 section and both compare links updated
- [ ] #3 README.md and README.nl.md highlight sections updated in the same commit
- [ ] #4 The upgrade note names the required ollama pull and the re-index cost
- [ ] #5 Documentation test subset green after the doc edits
- [ ] #6 PR opened against origin, CI green, review processed or its absence recorded
- [ ] #7 Tag v0.28.0 on a SHA verified to be on origin/main after the merge
- [ ] #8 GitHub release published and its body verified non-empty
<!-- AC:END -->
