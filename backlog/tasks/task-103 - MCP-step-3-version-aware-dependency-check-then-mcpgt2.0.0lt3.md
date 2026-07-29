---
id: TASK-103
title: 'MCP step 3: version-aware dependency check, then mcp&gt;=2.0.0,&lt;3'
status: To Do
assignee: []
created_date: '2026-07-29 22:46'
labels: []
dependencies:
  - TASK-102
ordinal: 106700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan §3.2 step 3. The only step that changes wire behaviour, hence gated behind the step-2 harness. Three changes that only make sense together: (1) setup.sh:276-286 install_python_dep must compare the INSTALLED version against the spec rather than merely checking find_spec presence at line 280 (measured drift: mcp 1.9.4 present while requirements pinned 1.28.1); (2) setup.sh:290-292 must install the SDK whenever kb-mcp.py is registered for any agent, not only for codex/opencode/copilot; (3) requirements.txt:2 mcp==1.28.1 becomes mcp>=2.0.0,<3 — a range, not a pin, because the 1.x line is in maintenance mode receiving security fixes only while every fresh pip install lands on 2.x anyway. Keep the dual-path import at kb-mcp.py:43-49 exactly as it is: that is what makes this reversible and keeps a machine still carrying 1.x working through rollout. Python floor is unchanged (v2.0.0 requires-python >=3.10, same as v1). Note the dependency on the SDK's dual-era serving is a MAY in the spec, not a guarantee, so it must be proven rather than assumed — see TASK-109.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 setup.sh compares installed version against the requirement spec, not just module presence
- [ ] #2 setup.sh installs the SDK whenever kb-mcp.py is registered for any agent
- [ ] #3 requirements.txt uses mcp>=2.0.0,<3 and the dual-path import at kb-mcp.py:43-49 is unchanged
- [ ] #4 The step-2 harness passes the legacy initialize flow against the new pin (the dual-era proof)
- [ ] #5 install-agent-envs.py:822-850 embedded client validator still reports a successful MCP handshake under the new pin
- [ ] #6 pytest suite green
<!-- AC:END -->
