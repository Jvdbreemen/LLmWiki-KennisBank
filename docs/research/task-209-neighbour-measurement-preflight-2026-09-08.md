# TASK-209 neighbour-measurement preflight — 2026-09-08

Status: incomplete; no cache implementation is justified by this preflight.
No live memory, settings, cache, index or maintenance history was changed.

## Measurement support

The task-specific collector distinguishes embedding-input hashes from whole-file
hashes and detects additions/removals separately. It refuses changed inputs,
incompatible hash contracts, active database journals, missing databases and
unnormalized vectors. Repeated observations and changed heartbeat timestamps
are explicitly not counted as three natural sweep runs.

The benchmark reads a stable idle index image into memory and calls the existing
production indexed-neighbour arm with a time budget. It cannot fall back to
embeddings or quadratic cosine work. This measures an in-memory index snapshot,
not a full live sweep or cold-disk latency. All per-document observations must
remain private; only aggregates belong here.

Collector/benchmark tests: **17 passed in 0.93s**. During integration, an extra
test first failed for legacy file-hash classification. The correction reports
incompatible hash algorithms separately rather than labelling every source
changed solely because its stored hash predates SHA-256.

## Bounded real-index observation

- 5,016 indexed documents; 4,712 current memory vectors; 2,560 dimensions.
- Existing embedding identity: `ollama:qwen3-embedding:4b`.
- 40.003 seconds for 1,222 KNN queries before the deliberate 40-second budget
  stopped the run. Windows: 1,218 queries at k=32 and four at k=128.
- The full neighbour calculation did not complete; total pairs and full-run
  latency are unknown. The historical 1,432-second / 4,077-memory result is not
  a matched baseline and cannot support a claimed speedup.
- The stored live file hashes use the old algorithm. The initial probe reported
  4,712 mismatches; that classification was corrected to *incomparable*, not
  evidence that all 4,712 memory bodies changed. A separate zero-query preflight
  verifies the corrected classification without repeating the timing claim.
- Natural post-body-cache sweep runs proved: zero.

## Remaining prerequisite

The installed embedding writer still predates the body-key/SHA-256 transition,
as independently established under TASK-210. No available observation in this
preflight proves the required body-change deltas over three post-upgrade
sweeps. Coordinate supported deployment and safe cache migration first, then
collect real before/after observations around three completed maintenance runs.
Only those measured deltas and a completed matched neighbour timing may decide
incremental update, cache, or no change. TASK-209 remains In Progress.
