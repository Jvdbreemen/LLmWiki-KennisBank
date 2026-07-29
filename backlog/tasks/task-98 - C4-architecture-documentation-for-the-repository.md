---
id: TASK-98
title: C4 architecture documentation for the repository
status: In Progress
assignee: []
created_date: '2026-07-29 21:11'
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
- [ ] #1 Every real code directory has a c4-code-*.md file
- [ ] #2 Component docs with interfaces plus master c4-component.md index
- [ ] #3 c4-container.md with deployment mapping and OpenAPI specs for the sidecar API
- [ ] #4 c4-context.md with personas, user journeys and external systems
- [ ] #5 All output under C4-Documentation/
<!-- AC:END -->
