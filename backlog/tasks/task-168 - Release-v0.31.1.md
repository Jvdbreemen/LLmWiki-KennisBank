---
id: TASK-168
title: Release v0.31.1
status: Done
assignee: []
created_date: '2026-08-15 19:07'
labels:
  - release
  - docs
dependencies: []
ordinal: 161700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A patch, and small on purpose: it carries `801fdef`, the commit that processed the Copilot review on PR #114 and was then never merged. PR #114 itself landed as `e314f70`; its review-processing follow-up stayed behind on `fix/upgrade-stamps-tag-object` and has sat there since 2026-08-13.

That is the failure this repo's own policy exists to prevent, one step further along than usual: the review was read *and acted on*, and then the acting was lost.

**What it fixes.** `C4-Documentation/c4-code-skills.md` documents step 10 of the upgrade skill as

    git rev-parse --short $LATEST

with no `^{}`. Every tag in this repo is annotated, so that command yields the SHA of the tag *object*, not the commit — which is exactly how v0.28.0 was stamped `80b0285` instead of `86eb290` and v0.29.0 `1506a9c` instead of `1cb608d`. The reference documentation was prescribing the bug the skill it documents warns about.

**What it does not fix, despite appearances.** The same commit rewrites `"<git rev-parse --short "$LATEST^{}">"` to `"<git rev-parse --short $LATEST^{}>"` in `skills/kennisbank-upgrade/SKILL.md`. Tested both forms: they behave identically, because a command substitution opens a fresh quoting context. That hunk is readability, not correctness, and the changelog should not claim otherwise.

Also checked and deliberately excluded: `perf/default-embed-qwen3-4b` (`4274941`). Its content is already on main by another route — the default is `qwen3-embedding:4b` and `docs/research/embedding-model-sweep-2026-08.md` exists — and the branch is behind main in places. Stale, not unreleased.

<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 801fdef lands on main, having been verified rather than assumed correct
- [x] #2 The changelog distinguishes the real fix from the cosmetic hunk in the same commit
- [x] #3 README.md and README.nl.md both get a v0.31.1 entry, in the same edit
- [x] #4 Full suite green before the docs edit; documentation subset green after
- [x] #5 Copilot review processed — comments endpoint AND review body — before merge
- [x] #6 Tag placed only on a SHA verified present on origin/main, and published with a non-empty body
<!-- AC:END -->
