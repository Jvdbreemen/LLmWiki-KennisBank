# L2 scene layer for memory retrieval — design

Date: 2026-08-05
Status: approved, not yet implemented
Related: `docs/research/embedding-model-sweep-2026-08.md` (method precedent),
ADR-0002 (vault path resolution)

## Motivation

TencentDB Agent Memory (MIT, TypeScript) organises agent memory in four tiers:
L0 conversation, L1 atom, L2 scenario, L3 persona. Retrieval reads top-down —
the cheap high tiers first, dropping to atoms only when a specific fact is
needed. KennisBank has two layers (curated wiki, atomic memory) and one flat
hybrid ranking per layer. The L2 tier — a project- or scenario-scoped block
sitting between atoms and the curated article — has no equivalent here.

This spec covers whether adding that tier improves memory retrieval, and
measures it rather than assuming it.

### What this is not

Two other ideas from the same source are deliberately out of scope:

- **In-session tool-payload compression.** Their largest reported win comes
  from compressing tool output during a session. KennisBank's prompt injection
  is already ~600 tokens (3 wiki hits + 1 neighbour + 3 memory hits, snippets
  only), so there is no token headroom on the hot path. The real payload cost
  sits in-session and is invisible to `kb-eval`; it needs a different harness
  and is a separate project.
- **Periodic re-derivation as a drift audit.** Worth doing, unrelated to
  retrieval quality, not measurable with recall@k.

Token count is therefore **not** a metric in this experiment. `top_n` stays at
3, so the injected block size is constant by construction; measuring it would
report zero.

## Hypothesis

> A memory that scores just below the similarity floor for a query, but belongs
> to the same scene as the query's strongest match, is more often relevant than
> its raw cosine suggests.

If true, scene membership is a usable prior and recall improves. If false,
admitting those members displaces correct top-1 hits and recall@1 degrades —
which the measurement will show.

The memory layer is dense-only (the lexical arm was removed in v0.28.0 after it
lost to dense alone) with a similarity floor of 0.45. Adding scene members to
the candidate pool without changing their score is therefore a no-op: a member
scoring above the floor was already retrieved, and one scoring below still
loses. The only real lever is the floor and the score:

- `scene_floor` — members of the winning scene are admitted at a lower floor
  (e.g. 0.35 instead of 0.45)
- `scene_boost` — members receive a small additive score bonus

## Architecture

### Scenes are derived index rows, not markdown

Scenes live in their own `kb-scene.db`, alongside `kb-graph.db`, rebuildable
and disposable. They are never written as vault markdown.

Reason: markdown scenes would enter the corpus, be indexed, appear in Obsidian,
and could be counted as correct answers by the eval — the exact circularity
this experiment must avoid. Markdown remains the source of truth; a scene is a
view over it. This follows the existing precedent of `kb-graph.db`, which is
also a derived, independently rebuildable index.

Schema:

```
scenes(scene_id, label, clusterer, size, built_at)
scene_members(scene_id, path)
scene_centroids(scene_id, vector BLOB)
meta(key, value)          -- fingerprint against kb-index.db
```

`centroid` is the normalised mean of its members' embeddings, read from
`kb-index.db`. No new embedding calls are made at build time or at query time.

### One interface, three clusterers

`_scenes.py` exposes `cluster(members) -> list[Scene]` with three
implementations, selected by `KB_SCENE_CLUSTERER`:

| Clusterer | Source | Properties |
| --- | --- | --- |
| `community` | `graph_nodes.community` in `kb-graph.db` | Deterministic, sub-ms, no LLM, rebuilds with the graph. Communities are computed vault-wide, so granularity is an open question to measure, not assume. |
| `tags` | Shared frontmatter tags within a sliding time window | Simplest and fully explainable. Tags are sweep-assigned and uneven in quality; risk of many singletons or a few enormous scenes. |
| `llm` | LLM scene formation under a hard `max_scenes` cap | Mirrors their `scene-extractor.ts`, where capacity pressure forces merging. Richest grouping, non-deterministic, slow. |

The clusterer is the **only** thing that differs between experiment arms.
Retrieval, thresholds, ranking and eval are identical across all of them.

### Retrieval hop

`kb-recall.memory_hits` gains one step before ranking: score the query vector
against the scene centroids, take the best scene above a threshold, and apply
the prior (`scene_floor` / `scene_boost`) to that scene's members.

Scenes are **never returned as hits**. They route only. This keeps the gold set
untouched and the measurement non-circular.

Cost: one extra SQLite read over a few hundred centroids, sub-millisecond. The
query vector is already computed on the hot path and is reused.

### Knob placement

`scene_floor`, `scene_boost` and `scene_clusterer` are resolved in
`kb-retrieve.retrieve_params()`. That function is the documented single source
of truth from which `kb-eval` loads the knobs via importlib. Resolving a
retrieval knob anywhere else makes the eval silently drift from the hook — the
drift TASK-86 fixed.

### Failure behaviour

Fail-open, without exception. A missing or stale `kb-scene.db` behaves exactly
like the baseline: no notice, no added latency. Staleness is determined by a
fingerprint against `kb-index.db`, the same pattern as `graph_is_current()`.

