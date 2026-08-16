---
id: TASK-190
title: Reuse debt from the August experiment scripts
status: Done
assignee: []
created_date: '2026-08-15 23:30'
updated_date: '2026-08-15 23:30'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by the 2026-08-15 eight-angle /code-review over main...release/v0.31.1,
verified against source before filing. Task IDs 169-179 are reserved by the
open PR #2 branch; this series starts at 180.

Duplication added by the v0.28-v0.31 experiment series, each copy already
drifting or wired to drift:

- Script loader: five identical hyphenated-import helpers
(scene-experiment.py:42, rank-factors.py:56, rerank-ceiling.py:62,
rerank-eval.py:49, recall-ablation.py:47) plus seven inline copies in new
tests that skip tests/_loader's sys.modules registration; rerank-ceiling
imports the entire scene-experiment driver (module top-level side
effects included) to borrow QueryCache.
- _memory.py: log_discard/recent_discards are byte-copies of
_log_closure/recent_closures; only the discard log got trimming — the
pair diverged within one release.
- kb-mcp.py:259-330: four activity tools share an identical 12-line
unavailable/try/compact dance, four synchronized edits per change.
- kb-state-audit.py:197: _looks_like_key hand-paraphrases _memory's
config-key predicate despite the shared-definition comment; they already
disagree at the margins (isupper() vs the regex).
- embed-sweep.py:67: hand-rolled POST to hardcoded localhost:11434,
ignoring _embeddings' endpoint resolution — on a non-default endpoint the
sweep measures a different host than the index build it compares against.
- recall@k defined in three bodies (_rank_of x2, gold_rank) across
experiments whose point is comparability.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 One shared load_script (scripts side), used by the five scripts; tests import tests/_loader
- [ ] #2 QueryCache lives in a shared module; no experiment imports another experiment's driver
- [ ] #3 One append-JSONL writer/reader pair in _memory; trimming is a parameter
- [ ] #4 One _activity_call dispatcher in kb-mcp
- [ ] #5 kb-state-audit imports _memory's config-key predicate
- [ ] #6 embed-sweep resolves the endpoint via _embeddings
- [ ] #7 One shared gold-rank/recall@k helper used by all experiment scripts
<!-- AC:END -->

## Close-out (2026-08-16)

Six of seven duplications consolidated on chore/backlog-zero (verified per item by adversarial agents before fixing): JSONL log helpers in _memory, QueryCache -> _querycache.py, the kb-mcp activity dispatcher, the config-key predicate (one _CFG_KEY boundary, parity-pinned), embed-sweep endpoint resolution, and the canonical rank helper in kb-eval with delegating wrappers.

Deliberately parked (skip advice from verification): (a) the five script-side loader copies were replaced-by-alias where touched, but the ~40 LEGACY test files with hand-rolled importlib loaders stay - mechanical churn, near-zero drift risk, and the seven in-scope test files were the new ones; (b) the recall@k AGGREGATION tables (kb-eval/_metrics/_report/rank-factors/rerank-ceiling) differ in schema and rounding on purpose - merging them changes published experiment-result JSON shapes for no comparability gain.
