---
id: TASK-186
title: FTS body-cap fix never reaches already-indexed docs
status: Done
assignee: []
created_date: '2026-08-15 23:30'
updated_date: '2026-08-15 23:30'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by the 2026-08-15 eight-angle /code-review over main...release/v0.31.1,
verified against source before filing. Task IDs 169-179 are reserved by the
open PR #2 branch; this series starts at 180.

build-kb-index.py:195 skips any file whose hash matches the index
(incremental path), and neither the schema version nor embed_id changed
with the FTS_BODY_CAP fix (TASK-164) — so the 72 long articles keep their
truncated 4000-char FTS rows until each file happens to be edited or the
user manually runs --rebuild, while the changelog reports the 16.6%-of-
wiki-text-invisible problem fixed. General shape: a constant that changes
what indexed rows SHOULD contain needs an invalidation story, not just a
new value.

Adjacent, same subsystem: OLLAMA_NUM_CTX=2048 assumes ~4 chars/token from
the 4000-char cap, but above num_ctx the embed call FAILS rather than
truncates — a cap-length document dense in code, paths or non-Latin text
can tokenize past 2048 and silently drop from the index (only visible as
a failed counter); the doc prefix is prepended after the cap, tightening
the margin.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Index carries a content-contract version; changing FTS_BODY_CAP (or peers) triggers reindex of affected rows
- [ ] #2 Existing vaults get the corrected FTS rows without a manual --rebuild
- [ ] #3 Docs failing the num_ctx ceiling are reported by name, not only counted; the cap/ctx margin is stated in one place
<!-- AC:END -->

## Close-out (2026-08-16)

Fixed on chore/backlog-zero: the index stamps fts_body_cap in meta; on mismatch the incremental build repairs exactly the length-mismatched FTS rows from the embedding cache (targeted, fits the 300s job budget) and deployed vaults heal on their next sessionstart. Embed failures are reported by name; the char cap is the named constant EMBED_DOC_CAP with the token-boundary story in one place.
