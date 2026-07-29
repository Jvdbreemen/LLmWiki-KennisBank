---
id: TASK-108
title: 'MCP: validate the 2026-07-28 upgrade and store the evidence'
status: To Do
assignee: []
created_date: '2026-07-29 22:51'
labels: []
dependencies:
  - TASK-103
ordinal: 111700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan §3.2 step 3 verification plus §7 open questions. The backward compatibility this migration relies on is an SDK property, not a spec guarantee: the revision says a dual-era server MAY serve both eras, so it must be proven rather than assumed. Close the open questions with one throwaway virtualenv carrying mcp 2.0.0, driving kb-mcp.py over the wire, and record the transcripts as durable evidence in the repo. Questions to close: (a) does the SDK auto-emit resultType on every result and ttlMs/cacheScope on the CacheableResult types (tools/list, resources/list, resources/read) — if not, we are silently non-conformant and this becomes bump-the-pin-and-file-an-issue; (b) does server/discover advertise supportedVersions and capabilities correctly; (c) does an unsupported requested version return -32022 with data.supported/data.requested; (d) does the legacy initialize flow still succeed against the same executable (the dual-era proof); (e) does the installer's embedded client validator at install-agent-envs.py:822-850 still report a successful handshake. Evidence goes in the repo, not only in a task note.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Throwaway venv with mcp 2.0.0 created and its exact resolved version recorded
- [ ] #2 server/discover result captured showing resultType, supportedVersions, capabilities, ttlMs and cacheScope
- [ ] #3 Unsupported-version request captured showing error -32022 with data.supported and data.requested
- [ ] #4 Legacy initialize flow captured succeeding against the same executable
- [ ] #5 tools/list result captured showing ttlMs and cacheScope
- [ ] #6 install-agent-envs.py client validator run and its result recorded
- [ ] #7 All transcripts stored as an evidence document under docs/, referenced from the plan
- [ ] #8 Any conformance gap found is recorded as a finding rather than smoothed over
<!-- AC:END -->
