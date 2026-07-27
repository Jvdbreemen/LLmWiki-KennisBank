---
id: TASK-84
title: 'Atlas: Graphify-lens — toon graphify-out/graph.html in de viewer'
status: Done
assignee: []
created_date: '2026-07-26 20:53'
updated_date: '2026-07-26 22:10'
labels:
  - atlas
  - visualization
dependencies:
  - TASK-44
ordinal: 94000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up on TASK-44 (idea: guided graph presentation). First step: surface the existing graphify visualization inside Atlas. The graphify pipeline already emits a self-contained interactive graph.html in <vault>/graphify-out/. Serve it from the sidecar (read-only, loopback) and add a "Graphify" lens that embeds it in an iframe. This dodges the file:// wall documented in wiki grote-graaf-visualiseren-render-grenzen: served over http://127.0.0.1 the page can run scripts normally.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Sidecar has GET /graphify-html that serves <vault>/graphify-out/graph.html with media type text/html and 404 when missing
- [x] #2 Frontend has a Graphify lens (tab) that embeds the page in an iframe via the loopback base URL
- [x] #3 Missing graph.html shows a clear degraded message instead of a broken iframe
- [x] #4 Sidecar tests cover the new endpoint (present + missing)
- [x] #5 pytest suite green
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Sidecar: GET /graphify-html serves <vault>/graphify-out/graph.html (404 when missing).
2. Frontend: DataClient.graphifyHtmlUrl(), new Graphify lens (HEAD-probe then iframe), tab in main.ts, .graphify-frame CSS.
3. Tauri CSP: add frame-src http://127.0.0.1:* (default-src 'self' would block the iframe in the bundled app).
4. Tests: test_graphify_html.py (200 + 404); full pytest gate + tsc + vite build.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Live-checked against the real vault (Kluis): /graphify-html returns 200 text/html, 1.15 MB. Sidecar tests 48 passed; tsc and vite build green. Note: the deployed Atlas app runs the installed build — a rebuild/reinstall (atlas BUILD.md) is needed before the new tab shows up there; dev-run shows it immediately.

Full gate green: 1015 passed, 2 skipped in 8:37 (pytest tests + atlas/sidecar/tests).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Sidecar endpoint GET /graphify-html serves <vault>/graphify-out/graph.html (404 when missing); new Graphify lens embeds it in a full-size iframe after a HEAD probe (clean degraded message when absent). Tauri CSP widened with frame-src http://127.0.0.1:*. Tests: test_graphify_html.py; full gate 1015 passed, 2 skipped. Merged via PR #79 (merge commit 1d69e6c, verified on origin/main). Note: Copilot review unavailable (quota limit reached) — merged on explicit user instruction with green gate; no inline findings to process.
<!-- SECTION:FINAL_SUMMARY:END -->
