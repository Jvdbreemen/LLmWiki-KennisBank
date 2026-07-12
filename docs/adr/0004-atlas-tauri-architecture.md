# ADR-0004: KennisBank Atlas as a local-first Tauri standalone app

- **Status**: Accepted
- **Date**: 2026-07-12
- **Deciders**: Robert van den Breemen
- **Epic**: TASK-27 (child task TASK-27.1)

## Context

KennisBank produces no visual artifact. The vault holds a rich, structured memory
layer (typed, bi-temporal, importance, status, evidence/trust), a wiki
(`02-wiki`), a knowledge graph (`graphify-out/graph.json`), and a temporal
activity log (`kb-activity.db`), but nothing lets a human *see* or interactively
*query* them. The design spec
(`docs/superpowers/specs/2026-07-11-knowledge-visualization-atlas-design.md`)
names this gap.

The requirement is a **sovereign, local, standalone** dashboard: something you
can call up as an app, that runs fully offline, and that never sends vault
content to the cloud. It must honour the KennisBank north-star: invisible, fast,
retrieval-first, local-always.

Every architecture choice below is grounded in the **real vault scale**, not a
toy corpus. These numbers are the drivers, measured on the maintainer's vault:

| Store | Scale | Consequence |
| --- | --- | --- |
| `graphify-out/graph.json` | 2514 nodes / 3388 links | SVG/d3-force chokes above ~1000 nodes -> canvas/WebGL is mandatory |
| `kb-activity.db` | 10868 activity events | a timeline cannot render 10k raw events -> server-side aggregation |
| `kb-index.db` | 813 docs | join target for graph encodings |
| `09-memory` + `kb-usage.db` | typed/bi-temporal memory + warmth | needs a live backend to compute health, not a frozen export |
| Recall | query -> Ollama embed -> vector+FTS -> RRF -> rerank | a live retrieval waterfall cannot live in a static file |

The single join key across all stores is the **file path**
(`docs.path` = `activity_events.source_path` = graphify `source_file` = usage stem).

## Decision

Build Atlas as a **Tauri standalone desktop app** with a **local Python sidecar**:

1. **Shell**: Tauri, reusing the native OS webview (WebView2 on Windows,
   WKWebView on macOS). Bundle is under 10 MB with low RAM. Rust is near-zero: a
   `main.rs` of boilerplate plus `tauri.conf.json` that hosts the webview and
   spawns/manages the sidecar.
2. **Frontend**: TypeScript with a canvas/WebGL force-graph renderer, in a
   tab-shell with the six lenses. The frontend talks to nothing but the local
   sidecar.
3. **Backend**: a Python **FastAPI sidecar** bound to `127.0.0.1` only. It reads
   the local KennisBank stores and reuses the existing modules
   (`_kbindex`, `_activity`, `_rank`, `_memory`, `kb-recall`) rather than
   reimplementing retrieval or ranking. Recall runs live against local Ollama.
4. **Boundary**: everything local. Sidecar on loopback, Ollama local, no outbound
   network. Every node and panel traces back to a source file or event.

This pattern follows the OralHistoryAgent ADR-007 line (native webview shell plus
a frozen Python sidecar), chosen there as a one-click local app.

## Technology choices (motivated against the real scale)

| Choice | Why this, not the obvious alternative | Scale driver |
| --- | --- | --- |
| WebView2 / WKWebView (Tauri) | reuse the OS webview instead of shipping Chromium (Electron); under 10 MB vs 100 MB+ | keep the app invisible and light |
| canvas / WebGL force-graph | SVG and d3-force stall above ~1000 nodes | 2514 nodes / 3388 links |
| FastAPI sidecar (not a static JSON export) | live recall and server-side aggregation are impossible in a `file://` document | 10868 events; live retrieval waterfall |
| minimal Rust scaffold | `main.rs` + `tauri.conf.json`; Rust only hosts the webview and spawns the sidecar | no native plugins needed |
| reuse `_kbindex/_activity/_rank/_memory/kb-recall` | one source of truth for retrieval/ranking; the Recall Inspector must match `kb-recall` exactly | correctness and no drift |

## Alternatives rejected

1. **Static self-contained HTML over `file://`** (the original design). Rejected:
   SVG cannot render 2514 nodes interactively; a 10868-event timeline needs
   server-side aggregation; and a live recall waterfall (query -> Ollama ->
   ranking) cannot run inside a static document. This ADR supersedes that design.
