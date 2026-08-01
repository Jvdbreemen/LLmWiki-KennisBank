---
id: TASK-125
title: Release v0.27.0
status: Done
assignee: []
created_date: '2026-07-31 21:42'
updated_date: '2026-08-01 08:55'
labels:
  - release
dependencies: []
modified_files:
  - CHANGELOG.md
  - README.md
  - README.nl.md
priority: high
ordinal: 121700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Release v0.27.0 from origin/main (56f69ec). Minor, not patch: the delta since v0.26.1 changes two output contracts and refuses a configuration that used to work.

Carried work:

- PR #92, TASK-117/118/120/121 — the four criticals from the comprehensive script-layer review. Embedding endpoint locality enforced at the sink (`KB_EMBED_ALLOW_REMOTE` to override), the vacuous no-cloud guard repaired, `_memory.set_status` frontmatter corruption fixed, the 6.8 s / 186 MB hot-path JSON fallback deleted in favour of a sentinel plus a visible notice, and sqlite-vec loaded without dragging in numpy (355 ms -> 0.6 ms).
- PR #93, TASK-119/116/98 — capture can no longer erase a human-approved memory; MCP capture stops reporting success for a byte-identical re-capture that wrote nothing.
- PR #94, TASK-124 — `setup.sh --skip-doctor` keeps the local gate affordable (-92.9 s on tests/test_setup_deploy.py).

Version rationale: the release skill classifies a changed output contract as minor. The hot-path fallback removal changes what a user sees when the index is missing, the MCP capture response changed, and a remote embedding endpoint that previously worked is now refused without an explicit opt-in.

Known deviation: the Copilot review is unavailable, not skipped — the bot reports the requesting account has reached its quota limit, the same condition recorded for v0.26.1 (TASK-122) and TASK-115. Record it in the release rather than implying the step ran.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Full suite green on the code being released, before the documentation edits
- [x] #2 CHANGELOG.md has a dated 0.27.0 section and both compare links updated
- [x] #3 README.md and README.nl.md highlight sections updated in the same commit, both languages
- [x] #4 Documentation test subset green after the doc edits
- [x] #5 PR opened against origin, CI green, review status recorded honestly
- [x] #6 Tag v0.27.0 placed on a SHA verified to be on origin/main after the merge
- [x] #7 GitHub release published and its body verified non-empty
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
v0.27.0 released. Tag v0.27.0 on 3d536c2ef8132e42a51eb8c690000362fb12a3dd, verified equal to origin/main after merging PR #95; `git rev-list -n1 v0.27.0` matched the SHA before publishing. Release body published and verified non-empty at 5001 characters.

Gate: full suite on the released code (56f69ec) 1123 passed, 2 skipped; documentation subset after the doc edits 56 passed; CI on PR #95 green (atlas 26 s, test 1 m 0 s).

Version rationale: minor rather than patch because three observable contracts changed — a non-loopback embedding endpoint for a local provider is now refused unless KB_EMBED_ALLOW_REMOTE is set, a missing index returns a sentinel plus the cold-model notice instead of the 6766 ms / 186 MB JSON fallback, and MCP capture no longer reports success for a byte-identical re-capture.

Copilot review was unavailable rather than skipped: the bot reported the requesting account has reached its quota limit on both PR #94 and PR #95, the same condition recorded for v0.26.1 (TASK-122) and TASK-115. The release rests on green CI, the local full suite, and per-finding reproduction before and after each fix.
<!-- SECTION:FINAL_SUMMARY:END -->
