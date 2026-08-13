---
id: TASK-158
title: 'The sweep budget counts chunks, but GPU time is spent on model calls'
status: To Do
assignee: []
created_date: '2026-08-13 21:52'
labels:
  - memory
  - performance
  - measurement
dependencies: []
priority: high
ordinal: 151700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`CHUNK_BUDGET = 150` was added in TASK-145 to bound one sweep run, and its stated purpose is the hot path: the sweep is detached but shares one GPU with the embedding model that serves retrieval, so an unbounded run starves recall for as long as it lasts.

It bounds the wrong unit. A chunk was measured at 6.0 s, but that measurement was `extract` alone. Each chunk yields roughly four candidates, and every candidate then costs an embed, up to three reconcile calls and a judge call — about five more model calls. So the real cost per chunk is closer to 45 s than 6 s, and 150 chunks is not fifteen minutes but nearly two hours.

Measured on the live vault, 2026-08-13: seven transcripts in about fifty minutes, 482 memories written, and the run had not reached its chunk budget when it was stopped.

The ratio also moved underneath the constant. `MAX_MEMORIES_PER_TRANSCRIPT` went from 20 to 60 in the same task that introduced the budget, which triples the number of candidates a chunk can turn into — and therefore triples the model calls a single budgeted chunk can cost. The budget number was chosen against the old ratio and never revisited.

This is the same shape as the progress-bar estimate in TASK-153, which extrapolated from rows in a triangular loop and was wrong by more than a factor of two: counting in a unit that is not the unit the work is actually in.

Count model calls, or wall-clock seconds, instead of chunks. Wall-clock is the more honest one, because it is what the hot path actually competes for and it stays correct when the per-call cost changes again.

The stop must keep the property TASK-145 established: the budget decides whether to START a transcript, never to abandon one, because the watermark is append-only and a half-processed transcript would be marked done and lose the rest.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The budget is expressed in a unit that tracks GPU time (model calls or wall-clock), not chunks
- [ ] #2 The chosen bound is justified against a measurement of a real run, not an estimate of one component
- [ ] #3 The stop still happens only between transcripts, never inside one
- [ ] #4 The heartbeat reports which bound was hit and what was left pending
- [ ] #5 A run that hits the bound is distinguishable in the heartbeat from a run that simply finished
- [ ] #6 python -m pytest tests -q is green
<!-- AC:END -->
