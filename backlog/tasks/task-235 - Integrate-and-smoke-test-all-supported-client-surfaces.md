---
id: TASK-235
title: Integrate and smoke-test all supported client surfaces
status: Done
assignee: []
created_date: '2026-09-04 00:00'
labels:
  - multi-client
  - documentation
  - setup
  - smoke-test
dependencies:
  - TASK-233
  - TASK-234
ordinal: 177400
---

## Description

Ship identical product semantics to every supported client surface. Update
setup/upgrade assets, commands, MCP instructions, README/C4/configuration, and
known limitations. A client without the optional runtime must fail open and
must not lose normal KennisBank recall.

## Acceptance Criteria

- [x] #1 Claude Code, Codex, OpenCode, and Copilot receive the correct scripts, commands/instructions, flags, and local vault configuration where supported
- [x] #2 Each supported explicit source and experience surface is smoke-tested, not merely copied
- [x] #3 Tool descriptions teach experience-first retrieval and source-on-demand evidence without suggesting automatic advisories
- [x] #4 README variants, C4 diagrams, settings docs, command docs, upgrade note, and rollback note agree on shipped behavior
- [x] #5 Missing MCP SDK, Ollama, vector extension, or projection fails open without affecting ordinary recall
- [x] #6 Generated/deployed client artifacts have parity tests and no stale experimental route text

## Evidence

Record client-by-client artifact paths, discovery output, smoke results, and
any explicitly unsupported surface.

See `docs/research/projection-client-surface-evidence-2026-09-07.md`.
