---
id: TASK-151
title: Release v0.29.0
status: Done
assignee: []
created_date: '2026-08-13 04:54'
updated_date: '2026-08-13 05:05'
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
- [x] #1 Changelog section dated and written for readers, with both compare links updated
- [x] #2 README.md and README.nl.md highlight sections updated in the same edit
- [x] #3 Full suite green before the documentation edits, documentation subset green after
- [x] #4 Copilot review processed before the merge
- [x] #5 Tag placed on a SHA verified to be on origin/main, never on a branch tip
- [x] #6 Release published with a non-empty body, verified
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Published 2026-08-13: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.29.0

  merge verified   ee8c3fd is an ancestor of origin/main
  tag              1cb608d == origin/main, identical
  release body     10731 characters, not a draft
  CI               full suite green on Linux (1m3s)
  Copilot review   4 of 4 files, no comments

On the gate: the local full suite was green at 1251 passed on commit 28ea0bb, and `git diff --stat 28ea0bb HEAD -- scripts/ tests/ setup.sh` is empty -- every change after that point is markdown. The documentation subset passed 56 after the doc edits. Two attempted re-runs of the full local suite were interrupted externally; rather than release on an unknown result, the released code was shown to be byte-identical to the code that last passed, and CI re-ran the whole suite on the PR anyway.

A killed gate is not a red gate, but it is not a green one either. The way out was evidence that the question had already been answered, not a shrug.
<!-- SECTION:NOTES:END -->
