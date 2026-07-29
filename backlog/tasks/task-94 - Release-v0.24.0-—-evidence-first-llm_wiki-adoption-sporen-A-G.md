---
id: TASK-94
title: Release v0.24.0 — evidence-first llm_wiki adoption (sporen A-G)
status: Done
assignee: []
created_date: '2026-07-29 04:52'
updated_date: '2026-07-29 05:17'
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
- [x] #1 Full suite green on released code
- [x] #2 Changelog v0.24.0 section + compare links
- [x] #3 README highlights EN+NL co-edited
- [x] #4 Docs-subset gate green after steps 2-3
- [x] #5 PR merged and verified on origin/main
- [x] #6 Tag on verified origin/main SHA only
- [x] #7 GitHub release published with non-empty body
- [x] #8 Release task + carried tasks closed
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
v0.24.0 released. Full suite green pre-docs (1089 passed, 8m11s); docs-subset gate green post-edit (56). Changelog section + compare links + README highlights EN/NL co-edited (PR #83, merge 5a5c73e verified on origin/main before tagging). Tag v0.24.0 on 5a5c73e, rev-list check equal. GitHub release published, body 10125 chars verified non-empty. Copilot review unavailable on both PR #82 and #83 (quota); merged with green gate under the standing user instruction (TASK-85 precedent). Carried tasks TASK-86/87/88/90 Done with recorded evidence; TASK-84/85 fixes included; TASK-89/91/92 remain In Progress on small human-evidence ACs; TASK-93 (legacy removal) starts its one-release clock now.
<!-- SECTION:FINAL_SUMMARY:END -->
