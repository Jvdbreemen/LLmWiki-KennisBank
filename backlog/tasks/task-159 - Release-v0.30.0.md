---
id: TASK-159
title: Release v0.30.0
status: Done
assignee: []
created_date: '2026-08-13 22:43'
updated_date: '2026-08-13 22:44'
labels:
  - release
dependencies: []
priority: high
ordinal: 152700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Cuts v0.30.0 from `origin/main`, following `skills/kennisbank-release/SKILL.md`.

Version proposed as **minor**, from the delta since v0.29.0: several `feat:` commits, a new frontmatter field (`volatility`), three new scripts (`_progress.py`, `_llmjson.py`, `kb-state-audit.py`), new `memory-doctor` subcommands, and changed defaults (supersede threshold 0.85 to 0.75, TOP_K 2 to 3). No breaking change to the CLI, commands or vault layout, so not a major.

What the release carries, all merged and measured:

- TASK-141 the hermeticity pin was slow here and silently switched off entirely
- TASK-144 NOOP meant the opposite of what it says; robust JSON in five seams
- TASK-146 `volatility: state | event` puts the update rule in the structure
- TASK-147 supersede window 0.85 to 0.75, TOP_K 2 to 3
- TASK-148 a zero means "nothing to do", never "this crashed"
- TASK-149 kb-state-audit compares memories against an authority
- TASK-150 a closed memory is visible and reopenable again
- TASK-152 the upgrade stamps a commit, not a tag object
- TASK-153 long-running scripts show progress and an estimate
- TASK-154 neighbour search through the index: 11x, identical pair set
- TASK-155 a NOOP records what it discarded
- TASK-156 the supersede judge reordered: 30% to 55% recognition

Two findings in this release contradict the tasks that asked for them, and both belong in the notes rather than being quietly dropped: the supersede judge is not too conservative (86% of its refusals are correct; the recorded history is contaminated with duplicate cleanups), and growing the corpus cost memory recall@5 0.778 to 0.768, below a floor set in advance.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Version and its reason stated from the commit delta
- [x] #2 CHANGELOG has a dated 0.30.0 section and both compare links updated
- [x] #3 Both READMEs name v0.30.0 in their highlight and new-in headings
- [x] #4 Full gate green before the docs edit, docs subset green after
- [x] #5 Copilot review processed before the merge
- [x] #6 The tag points at a SHA verified to be on origin/main
- [x] #7 The published release body is not empty
<!-- AC:END -->

Final Summary:
--------------------------------------------------
v0.30.0 published: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.30.0

Tag `v0.30.0` points at `9c035e5`, verified equal to `origin/main` after the
merge rather than assumed. Release body 7552 characters, checked non-empty --
both halves of that verification exist because both failed once before.

Gate: full suite 1382 passed / 2 skipped on the released code, documentation
subset 56 passed after the docs edit. Copilot reviewed the release PR and
generated no comments.

Carried twelve tasks. Two of them produced measurements that contradicted the
task that asked for them, and both went into the release notes as they came out:
the supersede judge is not too conservative (86% of its refusals are correct),
and growing the memory corpus cost recall@5 0.778 -> 0.768, below a floor
recorded a day in advance.
