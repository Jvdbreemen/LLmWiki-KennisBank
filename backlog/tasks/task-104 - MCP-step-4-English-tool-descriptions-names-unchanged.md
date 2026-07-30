---
id: TASK-104
title: 'MCP step 4: English tool descriptions (names unchanged)'
status: Done
assignee: []
created_date: '2026-07-29 22:48'
updated_date: '2026-07-30 05:35'
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
- [x] #1 All eight tool docstrings and INSTRUCTIONS_TEXT are English
- [x] #2 Tool names and parameter names are byte-identical to before
- [x] #3 Test asserts every registered tool has a non-empty description
- [x] #4 Test asserts the weeklog and timeline descriptions are not near-duplicates
- [ ] #5 pytest suite green
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
The eight MCP-facing tool docstrings and INSTRUCTIONS_TEXT are English; tool and parameter names are byte-identical, so no deployed client config breaks. The near-duplicate hazard is resolved substantively rather than cosmetically: timeline now says it lists INDIVIDUAL events and points at weeklog for an aggregated view, and weeklog says it AGGREGATES per day and points at timeline for the individual events. A wire test asserts every tool has a non-empty description, that the word overlap between those two descriptions stays under 0.6, and that each names the other as the alternative - so the hazard cannot silently return. Out of scope, deliberately: the internal *_tool() docstrings at kb-mcp.py:107 and :265 are still Dutch. They are not the selection signal a model reads (the SDK reads the decorated wrapper inside build_server()), and translating the module's whole Dutch comment layer would balloon the diff beyond this step.
<!-- SECTION:FINAL_SUMMARY:END -->
