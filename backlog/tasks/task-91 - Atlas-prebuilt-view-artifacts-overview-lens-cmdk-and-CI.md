---
id: TASK-91
title: >-
  Atlas: prebuilt view artifacts, overview lens 2.0, Cmd+K, JSON twin, facets,
  CI (Spoor F)
status: In Progress
assignee: []
created_date: '2026-07-28 08:00'
updated_date: '2026-08-03 21:57'
labels:
  - atlas
  - ui
  - llm-wiki-adoption
dependencies: []
modified_files:
  - atlas/sidecar/sources.py
  - atlas/sidecar/tests/test_decide_overview.py
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
AC#8 (2026-08-03) is PARTIALLY evidenced, box left unchecked -- three sub-measurements were asked for, one has a real browser number, one has a real number that misses target and got a mitigation, one could not be measured at all this session:

1. CI atlas job green on a real push: run 30854851637, branch chore/backlog-sweep-2026-08-03 (this PR, #101), 2026-08-03T21:29:35Z -- `atlas: success`, `test: success`. This sub-item is genuinely done.

2. Overview-lens first render: measured server-side /overview latency on the real vault (1609-concept scale) at 13.7-14.6s cold -- 27-30x over the <500ms target, NOT met. Root cause profiled (see sources.py's build_overview docstring + TASK-130): build_provenance()'s kb-lint re-run is ~12.2s of that, build_memory_health ~0.65s, the F1 heatmap itself ~34ms (not the problem). Applied a 30s in-process TTL cache around build_overview (atlas/sidecar/sources.py) as a stopgap -- repeat views inside the TTL now measure 2-5ms, but the FIRST view (the actual 'first-render' number this AC asks about) is unchanged at ~14s. The real fix is tracked separately as TASK-130 (kb-lint's collect_session_stems does an unscoped rglob over the whole vault). Cache invalidates on /memory/decide (approve/reject) so the dashboard doesn't serve stale counts after a write -- covered by a new regression test (test_approve_is_reflected_on_the_next_overview_fetch).

3. Palette (Cmd+K) open-to-filter latency and the overview lens's actual browser first-paint: NOT measured. This background session has no Chrome extension connection (mcp__claude-in-chrome__tabs_context_mcp returned 'extension not connected'), so no real-browser test was possible here, per CLAUDE.md's own rule that a server-side timing is not a substitute for testing UI in an actual running browser. /titles (the palette's one-time fetch) responded in 366ms server-side, which is a fine input but not the requested measurement.

AC#8 stays unchecked: 1 of 3 sub-claims fully evidenced, 1 measured-but-failing-with-mitigation-recorded, 1 blocked on browser access this session. Whoever picks this up next with a working Chrome extension: open the printed atlas/launch.py URL, record overview first-paint and Cmd+K-to-first-result timing, then check this box.
<!-- SECTION:NOTES:END -->

## Notes (2026-07-29)

- AC#5 (collapsible tool-call blocks): **explicitly deferred** — frontend-only
  follow-up, geen blokkade voor de rest van het spoor.
- AC#6 evidence: CI groen op PR #82 (test + atlas jobs, beide events pass) —
  runs 30405050117 / 30405054555.
- AC#1/#8 rest: eerste-render-meting van de Overzicht-lens op de echte vault
  (<500 ms-doel) bij de eerstvolgende Atlas-start.
