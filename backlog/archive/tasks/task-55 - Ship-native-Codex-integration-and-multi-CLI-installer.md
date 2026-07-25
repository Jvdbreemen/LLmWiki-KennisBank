---
id: TASK-55
title: Ship native Codex integration and multi-CLI installer
status: In Progress
assignee:
  - codex
created_date: '2026-07-18 11:27'
labels:
  - codex
  - integration
  - installer
  - release
dependencies: []
references:
  - 'https://github.com/rvdbreemen/adr-kit'
documentation:
  - README.md
  - INSTALL.md
  - CONTRIBUTING.md
  - 'https://learn.chatgpt.com/docs/build-plugins'
  - 'https://learn.chatgpt.com/docs/build-skills'
modified_files:
  - .codex-plugin/plugin.json
  - scripts/install-agent-envs.py
  - tests/test_install_agent_envs.py
  - tests/test_codex_plugin.py
  - README.md
  - INSTALL.md
  - CHANGELOG.md
priority: high
ordinal: 49000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add a first-class, separately packaged Codex integration for adr-kit without changing or regressing the existing Claude Code plugin. Provide an idempotent installer that detects actual Claude Code, Codex, and standalone GitHub Copilot CLI executables and installs the correct integration for every detected client. Complete the work as one focused release including documentation, live client validation, merge, and GitHub release notes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A valid `.codex-plugin/plugin.json` exposes ADR-kit Codex skills and the existing key-free MCP tools without relying on Claude Code plugin-cache paths.
- [ ] #2 The Codex solution is additive and separate: existing `.claude-plugin` manifests, hooks, commands, and install behavior remain valid and regression-tested.
- [ ] #3 An idempotent cross-platform installer detects executable Claude Code, Codex, and standalone GitHub Copilot CLIs and installs the correct native integration for each detected client.
- [ ] #4 Installer dry-run, explicit client selection, missing-client behavior, repeated runs, paths with spaces, and Windows command resolution are covered by automated tests.
- [ ] #5 README and INSTALL documentation explain client detection, install commands, Codex skill invocation, Copilot usage, upgrades, and troubleshooting.
- [ ] #6 The Codex plugin validates with the official validator, installs through a local marketplace, and is exercised in a fresh Codex process including bundled skills and MCP tool discovery.
- [ ] #7 Claude Code and Copilot integrations receive client-specific smoke validation without overwriting unmanaged user configuration.
- [ ] #8 The full relevant automated test suite, manifest/schema checks, ADR lint/doctor gates, and release smoke tests pass before merge.
- [ ] #9 Version metadata and CHANGELOG are updated consistently, a reviewed PR is merged to main, and a GitHub release with release text is published.
<!-- AC:END -->
