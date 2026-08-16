---
id: TASK-108
title: 'MCP: validation evidence — legacy era proven, modern era still gated'
status: To Do
assignee: []
created_date: '2026-07-29 22:51'
updated_date: '2026-07-30 05:35'
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
- [x] #7 All transcripts stored as an evidence document under docs/, referenced from the plan
- [x] #8 Any conformance gap found is recorded as a finding rather than smoothed over
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PROVEN NOW, on the current pin (mcp 1.28.1, Python 3.14.2), captured in docs/superpowers/plans/mcp-2026-07-28-evidence.md and asserted by tests/test_kb_mcp_wire.py: the legacy initialize handshake succeeds; tools/list returns exactly the eight expected names; tools/call returns content; all eight annotation sets arrive on the wire with the correct readOnlyHint and destructiveHint values; instructions are advertised in the initialize result; and every byte the server writes to stdout parses as JSON-RPC 2.0.

NOT PROVEN, and deliberately not attempted: server/discover, the required resultType, and ttlMs/cacheScope on the CacheableResult types. Those are modern-era claims that need mcp 2.x, and the definitive plan gates the pin bump on a measurement (TASK-110) because a modern-only server dies against every client currently in use. Attempting the throwaway-venv validation now would prove a configuration we have decided not to ship yet; it moves with TASK-110.

Also recorded rather than smoothed over: the earlier brief contained three claims that the verification pass refuted - mcp 2.0.0 does have field time (a seven-week public pre-release train; the real gap is zero post-GA patches), GitHub Copilot DOES support MCP resources on both surfaces (the opposite claim lived in kb-mcp.py and README.md and was the stated justification for the instructions= work, now corrected in the source), and DiscoverResult.instructions is unreachable in every client inspected, so the copilot-instructions duplication stays.
<!-- SECTION:NOTES:END -->

## Close-out (2026-08-16) — superseded

The provable half shipped: the legacy-era wire evidence is stored in docs/superpowers/plans/mcp-2026-07-28-evidence.md, permanently asserted by tests/test_kb_mcp_wire.py, and released in v0.26.0. The unproven half (ACs #1-6: server/discover, resultType, ttlMs/cacheScope under mcp 2.x) was deliberately not attempted because it would validate a configuration the plan decided not to ship; that exact scope is embedded in TASK-110 (modern-era wire assertions, dual-era proof AC#3, validator re-run AC#4). Closing this task loses nothing — the evidence is in the repo and the gated remainder travels with TASK-110.

**Evidence:** docs/superpowers/plans/mcp-2026-07-28-evidence.md (wire transcript captured 2026-07-30 on mcp 1.28.1); tests/test_kb_mcp_wire.py (asserts every claim); CHANGELOG.md [0.26.0] 2026-07-30 ('A wire-level MCP test harness' under Added; 'Not in this release, on purpose' section); TASK-110 description and ACs #3/#4 carry the modern-era wire assertions, dual-era proof, and install-agent-envs.py validator re-run.
