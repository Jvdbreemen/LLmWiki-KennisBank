# Source recall production evidence — 2026-09-06

## Decision under test

The public source-recall path is lexical and explicit. It uses SQLite FTS5/BM25
to find candidate evidence and a deterministic `SourceRef` resolver to hydrate
the exact passage from the raw source. It does not embed source chunks, maintain
a source-vector table, or activate automatically when normal recall is weak.

## Scale run

The production builder was run against the configured local vault with the
frozen source holdout left untouched.

- sources discovered and indexed: 16,286
- lexical chunks indexed: 490,317
- failed sources: 0
- failed chunks: 0
- published database size: 2,410.5 MB
- SQLite `PRAGMA integrity_check`: `ok`
- retrieval backend metadata: `sqlite_fts5`
- vector-like tables in the source database: none

The build publishes through a staging database and one atomic replacement. Two
scale defects were found before publication: retaining every decoded source in
memory reached about 3 GB, and committing once per source made the build
unacceptably slow. Streaming source processing and one staging transaction kept
observed memory roughly between 38 and 191 MB during the successful build.

## Latency evidence

Thirty warm iterations were measured on the configured local index with
`k=5` and query `bounded timeout`.

| Operation | Median | p95 | Budget | Result |
| --- | ---: | ---: | ---: | --- |
| FTS candidate search | 40.476 ms | 67.385 ms | 250 ms | pass |
| exact SourceRef hydration | 6.330 ms | 11.931 ms | 50 ms | pass |

An initial implementation missed both budgets: the search p95 was about
4,165 ms and hydration p95 about 676 ms. Conjunctive FTS terms, direct ordering
by the FTS rank column, and a bounded raw-source snapshot cache produced the
passing result. Exact hydration still validates the requested passage hash on
every response.

## Automated evidence

The relevant regression run completed with 118 passed tests and 1 intentional
skip. It covers the SourceRef contract, lexical schema/build, exact hydration,
latency budgets, CLI and MCP routing, projection doctor, ground-check integration,
setup deployment, and the static no-vector/no-embedding product policy.

The repository-wide Windows run is not treated as acceptance evidence because
the shared test socket shim can block unrelated subprocess and AnyIO tests.
The focused run avoids that harness defect without excluding any source-recall
contract named above.

## Critical limits

- The 2.4 GB index is a real storage and rebuild-cost tax for a vault whose raw
  text is substantially smaller. FTS is useful here, but it is not free.
- Conjunctive FTS deliberately favors precision and bounded latency. Verbose or
  poorly chosen queries can return no result and may need a narrower follow-up.
- A warm snapshot assumes stable filesystem identity, size, and timestamps for
  reuse of the whole-file digest. Passage bytes are still checked against the
  stored passage hash before they are returned.
- This evidence proves engineering viability and exact provenance, not yet
  end-user utility. Comparative product value remains the responsibility of the
  frozen layer evaluation in TASK-234.
