---
id: TASK-91
title: 'Atlas: prebuilt view artifacts, overview lens 2.0, Cmd+K, JSON twin, facets, CI (Spoor F)'
status: In Progress
assignee: []
created_date: '2026-07-28 08:00'
labels:
  - atlas
  - ui
  - llm-wiki-adoption
dependencies: []
ordinal: 96500
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Ideas verified in Pratiyush/llm-wiki (closest relative: offline-first, session transcripts as input) plus the scale lesson from llm_wiki #604 (unusable at 7k pages: relations computed at view time). Principle (E1 applied to UI): view data is aggregated in the sidecar, never computed per item while the user waits.

- F1 Overview lens 2.0: `/overview` gains a 365-day activity heatmap (`_activity_heatmap`: one SQL GROUP BY over activity_events, sqlite3.Row-safe sort) and wiki freshness buckets (d7/d30/d90/older/unknown from the existing frontmatter loop); frontend renders a flex heat-strip (~182 days, q0-q4 intensity classes) + freshness line. Half-fills TASK-44's tour idea.
- F2 Cmd/Ctrl+K palette: new `/titles` endpoint (kb-index.db docs, `_rel_key` paths); frontend `palette.ts` with pure `fuzzyFilter` (all tokens substring, rank by position/length/alpha; vitest-pinned) + overlay (el()/textContent, no innerHTML); lens-jump + `openInspect` doc-open; titles fetched once per session.
- F3 Recall Inspector copy-as-JSON of the whole waterfall (machine-readable twin).
- F5 Facet chips (alle/wiki/memory) in the Recall Inspector: `/recall` final hits carry `layer` + `neighbor`; client-side filtering, no new query per click.
- F4 Collapsible tool-call blocks in the drawer (frontend-only) — may remain follow-up.
- CI: dedicated `atlas` job in .github/workflows/ci.yml (sidecar pytest, frontend `tsc --noEmit` + vitest, npm cache on package-lock) — until now every Atlas change shipped unguarded.
- atlas/README: correct to the seven shipped lenses (Timeline/Provenance dropped in TASK-27.18; Overzicht/Graphify added) and the real write-path story (POST /memory/decide); document the palette.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Heatmap + freshness from single SQL aggregation; sidecar tests (events per day, fail-open without db, freshness buckets)
- [x] #2 No graph/relation computation on the UI thread
- [x] #3 Palette over prebuilt /titles; fuzzyFilter vitest-pinned; no live query per keystroke
- [x] #4 Copy-as-JSON + facet chips in Recall Inspector
- [ ] #5 Collapsible tool-call blocks (or explicitly deferred here)
- [x] #6 atlas CI job green
- [x] #7 atlas/README corrected (docs = contract)
- [ ] #8 EVIDENCE OF IMPROVEMENT: measured first-render time of the overview lens on the real vault (<500 ms target), palette open-to-filter latency, and CI job green on a real push — numbers/screenshots recorded here
<!-- AC:END -->

## Notes (2026-07-29)

- AC#5 (collapsible tool-call blocks): **explicitly deferred** — frontend-only
  follow-up, geen blokkade voor de rest van het spoor.
- AC#6 evidence: CI groen op PR #82 (test + atlas jobs, beide events pass) —
  runs 30405050117 / 30405054555.
- AC#1/#8 rest: eerste-render-meting van de Overzicht-lens op de echte vault
  (<500 ms-doel) bij de eerstvolgende Atlas-start.
