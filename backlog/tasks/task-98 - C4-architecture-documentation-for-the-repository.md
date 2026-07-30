---
id: TASK-98
title: C4 architecture documentation for the repository
status: In Progress
assignee: []
created_date: '2026-07-29 21:11'
updated_date: '2026-07-29 22:41'
labels: []
dependencies: []
ordinal: 101700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Generate a complete C4 documentation set (Code, Component, Container, Context) in C4-Documentation/ using the c4-architecture plugin agents, bottom-up. Repo is a distribution of local-first tooling: scripts/ (86 python/shell scripts), adapters/, atlas/ (Tauri app: Rust shell + JS frontend + Python sidecar), tests/, commands/, skills/, templates/, docs/, .github/workflows.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every real code directory has a c4-code-*.md file
- [x] #2 Component docs with interfaces plus master c4-component.md index
- [x] #3 c4-container.md with deployment mapping and OpenAPI specs for the sidecar API
- [x] #4 c4-context.md with personas, user journeys and external systems
- [x] #5 All output under C4-Documentation/
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Generated with 30 agents bottom-up: 20 code-level docs, 7 components + master index, container level (with apis/atlas-sidecar-api.yaml and apis/kb-mcp-tools.md), context level with personas and journeys. Also wrote figure-spec-architecture-overview.md, a dimensioned drawing spec for one high-level plate.

Running the doc-consistency guards against the generated documents exposed two guard-precision bugs and two real documentation errors - the CLAUDE.md lesson that a guard may not cover what it claims. GUARD BUG 1: test_documented_tool_output_uses_real_markers fired on any document mentioning doctor.sh that also contained '[warn]' anywhere; build-karpathy-index.py really prints [warn]/[error] to stderr (:327,:527), so truthful documentation tripped it. Narrowed to fenced blocks that actually show a doctor run, with 'Done. 0 errors' still flagged anywhere; verified by probing with a fabricated doctor transcript, which still fails. GUARD BUG 2: test_documented_env_vars_are_read_somewhere excluded tests/ from 'code', so KB_INTEGRATION (tests/test_kb_retrieve_memory.py:137) and KB_COPILOT_LIVE (tests/test_copilot_e2e.py:136) counted as ghosts; tests/*.py added as a source, and COPILOT_CUSTOM_INSTRUCTIONS_DIRS + COPILOT_OFFLINE moved to the external allowlist as standalone Copilot CLI knobs per ADR-0003.

REAL ERROR 1: the Copilot capture kill switch is KENNISBANK_COPILOT_NO_CAPTURE (kb-copilot-capture.py:198), not KB_NO_CAPTURE as the generated doc claimed. Fixed. REAL ERROR 2 (pre-existing, in a decision record): ADR-0001 cites an OLLAMA_MODEL default in scripts/semantic-tiling.py which the script does not read (it reads TILING_THRESHOLD_ERROR/TILING_THRESHOLD_REVIEW). Recorded in the C4 document rather than repeated as fact; ADR-0001 itself left untouched, since editing a decision record is the owner's call.

Open point carried forward from the component synthesis: four shared modules (_common.py, _migrations.py, _transcript.py, _liteparse.py) are consumed by several components but claimed as owned code by none. Documented as an open question in c4-component.md rather than silently assigned.
<!-- SECTION:NOTES:END -->
