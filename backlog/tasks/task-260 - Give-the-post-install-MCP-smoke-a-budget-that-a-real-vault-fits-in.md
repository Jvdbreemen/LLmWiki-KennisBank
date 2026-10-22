---
id: TASK-260
title: >-
  Make the post-install MCP smoke model-free and give it a budget a busy machine
  fits in
status: In Progress
assignee: []
created_date: '2026-10-21T22:54:00Z'
updated_date: '2026-10-21T23:21:00Z'
labels:
  - setup
  - mcp
  - windows
dependencies: []
priority: high
ordinal: 194600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
validate_mcp_runtime and the interpreter probe each cap at 15 s. Measured 2026-10-22 on Windows: the handshake smoke takes 8.6-9.0 s idle on a real vault (client imports 3.3 s, server import 2.6 s, three tool calls), 4.1 s on an empty one. TASK-116 measured 10.03 s and removed the budget from the tests only; production setup still aborts with 'Post-install validatie faalde' whenever the machine is busy, though the install itself succeeded. Observed 2026-10-21 for --agents omp and --agents codex. The smoke waits on legitimate first-start work, not on a hang.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Default budget fits a real vault with load headroom; a hang is still caught
- [x] #2 KENNISBANK_MCP_SMOKE_TIMEOUT overrides it
- [x] #3 A timeout message names the budget, the override and that the install itself completed
- [x] #4 Tests cover the default, the override and the message
- [x] #5 The smoke never reaches the embedder, also with the explicit recall routes enabled
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause, reproduced 2026-10-22: the smoke called experience_recall/source_recall with real queries. With source_explicit_recall and experience_explicit_recall enabled (true in the maintainer's vault after the upgrade prompt), each query embeds via Ollama (_embeddings.embed_query, 30 s urllib timeout, applied per resolved address for localhost). Observed: Ollama stalled ('ollama ps' -> timed out waiting for server to start) and setup failed for --agents omp and codex; validate_mcp_runtime took 64.1 s. Reproduced with KB_EMBED_ENDPOINT pointed at a TCP listener that accepts and never answers: 36.8 s before the change. After sending empty queries (both routes return status 'invalid' before embedding): 4.9-8.5 s, zero connections to the stalled embedder, across 9 runs. Budget: probe 3.1 s, handshake 4.9-8.5 s idle; raised 15 -> 60 s with KENNISBANK_MCP_SMOKE_TIMEOUT override for load (TASK-116 evidence). One unexplained 182 s run occurred once after the change and did not reproduce in 9 later runs; the 60 s budget and message cover it but its cause is not established.
<!-- SECTION:NOTES:END -->