The `scene_retrieval` toggle defaults to **off** and is only switched on if the
numbers earn it.

## Components

| File | Responsibility |
| --- | --- |
| `scripts/_scenes.py` | Scene model, `kb-scene.db` schema, three clusterers behind one `cluster()`. Pure stdlib, no network, no import side effects — as `_memory.py` and `_kbindex.py`. |
| `scripts/build-scene-index.py` | Build CLI. Reads memory embeddings from `kb-index.db`, calls the clusterer, writes centroids. Off the hot path. |
| `scripts/kb-recall.py` | The scene prior in `memory_hits`, behind the toggle. The only change to the read path. |
| `scripts/kb-retrieve.py` | Three knobs added to `retrieve_params()`. |
| `tests/test_scenes.py` | Clusterers, schema, and the parity test. |

## Experiment design

### Two staged axes

A full 3 × 3 grid over one measurement set produces a winner by chance. Two
stages instead, each with one explainable cause:

- **Stage 1 — clustering.** All three clusterers at a fixed neutral prior
  (`floor=0.35`, `boost=0`), plus `off`. Four arms.
- **Stage 2 — prior.** The two best clusterers from stage 1, at `floor-only`,
  `boost-only`, and `both`. Six arms.

`llm` runs three times to expose its own variance. `community` and `tags` are
deterministic and run once.

### Splits

`kb-memory-eval-set.json` (1224 questions) is split with a fixed seed into dev
(70%) and holdout (30%). Every decision — winning arm, thresholds, calibration
— is made on **dev**. The holdout runs exactly once, at the end, on the chosen
configuration.

`kb-memory-eval-set-v2.json` (84 questions, different provenance) is a third,
independent confirmation set.

A gain that does not hold on both holdout and v2 was overfitting and does not
ship.

### Baseline

Baseline is `main`, unmodified. The work happens in one git worktree in which
the clusterer is switchable per run, including `off`.

`off` inside the worktree must reproduce the baseline **exactly**. If it does
not, something other than clustering changed, and the experiment stops before
any conclusion is drawn. This parity test is the first test that must pass.

### Metrics

All from the existing harness: memory-layer recall@1/3/5, MRR, a breakdown per
`memory_type` (feit / procedure / beslissing / voorkeur), and `--latency`
p50/p95.

### Winner rule, fixed in advance

An arm wins only if all four hold on dev:

1. recall@5 improves by **≥ +0.02** over baseline
2. recall@1 does **not** decrease (no displacement of correct top hits)
3. p50 latency increases by **< 5 ms**
4. the gain appears in at least **two of the four** `memory_type` groups

If no arm qualifies, the result is "no gain", the numbers are written up, and
nothing ships — as with the source-overlap ranking boost rejected in v0.24.0.

### Evidence beyond the aggregate

Three artefacts explain the mechanism rather than just scoring it:

1. **Scene diagnostics per clusterer** — scene count, size distribution
   (median, p95, largest), coverage (share of the ~1428 memories in a scene),
   and singleton share. A clusterer producing one 900-member scene is
   hopeless by construction, and that must be visible before the retrieval run.
2. **Oracle ceiling, computed without running retrieval.** For each eval
   question: does the gold memory share a scene with the highest-scoring
   candidate? This is the upper bound on what the prior can ever deliver, per
   clusterer, computable in seconds. A ceiling of 3% means the expensive run is
   unnecessary.
3. **Per-question deltas.** Which questions flip from miss to hit, and which
   flip back. Displacement is the real cost and an average hides it. Twenty
   examples from each direction, with the scene that caused it.

### Reporting

`docs/research/l2-scene-retrieval-2026-08.md`, in the shape of
`embedding-model-sweep-2026-08.md`: method, raw numbers, per-arm tables, the
flip examples, and an explicit conclusion including what did not work. Raw eval
output is stored as JSON alongside it so every table is traceable to a run.

## Build order

Test-first throughout.

1. Schema, Scene model, and the `off` path → **parity test** (worktree `off`
   returns byte-identical hits to `main`). Nothing later means anything without
   this.
2. `community` clusterer.
3. `build-scene-index.py`, centroids from existing embeddings.
4. The prior in `memory_hits` (`scene_floor` + `scene_boost`).
5. Scene diagnostics + oracle ceiling for `community`.
6. **First measurement**: baseline vs `community` on dev.
7. `tags` clusterer, diagnostics, ceiling, measurement.
8. `llm` clusterer with `max_scenes` cap, three runs.
9. Stage 2: prior sweep on the two best clusterers.
10. `kb-calibrate` over `scene_floor` / `scene_boost` for the winner only —
    after the arm comparison, never before, or one arm is calibrated rich
    against two that are not.
11. Holdout + v2 confirmation, exactly once.
12. Report.

Steps 6 and 8 are decision points. If `community` and `tags` both land far
below the threshold, whether the non-deterministic `llm` arm can plausibly
close that gap is a judgement call to be made with the numbers on the table,
not automatically.

## Open questions

- Vault-wide graph communities may be too coarse for project-scoped scenes.
  The oracle ceiling in step 5 answers this cheaply, before any retrieval run.
- The `tags` clusterer needs a window length. Start at 90 days, and report the
  size distribution rather than tuning it silently.
