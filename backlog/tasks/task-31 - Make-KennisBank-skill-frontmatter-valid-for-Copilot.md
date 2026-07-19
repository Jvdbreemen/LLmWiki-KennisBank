---
id: TASK-31
title: Make KennisBank skill frontmatter valid for Copilot
status: Done
assignee:
  - Codex
created_date: '2026-07-19 07:19'
updated_date: '2026-07-19 07:36'
labels:
  - bug
  - skills
  - copilot
  - yaml
dependencies: []
documentation:
  - AGENTS.md
modified_files:
  - skills/kennisbank-upgrade/SKILL.md
  - skills/kennisbank-contribute/SKILL.md
  - tests/test_skill_frontmatter.py
priority: high
ordinal: 49000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Quote or fold YAML description scalars for the kennisbank-upgrade and kennisbank-contribute skills so GitHub Copilot CLI can parse them. Add regression coverage using a real YAML parser when available through the supported test environment, validate all shipped skill manifests, and redeploy through setup.sh so the personal skill copies are repaired without hand-copying.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Both affected source SKILL.md files have valid YAML frontmatter and retain their trigger descriptions.
- [x] #2 Regression coverage parses every shipped skill frontmatter with YAML semantics that reject the original colon-space defect.
- [x] #3 Existing skill structure and agent-environment installation tests pass.
- [x] #4 The supported setup path redeploys the corrected skills to ~/.agents/skills without overwriting unrelated personal content.
- [x] #5 copilot skill list reports neither KennisBank skill as failed after redeployment.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Update only the two invalid description scalars using YAML folded blocks, preserving their full trigger text. 2. Strengthen the existing skill-frontmatter test to parse every shipped skill with the same YAML rules Copilot expects, while preserving compatibility with the repository's test environment. 3. Run focused skill and installer tests, then the relevant broader suite. 4. Run setup.sh with KENNISBANK_VAULT=D:/Users/Robert/Documents/Claude/Projects/Kluis and the currently configured agent targets needed to redeploy shared personal skills. 5. Verify Copilot lists both skills cleanly, record evidence, and mark the task Done.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented folded YAML description scalars for kennisbank-upgrade and kennisbank-contribute, preserving trigger phrases. Replaced the permissive frontmatter test with a strict top-level skill-manifest parser that rejects the original unquoted colon-space defect, accepts quoted/folded values, and validates every shipped skill. Verification: 5 skill-frontmatter tests passed; 10 agent-environment installer tests passed; the targeted setup deployment test passed; both source and deployed skills passed skill-creator quick_validate; deployed SHA-256 hashes match source; copilot skill list reports both skills with no failures. Live setup.sh --yes --agents copilot --skip-model-check installed 3 shared skills and agent validation passed. Its final doctor gate found one unrelated existing-vault failure: two wiki articles have missing/dangling provenance. Broader suite: 739 passed, 2 skipped, 4 unrelated failures in test_copilot_doctor (2), test_kb_mcp (MCP 1.28 annotation handling), and test_safe_edit (no-op exit code).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed the two KennisBank skills that GitHub Copilot rejected by moving their long descriptions to valid folded YAML scalars. Added regression coverage for the exact colon-space parsing failure and all shipped skill manifests. Redeployed through the supported setup path to ~/.agents/skills and verified byte-identical installed files, valid skill manifests, and a clean Copilot skill catalog. Focused tests pass; broader unrelated baseline failures and the existing vault provenance-lint failure are documented in the implementation notes.
<!-- SECTION:FINAL_SUMMARY:END -->
