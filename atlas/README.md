# KennisBank Atlas

A sovereign, local-first dashboard for the KennisBank vault: see and query your
knowledge (wiki), memory (typed, bi-temporal), the knowledge graph, the activity
heatmap, and the live retrieval waterfall - all offline. Architecture:
ADR-0004. It is a TypeScript frontend talking only to a local FastAPI sidecar on
loopback; the sidecar reads the vault stores read-only — with exactly one
deliberate write path: `POST /memory/decide` flips the `status:` line of an
unverified memory to current/retracted (the human review action, shared with
`/kennisbank:review` since TASK-89). It reuses the existing KennisBank modules
(`_kbindex`, `_activity`, `_rank`, `_memory`, `kb-recall`, `kb-lint`). Nothing
leaves the machine.

Press **Cmd/Ctrl+K** anywhere for the palette: jump to a lens or open any
document by title (prebuilt index, no per-keystroke queries).

## Lenses

The seven shipped lenses (Timeline and Provenance were dropped in TASK-27.18 —
bare bar charts and a coverage percentage answered no question; provenance
survives as a line in Overzicht, and the `/timeline` and `/provenance`
endpoints remain for tooling):

- **Overzicht** - one health page over the whole vault: counts, signals, the
  365-day activity heatmap and wiki freshness buckets (TASK-91).
- **Graph** - the wiki knowledge graph, coloured by community/status/kind or the
  provenance and memory-entry-points overlays; click a node to read the article.
  Toggle "memory-fragmenten" for the full two-layer graph.
- **Graphify** - the graphify-out/graph.html page embedded in the viewer.
- **Wordcloud** - concepts sized by importance (links + usage).
- **Time-slider** - the graph as-of a date (capture-time vs valid-time).
- **Memory Health** - lifecycle counts, quarantine queue, importance x recency
  heatmap, warm/stale usage, supersede chains, approve/reject buttons.
- **Recall** - the live retrieval waterfall (vector -> FTS -> RRF -> rerank),
  with facet chips (alle/wiki/memory) and a copy-as-JSON export of the whole
  waterfall.

## Requirements

- Python 3.12+ with the sidecar deps: `pip install -r atlas/sidecar/requirements.txt`
- Node 18+ and npm: `cd atlas/frontend && npm install`
- Ollama running locally (for `/recall`; other lenses work without it)
- A KennisBank vault; set `KENNISBANK_VAULT` to its path (ADR-0002)
- For the standalone Tauri app (optional): the Rust toolchain (rustup) - see below

## Run (dev)

One command starts the sidecar and the Vite dev server and prints the URL:

```bash
KENNISBANK_VAULT=/path/to/vault python3 atlas/launch.py
# -> [atlas] OPEN:  http://127.0.0.1:<vite>/?port=<sidecar>
```

Open the printed URL. Ctrl-C stops both. (Manual alternative: run
`python3 -m atlas.sidecar` and `cd atlas/frontend && npx vite` separately, then
open the frontend with `?port=<sidecar-port>`.)

## Doctor

Check readiness (deps, toolchain, vault stores, and optionally a live sidecar):

```bash
KENNISBANK_VAULT=/path/to/vault python3 atlas/doctor.py [--port <sidecar-port>]
```

Exit 0 = ready for dev. The Rust toolchain is reported but OPTIONAL - it is only
needed for the bundled app; dev mode runs without it.

## Tests

- Sidecar (Python): `python3 -m pytest atlas/sidecar/tests/`
- Frontend (TypeScript): `cd atlas/frontend && npm test` (encoding + time-filter
  unit tests)

## Standalone app (Tauri) - build prerequisites

The bundled desktop app (TASK-27.12) wraps the frontend in a Tauri WebView2 shell
and ships a frozen Python sidecar. It needs, at build time only:

- Rust toolchain via rustup (`cargo`) and the Tauri CLI
- A sidecar freezer (PyInstaller) to bundle the FastAPI sidecar without a system
  Python

The scaffold lives in `atlas/src-tauri/`. Dev mode above needs none of this.
