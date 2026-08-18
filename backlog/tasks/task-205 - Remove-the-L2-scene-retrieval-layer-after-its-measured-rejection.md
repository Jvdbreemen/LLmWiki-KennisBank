---
id: TASK-205
title: Remove the L2 scene retrieval layer after its measured rejection
status: Done
assignee: []
created_date: '2026-08-18 17:18'
labels:
  - retrieval
  - simplification
  - yagni
dependencies: []
references:
  - scripts/kb-recall.py
  - scripts/kb-retrieve.py
  - scripts/_scenes.py
  - docs/research/l2-scene-retrieval-2026-08.md
  - docs/superpowers/specs/2026-08-05-l2-scene-retrieval-design.md
priority: medium
type: chore
ordinal: 170700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-134 measured the L2 scene tier on 2026-08-10/11 against a pre-registered winner rule and rejected it: recall@5 +0.000 (needed >= +0.02), recall@1 -0.006 (needed no decrease), p50 +65 ms (needed < +5 ms), gain in 1 of 4 memory_type groups (needed >= 2). `scene_retrieval` has been off ever since and the owner confirmed on 2026-08-18 it stays off.

The code is still there and inert. That is the expensive kind of dead code: `_scene_path`, `_merge_scene_members`, `_scene_members_for` and the `scene_prior` argument thread through `kb-recall.py`, the hot-path read library, so every future change to recall has to reason around a branch nothing reaches.

## Why all-or-nothing

The obvious compromise — drop the production path, keep the experiment — does not work. `scene-experiment.py:67` drives `kb_recall.recall_hits(..., scene_prior=...)`, so the experiment measures the production path. Removing `scene_prior` from `kb-recall.py` guts the experiment either way.

## Why removal rather than keeping the substrate

The follow-up the research recommends needs a fourth clusterer that does not exist (chunked LLM clustering; the single-shot variant died on a 32k-token prompt over 1508 notes). Keeping three rejected clusterers plus an inert hot-path branch does not accelerate that work. The research report and git history do, and better.

## Scope

Delete: `scripts/_scenes.py` (352), `scripts/build-scene-index.py` (178), `scripts/scene-experiment.py` (195), `scripts/scene-report.py` (145), and `tests/test_scenes.py`, `test_scene_recall.py`, `test_scene_experiment.py`, `test_scene_report.py` (938 lines together).

Simplify: `kb-recall.py` (~90 lines), `kb-retrieve.py` (~25), `kb-eval.py`, `_settings.py`, and the scene references in `test_knob_consistency.py`, `test_query_seam_callsites.py`, `test_kb_retrieve_memory.py`.

Sweep: toggle lists in `commands/kennisbank/settings.md` and `skills/kennisbank-upgrade/SKILL.md`, plus the nine `docs/C4-Documentation/` files that name the layer.

Keep: `_querycache.py` (extracted from scene-experiment in TASK-190, now shared with rank-factors and rerank-ceiling); `docs/research/l2-scene-retrieval-2026-08.md`, the spec and the plan; the CHANGELOG history. Those are the record of why, and deleting them invites rebuilding the thing.

Vault side: `kb-scene.db` is derived and has no automated builder, so it can be deleted from a deployed vault.

An ADR records the reversal, so the next person proposing a scene layer meets the measurement first.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 No `scene` identifier remains in scripts/ outside `_querycache.py`'s docstring history note
- [x] #2 `kb-recall.recall_hits` and `memory_hits` no longer take a `scene_prior` argument, and no caller passes one
- [x] #3 The `scene_retrieval`, `scene_clusterer`, `scene_floor` and `scene_boost` knobs are gone from `_settings.py`, `kb-retrieve.py`, the settings command and the upgrade skill
- [x] #4 `docs/research/l2-scene-retrieval-2026-08.md`, the spec, the plan and the CHANGELOG history are untouched
- [x] #5 `_querycache.py` still exists and rank-factors plus rerank-ceiling still work
- [x] #6 An ADR records the reversal, cites the four failed winner-rule conditions and the oracle ceiling, and is linted
- [x] #7 `python -m pytest tests -q` is green with the scene tests removed rather than skipped
<!-- AC:END -->

## Final Summary

Committed as d203384 on chore/task-205-remove-scene-layer, built in a separate
worktree because the shared checkout carries another session's uncommitted
v0.35.0 release work. Net: 32 files, +402/-2009. Suite 1575 passed / 3 skipped
with the real pytest exit code captured (an earlier run reported exit 0 through
a tail pipe while 2 tests failed).

Those 2 failures were the repo's own guards catching what the sweep missed:
kennisbank-settings.example.json still shipped scene_retrieval, and the
ghost-env-var guard flagged KB_SCENE_* documented in the kept spec/plan. Fixes:
example cleaned; docs/superpowers/ added to _markdown_files() exclusions in
test_docs_consistency.py - dated specs/plans are decision records of the same
class as research and ADRs, which were already excluded. That widening covers
every consistency check sharing the generator; flagged in the commit body.

ADR-008 iterated to adr-kit grade A 1.0 (initially C: missing Related
Decisions/References; the ADR-001 reference names the legacy file
0001-embedding-model-default.md because the linter cannot resolve the old
numbering). tests/test_no_scene_layer.py (9 guards) pins the removal and tells
any future re-introduction to delete the file in the same change.

Open: PR to fork/upstream (after the parallel v0.35.0 release lands), and
kb-scene.db still in the deployed vault (3.5 MB, derived, deletable any time).
