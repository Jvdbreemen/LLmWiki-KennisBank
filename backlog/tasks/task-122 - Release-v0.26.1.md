---
id: TASK-122
title: Release v0.26.1
status: Done
assignee:
  - '@claude'
created_date: '2026-07-30 19:01'
updated_date: '2026-07-30 19:16'
labels:
  - release
dependencies: []
ordinal: 117700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Patch release carrying documentation-only corrections to the C4 architecture set that shipped in v0.26.0. Carries TASK-111 (three factual claims in the figure spec: vault folder count, database rebuildability, a named Atlas lens that does not exist), TASK-112 (two geometry errors and a wrong internal cross-reference in the same spec), TASK-113 (a seven-component contradiction between the figure spec and c4-component.md), and TASK-114 (review of the automated container and context revisions, which restored claude-cli to the documented consent boundary). Patch rather than minor: no code, schema, output contract or dependency changes, only documentation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The full suite runs before the release documentation is written, and any failure is either fixed or shown to be the known Windows-only test_setup_deploy.py flake recorded in TASK-116
- [x] #2 CHANGELOG.md carries a dated 0.26.1 section and both compare links at the bottom are updated
- [x] #3 README.md and README.nl.md are updated together in the same commit, never one without the other
- [x] #4 The documentation subset gate passes after the changelog and README edits
- [x] #5 A pull request is opened against origin/main, CI is green, and every Copilot review comment is checked against the code rather than dismissed
- [x] #6 The tag is placed on a SHA verified to be on origin/main after the merge, not on a branch tip
- [x] #7 The published release body is verified non-empty
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Released v0.26.1 (tag b9130e0, verified equal to origin/main after merging PR #91). Documentation-only patch correcting the C4 set that shipped in v0.26.0.

The load-bearing correction is the consent boundary: claude-cli had been removed from it and OpenRouter asserted as the only route to cloud generation. CLOUD_PROVIDERS is {openrouter, claude-cli} and claude-cli shells out to the claude binary. It is also the provider neither installer offers, so it carries no configuration-time warning and is exactly the path a reader most needs told about. Restored, and the previously open question about a per-call warning is now answered from code (scripts/_llm.py:164-168, broader coverage than setup.sh:225).

Also fixed: vault folder count (five named, ten exist), the claim that all four databases rebuild (kb-usage.db does not), a named Atlas lens that was removed under TASK-27.18 and already documented as gone elsewhere in the same set, two support facts about the detached index worker, two geometry errors in the plate specification, and two counting errors that each contradicted nearby text.

Changed rather than fixed: the plate no longer quotes an exact test count. It said 1099, the suite now collects 1112. The same figure appears five more times in c4-code-github-workflows.md where it underpins an analysis rather than sitting in a label, so that is TASK-123 rather than a drive-by edit.

Gates: full suite 1110 passed, 2 skipped, zero failures in 8m56, with the Windows-only test_setup_deploy.py flake from TASK-116 not reproducing. Documentation subset after the changelog and README edits: 56 passed. CI green on PR #91 (test 1m25s, atlas 26s). Release body verified at 3470 bytes.

Copilot review was unavailable, not skipped: the bot replied that the requesting account has reached its quota limit, the same condition TASK-115 recorded on every PR that day. The merge therefore rests on green CI, the local full and targeted suites, and the fact that each correction was verified against source before it was written.

One premise in TASK-114 did not survive contact and is recorded there rather than quietly dropped: components do not map one-to-one onto containers, and the container document never claimed they did.
<!-- SECTION:FINAL_SUMMARY:END -->