2. **Local server plus the system browser** (no app shell). Rejected: no
   one-click app, no lifecycle ownership (a loose background process and a browser
   tab), no packaging story. It is a web page, not the callable standalone app the
   epic requires.
3. **Electron**. Rejected: 100 MB+ bundle and 200-400 MB RAM because it ships a
   full Chromium. That directly contradicts the invisible-and-light north-star,
   for no capability Tauri lacks here.
4. **Obsidian plugin / third-party host**. Rejected: reintroduces an external
   dependency and is not sovereign or standalone.

## Sidecar API contract

Base URL: `http://127.0.0.1:<port>`. The port is a free/ephemeral port negotiated
at spawn time; Tauri passes it to the frontend. All endpoints are `GET`, return
deterministic ordering, and carry a top-level `status` field
(`"ok" | "degraded" | "empty"`) so the frontend can degrade fail-open. Every later
child task references the endpoint definitions here.

### `GET /health`
Liveness and source readiness.
```json
{ "status": "ok", "version": "0.1.0", "vault": "<abs-path>", "port": 51763,
  "sources": { "kb_index": true, "activity": true, "usage": true,
               "memory": true, "graph": true, "ollama": true } }
```

### `GET /graph`  (serves Graph 27.4, Time-slider 27.5, Provenance overlay 27.9)
Params: `valid_as_of` (ISO timestamp, optional; bi-temporal filter).
```json
{ "status": "ok", "generated_at": "<iso>",
  "nodes": [ { "id": "<path>", "label": "...", "kind": "wiki|memory",
              "memory_type": "...", "layer": "...", "importance": 0.0,
              "warmth": 0.0, "node_status": "active|quarantined|superseded",
              "valid_from": "<iso>", "valid_until": "<iso|null>", "degree": 0 } ],
  "links": [ { "source": "<path>", "target": "<path>", "rel": "...", "weight": 1.0 } ] }
```
Data joins `graphify-out/graph.json` with `_kbindex` and `_memory` on file path.
Time-slider filtering is client-side over `valid_from`/`valid_until`.

### `GET /timeline`  (serves Timeline 27.7)
Params: `bucket` (`day|week`), `from`, `to`, `dimension` (`event|capture`).
Server-side aggregation of the 10868 events via `_activity`.
```json
{ "status": "ok",
  "buckets": [ { "start": "<iso>", "end": "<iso>", "event_count": 0,
                "capture_count": 0, "by_kind": { "edit": 0, "recall": 0 } } ] }
```

### `GET /memory-health`  (serves Memory Health 27.6)
Backed by `_memory` + `kb-usage.db`.
```json
{ "status": "ok",
  "counts": { "active": 0, "quarantined": 0, "superseded": 0, "unverified": 0 },
  "supersede_chains": [ { "head": "<id>", "chain": ["<id>", "..."] } ],
  "warmth": [ { "path": "<path>", "warmth": 0.0, "last_used": "<iso>" } ],
  "quarantine": [ { "id": "<id>", "reason": "..." } ] }
```

### `GET /recall`  (serves Recall Inspector 27.8)
Params: `q` (query), `k` (top-k). The only endpoint that needs Ollama. Runs the
live waterfall and reuses `kb-recall` so ordering matches exactly.
```json
{ "status": "ok", "query": "...",
  "stages": { "vector": [ { "path": "<path>", "score": 0.0 } ],
              "fts":    [ { "path": "<path>", "score": 0.0 } ],
              "rrf":    [ { "path": "<path>", "score": 0.0 } ],
              "rerank": [ { "path": "<path>", "score": 0.0 } ] },
  "final": [ { "path": "<path>", "score": 0.0, "snippet": "..." } ] }
```

### `GET /provenance`  (serves Provenance overlay 27.9)
Backed by `kb-lint`; rendered as an overlay on the Graph lens.
```json
{ "status": "ok",
  "coverage": { "sourced": 0, "unsourced": 0, "total": 0 },
  "unsourced": [ { "path": "<path>", "reason": "no source link" } ] }
```

## Frontend module boundaries

