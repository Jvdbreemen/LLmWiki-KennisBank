---
id: TASK-166
title: Release v0.31.0
status: Done
assignee: []
created_date: '2026-08-15 15:50'
labels:
  - release
dependencies: []
ordinal: 159700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Carries TASK-138, TASK-160, TASK-162 (design only), TASK-163 and TASK-164 — the branch `research/rerank-ceiling`, open as PR #121.

**Minor, not patch.** Two output contracts change:

- Swept memories gain a `source_chunk: "N/M"` frontmatter field (TASK-163).
- `fts_docs` now stores the whole document instead of the first 4000 characters, so every existing `kb-index.db` is stale until rebuilt (TASK-164). The builder rebuilds on a hash change, but the hashes did not change — only the stored text did, which means users need `--rebuild` to get the improvement. That must be said in the changelog, or the release ships a measured gain nobody receives.

**What a reader needs to know it does for them:** questions about material past the first 4000 characters of a wiki article go from recall@5 0.450 to 0.725. Two thirds of the wiki was never affected; the third that runs long was half-findable and is now mostly findable.

**What it explicitly does not do:** the trust factor. TASK-163 set out to make `trust_factor` work and concluded, on measurement, that it should not be built on grounded verification. That belongs in the changelog as a decision, not omitted because nothing shipped.

Follow the `kennisbank-release` skill. Two steps that have burned this repo before and apply here: wait for the Copilot review and read the review BODY as well as the comments endpoint (its suppressed findings live only in the body, and one of them this session was the best finding of the review); and tag only a SHA confirmed present on `origin/main` after the merge, using `^{}` when stamping the deployed version.

<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Version proposed from the commit delta with a stated reason, and confirmed
- [ ] #2 CHANGELOG has a dated section saying what changes for the user, including that kb-index.db needs a rebuild
- [ ] #3 README.md and README.nl.md both updated in the same edit
- [ ] #4 Full suite green before the docs edit; documentation subset green after
- [ ] #5 Copilot review processed — comments endpoint AND review body — before merge
- [ ] #6 Tag placed only on a SHA verified present on origin/main
- [ ] #7 Release published with a non-empty body
<!-- AC:END -->
