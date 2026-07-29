---
id: TASK-94
title: Release v0.24.0 — evidence-first llm_wiki adoption (sporen A-G)
status: In Progress
assignee: []
created_date: '2026-07-29 04:52'
labels:
  - release
dependencies: []
ordinal: 97700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Release of PR #82 (merge 71cc9f6) plus the two unreleased Atlas fixes (PR #80/#81, TASK-84/85). Carries TASK-86..92: evidence-first eval harness (production parity, 329/1224-question sets, --latency, injection-path test, kb-eval-gen), graph_retrieval default ON (A/B gate passed: wiki @1 0.745->0.790, @5 ->1.000, single-hop@1 +5.4pt), provenance index + coupling experiment (REJECTED, knob off), human review queue outside Atlas + wiki-scan, structural hardening (refusal gate, self-source/index-drift lint, kb-normalize, producer provenance), Atlas heatmap/Cmd+K/facets/JSON-export + CI job, OKF v0.2 export. Proposed version: MINOR (7x feat, schema additions doc_sources/neighbor_log, behaviour flip, new dev dep PyYAML).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Full suite green on released code
- [ ] #2 Changelog v0.24.0 section + compare links
- [ ] #3 README highlights EN+NL co-edited
- [ ] #4 Docs-subset gate green after steps 2-3
- [ ] #5 PR merged and verified on origin/main
- [ ] #6 Tag on verified origin/main SHA only
- [ ] #7 GitHub release published with non-empty body
- [ ] #8 Release task + carried tasks closed
<!-- AC:END -->