- **app-shell**: tab router, sidecar port handshake, global status banner.
- **data-client**: the single module that talks to the sidecar (typed fetch). No
  other module issues network calls. This is where the localhost-only invariant is
  enforced in code.
- **graph-renderer**: shared canvas/WebGL force-graph, reused by the Graph lens,
  the Time-slider, and the Provenance overlay.
- **lens modules** (six): Graph, Time-slider, Memory Health, Timeline, Recall
  Inspector, Provenance. Each consumes one endpoint (or filters `/graph`).
- **encoding/legend**: shared mapping of memory fields (type, layer, importance,
  warmth, status) to visual channels.

## Consequences

Positive: a sovereign, light, live, fast dashboard that renders real vault scale
and never leaves the machine.

Costs, stated explicitly:
- A **Rust toolchain** (cargo) is required to build the app.
- Packaging ships **two runtimes**: the frozen Python sidecar and the webview
  host. This is the ADR-007 "two runtimes to package" cost.
- A cross-platform build matrix (Windows first, macOS second).
- Sidecar **lifecycle** ownership: spawn on app start, health-poll with retry,
  graceful shutdown on close, no orphan processes.

No choice introduces an external cloud or network dependency. The sidecar binds
`127.0.0.1` only and Ollama is local; there is no outbound network path.

## Threat and operational model

- **Binding**: the sidecar binds `127.0.0.1` only, never `0.0.0.0`, on a
  free/ephemeral port. It is not reachable off the machine.
- **No external requests**: the sidecar reads only local DBs and calls only local
  Ollama (for `/recall`). No endpoint reaches the public internet.
- **Fail-open**: a missing index, DB, Ollama, or sidecar yields an
  empty-but-valid response with a `status` field, never a crash. The app degrades
  (a lens shows "source unavailable") rather than breaking.
- **Single-user desktop**: loopback-only on a personal machine is the trust
  boundary. If a shared machine ever needs it, add a per-launch loopback token in
  the port handshake; not required for the default single-user case.
- **Packaging cost** (restated): Rust toolchain at build, two runtimes bundled.

## Acceptance smoke (gate for TASK-27.10)

The launcher/doctor task is Done only when:
1. The app starts as a Tauri app (WebView2 loads the bundled frontend).
2. The sidecar spawns and `/health` is green.
3. At least the Graph lens renders against real data (2514 nodes, performant).
4. Live recall works: the Recall Inspector runs a `/recall` waterfall and returns
   ordered results.
5. The sidecar shuts down with the app (no orphan process).

## Traceability (lens/component -> child task -> ADR section)

| Child | Deliverable | ADR section it derives from |
| --- | --- | --- |
| TASK-27.2 | FastAPI sidecar + data-API | Sidecar API contract; Enforcement |
| TASK-27.3 | Tauri scaffold + TS tab-shell + sidecar lifecycle | Decision; Frontend module boundaries; Threat/operational |
| TASK-27.4 | Graph lens | `/graph`; graph-renderer |
| TASK-27.5 | bi-temporal Time-slider | `/graph` (`valid_from`/`valid_until`); Decision |
| TASK-27.6 | Memory Health lens | `/memory-health` |
| TASK-27.7 | bi-temporal Timeline lens | `/timeline` |
| TASK-27.8 | Recall Inspector lens | `/recall` |
| TASK-27.9 | Provenance/trust overlay | `/provenance`; Enforcement (provenance) |
| TASK-27.10 | launcher / idle-hook / doctor / setup / docs | Acceptance smoke |
| TASK-27.11 | performance/scale hardening | Technology choices; scale drivers |
| TASK-27.12 | Tauri packaging + bundling | Consequences; Threat/operational (packaging cost) |

## Enforcement (declarative invariants)

- The sidecar MUST bind `127.0.0.1` only.
- The frontend MUST talk only to the localhost sidecar; no module other than
  `data-client` issues network calls, and none reaches an external host.
- The sidecar MUST reuse `_kbindex`, `_activity`, `_rank`, `_memory`, and
  `kb-recall`; it MUST NOT reimplement retrieval or ranking. `/recall` MUST return
  the same ordering as `kb-recall`.
- Every node and panel MUST trace to a source file or event (provenance).
- All processing is local; Ollama is local; there is no cloud and no outbound
  network.
- Every code path is fail-open: a missing source yields an empty-but-valid
  response with a `status` field, never a crash.
