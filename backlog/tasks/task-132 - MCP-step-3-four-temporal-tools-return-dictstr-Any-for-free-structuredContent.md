---
id: TASK-132
title: >-
  MCP step 3: four temporal tools return dict[str, Any] for free
  structuredContent
status: Done
assignee: []
created_date: '2026-08-03 22:09'
updated_date: '2026-08-03 22:10'
labels:
  - mcp
dependencies:
  - TASK-100
modified_files:
  - scripts/kb-mcp.py
  - tests/test_kb_mcp.py
priority: medium
ordinal: 127700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan §3.2 step 3 (docs/superpowers/plans/mcp-2026-07-28-migration.md line 489). Identified as the still-open, still-valid piece of work while TASK-107 was found to be superseded by the same plan's D7 decision -- TASK-107's own comment names this as "being done separately."

what_did_i_do_tool, timeline_tool, weeklog_tool, topic_timeline_tool and _activity_unavailable changed from `-> str` (JSON-stringified via _activity_json) to `-> dict[str, Any]`, returning activity.*()'s result directly. _activity_json deleted along with the now-unused `import json`. The four `@srv.tool()` wrappers mirror the return annotation. No `structured_output=` kwarg passed (does not exist on mcp 1.9.4, per the plan). Result: `structuredContent` + `outputSchema` come free from the SDK's return-annotation auto-detection on 1.28.1/2.0.0, with `content` unchanged on 1.9.4 (dict serialises to the same text per the plan's measured byte-identity claim).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Four *_tool functions and _activity_unavailable return dict[str, Any], not str
- [x] #2 _activity_json deleted, no remaining call sites, unused `import json` removed
- [x] #3 Four @srv.tool() wrappers' return annotations mirror the change
- [x] #4 tests/test_kb_mcp.py::test_temporal_tool_wrappers_return_json rewritten to test_temporal_tool_wrappers_return_dicts, asserting dicts plus the json.dumps(indent=2, ensure_ascii=False) byte-identity pin
- [x] #5 Full pytest suite green
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Done exactly as scoped in the plan (~30 lines in kb-mcp.py, ~15 in the test). Full suite: 1129 passed, 2 skipped (python -m pytest tests -q, 2026-08-04). No client-visible behaviour change on the current pin (mcp 1.28.1) since content stays byte-identical; structuredContent/outputSchema become available for clients that read them once the SDK emits them.
<!-- SECTION:FINAL_SUMMARY:END -->
