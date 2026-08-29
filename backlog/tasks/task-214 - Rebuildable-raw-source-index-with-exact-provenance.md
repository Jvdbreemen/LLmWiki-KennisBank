---
id: TASK-214
title: Build a rebuildable raw-source index with exact provenance
status: Done
assignee: []
created_date: '2026-08-25 00:00'
updated_date: '2026-08-26 00:00'
labels:
  - source-recall
  - indexing
  - provenance
  - sqlite
dependencies:
  - TASK-212
  - TASK-213
ordinal: 175300
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement the offline source-recall index using the approved local storage
shape. Prefer the existing SQLite/sqlite-vec toolchain over introducing a new
vector database vendor. The index is a derived cache and must be safe to delete
and rebuild from raw files.

Index raw transcripts and approved source directories with stable document and
chunk identities. Store exact path/hash/session metadata, offsets or passage
boundaries, timestamps, project/client/role, redaction status, embedding model,
and index version. Use context-aware windows so a hit can return the relevant
passage plus surrounding context without losing the parent document.

The builder must support full rebuild, incremental rebuild, stale-entry
removal, model/version migration, interrupted-run recovery, progress output,
and a machine-readable manifest. It must not modify raw content or current
memory status.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A deterministic offline builder indexes all approved source roots and records its manifest and configuration
- [x] #2 Every returned chunk maps to an existing source path, hash, document id, and exact passage/window location
- [x] #3 Deleting the derived index and rebuilding produces equivalent ids and metadata for unchanged sources
- [x] #4 Changed, deleted, unreadable, and redacted sources are handled explicitly and reported
- [x] #5 The builder is fail-safe: a partial or failed rebuild cannot silently replace a known-good index
- [x] #6 Full and incremental rebuilds emit progress and do not run on the normal recall hot path
- [x] #7 Unit tests cover chunk identity, context windows, stale entries, hash changes, model version changes, and provenance failures
- [x] #8 No new hosted service or cloud data path is required
<!-- AC:END -->

## Implementation Notes
<!-- SECTION:NOTES:BEGIN -->
Keep raw source indexing logically separate from current wiki/memory ranking.
The exact module and database names are chosen by TASK-212, but the default
should reuse the repository's existing SQLite/sqlite-vec primitives.

### Evidence

- `scripts/build-source-index.py` uses the existing local SQLite/sqlite-vec
  projection, staging plus atomic replacement, a version stamp, source
  manifest, exact hashes/offsets, approved scalar frontmatter metadata, and an
  optional progress callback/CLI stream.
- `tests/test_build_source_index.py`: 11 tests cover approved roots, metadata,
  stable rebuild ids, changed/deleted/unreadable/redacted sources, failed
  rebuild preservation, model changes, and full/incremental progress.
- The source retrieval contract tests independently cover exact provenance,
  freshness, chunk boundaries, and normal-path routing.
<!-- SECTION:NOTES:END -->
