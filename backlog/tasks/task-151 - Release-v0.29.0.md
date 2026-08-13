---
id: TASK-151
title: Release v0.29.0
status: In Progress
assignee: []
created_date: '2026-08-13 04:54'
updated_date: '2026-08-13 04:55'
labels:
  - release
dependencies: []
priority: high
ordinal: 145700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Minor release. 63 commits since v0.28.0: 16 fix, 12 chore, 8 feat, 8 docs, 3 review, 2 perf.

Minor rather than patch because the default judge model changes (`gemma4:latest` -> `qwen3.5:4b`, which needs an `ollama pull`), capture behaviour changes noticeably, and there are eight `feat:` commits. Nothing breaks the CLI, the commands or the vault layout, so not major.

What this release carries:

- **TASK-143** — the judge is a reasoning model and its thinking ate the answer. `think: false` on both call sites. Measured: 30-56 s per call with one in three returning nothing, against 1.6 s and none empty.
- **TASK-145** — capture read 6 chunks of a session and could parse only one client's transcripts. Codex and Copilot shapes added (39 of 299 transcripts read as empty before, 7 after, 94 MB recovered); caps raised to 40 chunks / 60 memories on measured yield, with a new 150-chunk per-run budget.
- **TASK-148 (half)** — the reconcile pool re-embedded 1506 memories before touching a transcript; it now reads kb-index.db (>600 s -> 16.8 s). Plus `--help` no longer starts a sweep, and the CLI no longer discards the raised cap.
- **TASK-139** — one judge model across all eight surfaces that write one, sized to coexist with the embedder on 16 GB.
- **TASK-140** — single-flight locks handed themselves the lock on Windows 11.7% of the time.
- **TASK-142/144** — the judge-model measurement, and the NOOP misreading both models share.
- **TASK-134/135/133/141** — the L2 scene measurement, compact Copilot MCP output, hook robustness, and the hermeticity-pin finding.

Also ships the recall baseline (`docs/research/recall-baseline-2026-08-13.md`) and the self-correcting memory layer design.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Changelog section dated and written for readers, with both compare links updated
- [ ] #2 README.md and README.nl.md highlight sections updated in the same edit
- [ ] #3 Full suite green before the documentation edits, documentation subset green after
- [ ] #4 Copilot review processed before the merge
- [ ] #5 Tag placed on a SHA verified to be on origin/main, never on a branch tip
- [ ] #6 Release published with a non-empty body, verified
<!-- AC:END -->
