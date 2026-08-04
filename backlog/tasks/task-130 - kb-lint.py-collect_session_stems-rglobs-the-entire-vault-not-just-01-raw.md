---
id: TASK-130
title: 'kb-lint.py: collect_session_stems() rglob''s the entire vault, not just 01-raw'
status: Done
assignee: []
created_date: '2026-08-03 21:56'
updated_date: '2026-08-03 22:39'
labels:
  - performance
  - kb-lint
  - atlas
dependencies: []
modified_files:
  - scripts/kb-lint.py
priority: medium
ordinal: 125700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Discovered while measuring TASK-91 AC#8: Atlas sidecar's `/overview` endpoint calls `build_provenance()` -> `kb_lint.lint_vault()` on every request, uncached. On the real vault this alone took ~12.2s of the endpoint's ~13-14.6s total (measured 2026-08-03).

Root cause: `collect_session_stems()` (scripts/kb-lint.py:95) does `root.rglob(f"{SESSION_PREFIX}*.md")` -- a recursive walk over the WHOLE vault tree (09-memory, okf-out, archive, everything), not scoped to 01-raw/01-raw-adjacent dirs, even though its own docstring says the intent is "sessions moved to 01-raw/debug, 08-archive, ...". A vault with thousands of total files pays a full recursive filesystem walk on every lint_vault() call.

Atlas's own /overview got a stopgap fix (a 30s in-process TTL cache around build_overview, atlas/sidecar/sources.py) so the sidecar itself no longer pays this per-request. kb-lint.py itself (used directly by /wiki, doctor.sh, etc.) is unaffected by that cache and still pays the full rglob every invocation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Root cause confirmed: profile collect_session_stems() in isolation on the real vault, record ms
- [x] #2 Fix scopes the walk (e.g. glob only under known session-bearing dirs, or cache the stems set with a cheap staleness check) without changing lint_vault()'s public contract
- [x] #3 Re-measure build_provenance() / kb-lint on the real vault after the fix and record before/after here
- [x] #4 Existing kb-lint tests stay green; add a regression test if the scoped walk could silently drop a valid session dir
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Profiled first, per the review that caught the previous session's premature attribution (build_memory_health had been misdiagnosed as the /overview bottleneck before -- it was actually build_provenance/kb-lint). This time measured collect_session_stems() and lint_article() separately on the real vault before touching any code: collect_session_stems 15.58s, lint_article summed across 164 articles 182ms, lint_index_drift 164ms. The rglob was confirmed as the real cost.

Root cause pinpointed further: timed the rglob per top-level vault directory. 05-bronnen/ (58,285 files, an Evernote-style import archive) alone accounted for 12.0s of the 15.58s and matched zero raw-sessie-*.md files -- pure dead weight from a directory that, by the vault's own convention (see resolving_bron_links()), is a different herkomst category and structurally cannot hold session files. Every other top-level directory was fast (<100ms) regardless of file count (09-memory's 1448 files cost 11ms), so the issue was 05-bronnen's specifically deep/slow tree, not raw file count vault-wide.

Fix: collect_session_stems rewritten from root.rglob() + post-hoc filtering to os.walk() with directory pruning, adding "05-bronnen" to SKIP_DIRS. rglob always descends fully and filters results after the fact; os.walk with dirnames[:] pruning never descends into an excluded directory at all, which is what actually saves the time (adding 05-bronnen to the old SKIP_DIRS without changing the algorithm would have changed nothing, since rglob was already walking it before the post-filter ran).

Correctness verified exactly per the review's ask, not just "tests pass": stems set before (1037) and after (1037) are identical; lint_vault()'s full report on the real vault is identical before/after (164 articles, 0 warnings, 0 hard) -- confirmed by re-running lint_article's own sum (0 warnings, matching lint_vault's 0). The test_vault_under_skip_named_ancestor_still_resolves edge case (a vault rooted under a path literally containing ".claude") was checked by inspection: os.walk starts at root and never looks at ancestor path components, so it handles this case even more directly than the original's relative_to()-based reasoning did.

collect_session_stems: 15.58s -> 78ms (~200x). lint_vault() end-to-end: ~12.4s -> 247ms. Full pytest suite: 1129 passed, 2 skipped (2026-08-04).
<!-- SECTION:FINAL_SUMMARY:END -->
