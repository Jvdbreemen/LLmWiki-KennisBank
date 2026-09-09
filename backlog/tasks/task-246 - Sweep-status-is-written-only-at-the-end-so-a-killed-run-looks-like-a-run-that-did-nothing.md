---
id: TASK-246
title: >-
  Sweep status is written only at the end, so a killed run looks like a run that
  did nothing
status: To Do
assignee: []
created_date: '2026-09-09 18:02'
updated_date: '2026-09-09 18:20'
labels: []
dependencies: []
priority: high
type: bug
ordinal: 185600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The sweep writes memory-sweep-status.json only on its terminal paths (scripts/memory-sweep.py:356, :373, :556, :606). The per-transcript loop writes nothing. A run that is killed mid-loop therefore leaves the previous status in place, and every counter reads zero.

Measured on 2026-09-09 in the Kluis vault: the .swept watermark holds 418 stems with mtime 08:25:21 and 170 memory files were written in the last 36 hours, while the status file reports processed 0, written 0, model_unreachable true, last_run 17:36:16. Two killed runs were read as failures on that evidence, and memory-notify reports the same zeros at every session start.

Second effect: the lock release and the status write sit in the same unreached epilogue, so a killed run also leaves a stale lease behind.

Fix direction: write a partial heartbeat after each transcript, marked so a reader can tell a run in progress from a finished one, and skip the rot corpus scan on that path (it costs a full scan of thousands of files and does not depend on the transcript that just finished). Write the file atomically so a kill during the write cannot truncate the JSON.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A heartbeat is written after every processed transcript, not only on the terminal paths
- [ ] #2 The status distinguishes a run that is still going or was interrupted from a finished run
- [ ] #3 The partial write does not run the rot corpus scan and carries the previous rot counts forward
- [ ] #4 The status file is written atomically, so an interrupted write cannot leave truncated JSON
- [ ] #5 A regression test kills a sweep mid-loop and asserts the status reflects the transcripts already done
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Correction to this record, found while reproducing. The description claimed the lock release sits in the same unreached epilogue as the status write. It does not: run_sweep holds the lock through 'with ss.sweep_lock()', so a context manager releases it even when an exception or a SIGINT propagates. Only a hard kill that skips __exit__ leaves a lease behind, and the time-based lease already covers that case. The lock is out of scope here.

Implementation: _write_heartbeat gained a partial flag. Partial writes carry the four rot keys forward from the file on disk instead of rescanning the corpus, and stamp running true; the four terminal paths keep counting rot and stamp running false. The per-transcript finally block writes the partial and keeps pending_left current. Every write now goes through a pid-named tmp plus os.replace, because the partial write lands during the run and a kill during an in-place write leaves unparseable JSON.

Falsified against the pre-fix implementation: 5 of the 6 new tests fail there. The sixth (the end of a run does count the rot) passes both ways by design, as the guard against turning every write into a partial one.
<!-- SECTION:NOTES:END -->
