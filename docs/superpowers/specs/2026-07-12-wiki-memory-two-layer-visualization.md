# Design: two-layer visualisation of wiki (long-term) and memory (entry points)

- **Date**: 2026-07-12
- **Epic**: TASK-27 (KennisBank Atlas)
- **Status**: Accepted (options surveyed, decision recorded)

## Problem

KennisBank holds two kinds of knowledge, both distilled from the same raw logs:

- **Wiki articles (`02-wiki`) = long-term memory.** Durable, consolidated,
  human-curated "truth". These form the knowledge map.
- **Memory fragments (`09-memory`) = entry points.** Small, typed entries whose
  job is to lead an agent to the right article at the right moment (retrieval
  hooks). Many fragments point to one article.

Atlas currently graphs only the wiki layer. We want both layers visible in one
app **without collapsing their very different roles** — the wiki is the map, the
memory is the way in.

## Research grounding (brief)

- **Obsidian** graph distinguishes node kinds only via colour-groups, size (link
  count), tags-as-nodes, and a *local graph* for focus. No native two-layer view.
- **Zep / Graphiti** and **Letta / MemGPT** explicitly separate short-lived
  **episodes/facts** from durable **entities/summaries/archival** — the same
  fragment-vs-article split we have.
- **Multilayer network viz** (muxViz) stacks layers on separate planes; strong on
  "show both layers" but weak on readability and expensive on a 2D canvas.
- **TheBrain** uses focus+context (one active item + its neighbours).

## Options considered

| # | Option | For | Against |
|---|--------|-----|---------|
| 1 | Single graph, encoding-only separation | simplest, reuses graph | hairball at scale; roles blur |
| 2 | Satellite/halo (article core + orbiting fragments) | "entry points to THIS article" legible | multi-article fragments awkward; layout cost |
| 3 | Bipartite two-column | crystal-clear many→one mapping | loses article↔article structure; not a map |
| 4 | Two stacked planes (2.5D) | literal "over each other"; explicit | hard to read/navigate on 2D; costly; occlusion |
| 5 | **Base map + toggleable overlay/lens** | wiki=map, memory=way-in; clean; density signal; scales; reuses graph+inspect | individual fragments need drill-down |
| 6 | **Linked dual-view (brushing)** | each layer in ideal form; editor-friendly | two views; less "one picture" |
| 7 | Semantic zoom | elegant scale; drill into entry points | fragments hidden until zoom; non-trivial |

## Decision

**Primary: Option 5 (base map + memory overlay) combined with Option 6's linked
inspect.**

- The wiki article graph stays the durable map.
- A toggle **"memory entry-points"** encodes, per article, how many memory
  fragments point to it (size/glow) — surfacing which knowledge is well-served
  for agents and which articles are blind spots (no entry point).
- Clicking an article opens the existing inspect drawer, which lists that
  article's fragments (entry points) with their type — the linked-view coupling,
  without a second permanent panel.

Rationale: matches the mental model (map vs way-in), scales to vault size, and
reuses the graph + inspect already built. Option 2 (satellites) is the striking
alternative if individual fragments must float visibly; kept as a future variant.

## Prerequisite: the fragment → article edge

No option works without a fragment→article association, which does not exist yet.
Candidate links: (a) shared `source_session`, (b) embedding similarity, (c) the
recall outcome. We choose **(c) recall**: run each memory fragment through the
existing recall waterfall (TASK-27.8, reuses `kb-recall`) and link it to its top
wiki article. This is exactly "which article would this fragment lead an agent
to", reuses production ranking, and needs no new similarity code.

## Build plan (tasks)

1. **TASK-27.14** — Sidecar: fragment→article links via recall. A `/memory-links`
   endpoint (or `/graph` enrichment) mapping each fragment to its top article(s),
   plus a per-article entry-point count. Read-only, fail-open, tested.
2. **TASK-27.15** — Frontend: Graph "memory entry-points" overlay (size/glow by
   count, toggle) + the inspect drawer lists an article's fragments with types.

Future: TASK for the satellite (Option 2) variant if desired.
