---
id: TASK-109
title: 'MCP step 8: documentation, changelog and release'
status: To Do
assignee: []
created_date: '2026-07-29 22:51'
labels: []
dependencies:
  - TASK-104
  - TASK-105
  - TASK-106
  - TASK-107
  - TASK-108
ordinal: 112700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan §3.2 step 8. Lands last, after the code and the evidence. Correct the stale tool count in README.md:534 (says six, was eight, becomes ten after TASK-106), document the new tools and the capture provenance parameters, state the mcp>=2.0.0,<3 requirement and the Python 3.10 floor, and record what the validation in TASK-108 actually proved — including any conformance gap found, rather than only the good news. Both README variants must move together per the repo rule that the Dutch file is a co-edited translation and not a fork. Then the release: changelog section, PR upstream, process the review, merge, verify origin/main contains the merge, tag that SHA, publish.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 README.md and README.nl.md both updated: tool count corrected, new tools and capture parameters documented, dependency requirement and Python floor stated
- [ ] #2 CHANGELOG section written describing the behaviour change and what the validation proved
- [ ] #3 Any conformance gap from TASK-108 is stated in the changelog, not omitted
- [ ] #4 PR opened upstream, review processed, merged, and origin/main verified to contain the merge before tagging
- [ ] #5 Release published on the verified tag
<!-- AC:END -->
