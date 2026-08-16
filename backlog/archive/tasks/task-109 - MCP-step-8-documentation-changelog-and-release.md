---
id: TASK-109
title: 'MCP step 8: documentation, changelog and release'
status: To Do
assignee: []
created_date: '2026-07-29 22:51'
updated_date: '2026-08-03 22:13'
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

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-08-03 22:13
---
2026-08-03 sweep: TASK-106 in this task's dependency list does not exist as a backlog task (mcp__backlog__task_search confirms no TASK-106) -- the same phantom-dependency pattern already found on TASK-107 (which listed a non-existent TASK-103). Both point at the same root cause: this task's dependency list and its 'step N' framing were pinned to an earlier revision of docs/superpowers/plans/mcp-2026-07-28-migration.md, which the plan document itself says it supersedes (see its own line 3-4). TASK-104 and TASK-105 (both real, both Done) satisfy what the plan's current step 4/5 actually ask for.
---

created: 2026-08-03 22:13
---
The real, non-phantom blocker is unchanged: TASK-108's ACs #1-6 (modern-era SDK proof) are gated on TASK-110 (pin bump to mcp>=2), and TASK-110 stays explicitly blocked pending a named client + stated necessity (none supplied as of this sweep). TASK-109's own AC#1 asks to 'state the mcp>=2.0.0,<3 requirement' -- writing that into README/CHANGELOG before TASK-110 actually fires would document a requirement that is not yet true. This task cannot be started, let alone closed, before TASK-110 resolves. Left as To Do; the step-3 work its dependency chain implicitly wanted is done separately as TASK-132.
---
<!-- COMMENTS:END -->
