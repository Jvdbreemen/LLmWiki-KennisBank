---
id: TASK-104
title: 'MCP step 4: English tool descriptions (names unchanged)'
status: To Do
assignee: []
created_date: '2026-07-29 22:48'
labels: []
dependencies:
  - TASK-103
ordinal: 107700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan §3.2 step 4. Tool descriptions are the selection signal a model reads when choosing between eight similarly-shaped tools, and the repo language policy makes English the default. Translate the eight docstrings inside build_server() (kb-mcp.py:270-271, 277-278, 283-284, 289-291, 297-298, 305, 312, 319) and INSTRUCTIONS_TEXT (:245-259) to English. Tool NAMES and parameter names stay exactly as they are: renaming is the one change here that could break a user's existing prompts and six shipped client configs for no retrieval gain. Genuine hazard to fix while here: the weeklog and timeline descriptions currently read almost identically, which makes tool selection a coin flip.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 All eight tool docstrings and INSTRUCTIONS_TEXT are English
- [ ] #2 Tool names and parameter names are byte-identical to before
- [ ] #3 Test asserts every registered tool has a non-empty description
- [ ] #4 Test asserts the weeklog and timeline descriptions are not near-duplicates
- [ ] #5 pytest suite green
<!-- AC:END -->
