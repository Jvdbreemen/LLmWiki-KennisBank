---
id: TASK-129
title: Release v0.28.0
status: Done
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
- [x] #1 Full suite green on the code being released, before the documentation edits
- [x] #2 CHANGELOG.md has a dated 0.28.0 section and both compare links updated
- [x] #3 README.md and README.nl.md highlight sections updated in the same commit
- [x] #4 The upgrade note names the required ollama pull and the re-index cost
- [x] #5 Documentation test subset green after the doc edits
- [x] #6 PR opened against origin, CI green, review processed or its absence recorded
- [x] #7 Tag v0.28.0 on a SHA verified to be on origin/main after the merge
- [x] #8 GitHub release published and its body verified non-empty
<!-- AC:END -->


## Final Summary

v0.28.0 released. Tag on 86eb29039a74d3f99a6933ec3ce1da820bc770ac, verified equal to origin/main
after merging PR #99 and #100; `git rev-list -n1 v0.28.0` matched before publishing. Release body
verified non-empty at 4935 characters.

Gate: full suite 1135 passed, 2 skipped; documentation subset 56 passed; CI green on both PRs.

The Copilot review earned its place in this procedure. On PR #99 it caught that the release notes
promised `retrieve_threshold` 0.50 while `kb-retrieve.py` still fell back to 0.60 -- documentation
describing a default the shipped code did not have. Auditing the rest of the tree from that one
comment found four more stale spots (`kb-search.py` in three places, three C4 documents still
naming `MEMORY_MIN_COS = 0.60`), which became PR #100.

The deeper problem was the guard. `test_knob_consistency` stayed green throughout because it
compares `kb-retrieve.py` against `kb-calibrate.py`, and both said 0.60: a consistency check between
two sources can only detect that they differ, never that both are wrong. PR #100 anchors two
independent surfaces to the hook default instead -- the shipped example config and the search CLI.

Deliberate ordering: the tag waited for PR #100. Tagging documentation that disagrees with the code
and correcting it afterwards is the wrong way round, and the tag is the thing users pin to.
