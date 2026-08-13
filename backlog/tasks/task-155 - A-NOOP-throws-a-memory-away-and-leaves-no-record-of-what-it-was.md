---
id: TASK-155
title: A NOOP throws a memory away and leaves no record of what it was
status: To Do
assignee: []
created_date: '2026-08-13 18:34'
labels:
  - memory
  - observability
dependencies: []
priority: medium
ordinal: 149700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Of the three reconcile actions, NOOP is the only one where the candidate memory is not written. The heartbeat counts `reconcile_noop`, so we know how often it happened; nothing anywhere says WHAT was discarded.

That is the same shape as TASK-150 one step earlier in the pipeline. There, a superseded memory existed on disk but appeared in no path a human uses, which is functionally deletion. Here the memory never reaches disk at all, so there is not even a file to reopen.

It matters because NOOP is exactly the action models get wrong. Measured on 20 unrelated pairs with the old prompt, qwen3.5:4b answered NOOP 25% of the time with reasons that said, in so many words, "these are unrelated" — the definition of ADD (TASK-144). The prompt fix took that to 0%, but the mechanism that made the loss invisible is untouched: a future prompt, model or threshold change can reintroduce it and nothing will say so.

Record every discarded candidate the way closures are recorded: title, body, which existing memory covered it, the judge's reason, and the prompt version. `.claude/memory-noop-log.jsonl`, beside `memory-closed-log.jsonl`, with a `memory-doctor.py discarded` view over it. Same rules as the closed log: a record, never a gate — if the log cannot be written, the sweep carries on.

Then the question "is the reconcile seam throwing away good knowledge?" becomes answerable by reading, instead of by re-running a measurement.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every NOOP writes a record with the candidate title and body, the covering memory, the judge's reason and the prompt version
- [ ] #2 memory-doctor.py shows recent discards, with --json for the heartbeat
- [ ] #3 A broken log never blocks the sweep, proven by a test
- [ ] #4 The log is bounded so a long --all rebuild cannot fill the disk
- [ ] #5 python -m pytest tests -q is green
<!-- AC:END -->
