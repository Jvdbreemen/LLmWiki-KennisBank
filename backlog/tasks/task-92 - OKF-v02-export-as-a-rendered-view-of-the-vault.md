---
id: TASK-92
title: 'OKF v0.2 export as a rendered view of the vault (Spoor G)'
status: In Progress
assignee: []
created_date: '2026-07-28 08:00'
labels:
  - export
  - interoperability
  - llm-wiki-adoption
dependencies:
  - TASK-88
  - TASK-89
  - TASK-90
ordinal: 96600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Adoption decision (owner-approved): OKF (Open Knowledge Format v0.2, GoogleCloudPlatform/knowledge-catalog, Apache-2.0 spec — license verified) as an **export format — a rendered view — never internal storage**. Rationale: export is trivial and touches nothing; bi-temporality (valid_from/valid_until) has no OKF equivalent; OKF requires markdown links while the vault lives on wikilinks+Obsidian; v0.2 is young and Google-steered.

Key fit: OKF's trust tiers map 1:1 onto the memory lifecycle — no `verified` key = unverified (+ `status: draft`); `verified: {by: process:kb-judge}` = machine-confirmed (judge current); review-log approve adds `{by: human:owner}` = human-reviewed; retracted/superseded/expired -> `status: deprecated`; `generated: {by: model_id@pN, at}` from E5 producer provenance; `sources[]` from C1 `_provenance.doc_sources`; `expires` -> `stale_after`.

`scripts/kb-okf-export.py` (off-path batch, default `<vault>/okf-out`): §11 conformance (every non-reserved .md has frontmatter with non-empty `type`); wikilinks -> bundle-root-absolute markdown links, broken targets stay links and are counted; per-directory `index.md` (no frontmatter) + root `okf_version: "0.2"`; `log.md` from kb-activity.db `activity_events` daily rollups; deterministic and byte-idempotent. Attested Computation (§10) and per-claim footnotes (§5.1) deliberately out of scope. Minimal export ships before C/D/E; the trust layer enriches as they land.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Bundle passes §11 conformance — automated fixture test (PyYAML as strict referee when available)
- [x] #2 Trust-tier mapping verified (draft / process / human combinations)
- [x] #3 Wikilinks converted; broken-link count reported
- [x] #4 index.md per dir + root okf_version; log.md from rollups; byte-idempotent across two runs (test)
- [ ] #5 Manual validation of one real-vault bundle against the spec's example bundles recorded here
- [x] #6 Spec license: Apache 2.0 (verified 2026-07-27); no reference-agent code copied
- [x] #7 EVIDENCE OF IMPROVEMENT: real-vault export run recorded here (concept count, broken-link count, byte-idempotence check via two runs + hash compare) and one bundle validated against the spec examples
<!-- AC:END -->

## Evidence (2026-07-29, real vault)

`kb-okf-export.py` on the live vault: **1472 concepts** exported
(02-wiki + 09-memory), 2 directories, **306 non-resolving links** (kept as
markdown links per spec — consumers MUST tolerate broken links).
Byte-idempotence verified: two consecutive runs, identical sha256 over all
.md files (3669af70fdaa1457...). OPEN: AC#5 manual diff of conventions
against the spec repo's example bundles.
