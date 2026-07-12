# Atlas performance and visual evaluation (TASK-27.11)

Recorded against the real maintainer vault (see the build screenshots in the
session log) and the hermetic perf test (`atlas/sidecar/tests/test_perf.py`).

## Measured latencies (real vault)

| Endpoint / op | Scale | Time | Note |
|---|---|---|---|
| `/timeline` (week) | 11198 events | ~0.76s | server-side aggregation |
| `/graph` (wiki) | 1106 raw -> 95 file nodes / 161 links | fast (<0.5s) | |
| `/graph?include_memory=1` | 937 nodes / 832 links | ~10-57s | dominated by the one-time memory-links scan (cached; warmed at startup) |
| `/memory-links` | 704 fragments | ~47s first, then cached | vector+FTS+RRF over stored embeddings, no Ollama |
| `/memory-health` | 811 memories | ~0.28s | |
| `/provenance` | 97 wiki (kb-lint) | fast | |
| `/recall` | live | ~10-40s cold embed, ~1s warm | Ollama re-embed of the query |
| timeline aggregation (hermetic) | 4000 events | <1.0s (test-enforced) | budget guard |

## Frontend scale

- Renderer: `force-graph` on a 2D **canvas** (not SVG) - the ADR-0004 requirement
  to avoid the SVG ceiling. Verified interactive at **937 nodes** (95 wiki + 842
  memory) with the memory overlay on.
- **Level-of-detail**: above 400 nodes the Graph lens drops the per-node warmth
  halo and status ring (the expensive per-frame extras); the omission is shown in
  the controls ("LOD aan (N nodes; halo/ring uit voor snelheid)"), never silent.
- **Animation cooldown**: the force engine stops after ~120 ticks
  (`cooldownTicks` + `pauseAnimation`) so an idle graph does not burn CPU and the
  page reaches idle.
- **Lens teardown**: leaving a graph lens stops its animation loop (lifecycle.ts),
  preventing a detached loop from pegging the main thread.

## Note on the 2514-node target

The AC references 2514 nodes / 3388 links, which is graphify's FULL graph across
all layers. The current `/graph` is scoped to 02-wiki (95 file nodes; 937 with
memory). The canvas approach + LOD is proven at 937 nodes and scales to a few
thousand; reaching the exact 2514 requires a full-graphify regraph (a data-scope
task), not a rendering change.

## Visual evaluation checklist (all lenses reviewed live)

- [x] Graph - community/status/kind/provenance/entry-points colour modes,
  size=importance/degree, ring=status, halo=warmth; legend matches; filters work.
- [x] Wordcloud - size = degree + warmth; top concepts largest; click -> article.
- [x] Time-slider - as-of scrub shrinks the graph to the then-existing nodes;
  capture/valid axis toggle.
- [x] Memory Health - count tiles, unverified queue, importance x recency heatmap,
  warm/stale badges, supersede chains.
- [x] Timeline - weekly event-time vs capture-time bars; recent ramp-up visible.
- [x] Recall - live waterfall; per-hit factor breakdown multiplies to the final.
- [x] Provenance - coverage bar + unsourced list == kb-lint.

No colour choice relies on red/green alone except the provenance/status overlays;
a colour-blind-safe palette pass is a documented follow-up.
