---
id: "ADR-008"
title: "Remove the L2 scene retrieval layer after its measured rejection"
status: "Accepted"
date: "2026-08-18"
binding: true
gate: null
documents_shipped: false
verified_in: []
supersedes: []
superseded_by: null
format: "madr"
---

<!-- markdownlint-disable MD025 -->

# ADR-008 Remove the L2 scene retrieval layer after its measured rejection

## Status

Accepted, 2026-08-18.

## Status History

```yaml
status_history:
  - date: 2026-08-18
    status: Proposed
    changed_by: Claude
    reason: Owner asked whether the rejected scene layer can be removed to simplify the codebase
    changed_via: manual
  - date: 2026-08-18
    status: Accepted
    changed_by: Claude
    reason: Owner approved removal after reviewing the measurement and the all-or-nothing scope
    changed_via: manual
```

## Context and Problem Statement

TASK-134 built a scenario tier (L2) between atomic memories and curated wiki
articles, modelled on the L0-L3 memory pyramid of layered agent memory. Scenes are derived rows in
`kb-scene.db`, built off the hot path from vectors already in `kb-index.db`, and
never returned as retrieval hits. At query time the best-matching scene acts as
a prior over its members: they are admitted at a lower similarity floor
(`scene_floor`) and may receive a score bonus (`scene_boost`).

The experiment was staged with a winner rule fixed in advance and measured on
2026-08-10/11. It failed. `scene_retrieval` has defaulted to off ever since, and
on 2026-08-18 the owner confirmed it stays off.

That left roughly 1800 lines of shipped, inert code. The cost is not uniform.
`_scene_path`, `_merge_scene_members`, `_scene_members_for` and the
`scene_prior` argument thread through `kb-recall.py` — the hot-path read
library — so every later change to recall has to reason around a branch no
production path reaches. `build-scene-index.py` has no automated caller at all,
so any `kb-scene.db` on disk is orphaned the moment the index moves.

## Decision Drivers

* KennisBank's north star is a sub-second interactive path; complexity in the
  recall library is the most expensive complexity in the repository.
* A measured rejection should be visible in the code, not only in a report.
* Deleting the apparatus must not delete the reason, or the layer gets rebuilt.
* `_querycache.py` was extracted from the scene experiment and is now shared;
  removal must not take it along.
* The idea is not dead — the same research measured a real ceiling — so the
  record has to state precisely what failed and what would reopen it.

## Considered Options

* Remove the layer entirely and record the decision in an ADR.
* Keep everything and leave the toggle off.
* Remove the production path, keep the experiment apparatus.
* Re-measure on the grown corpus before deciding.

## Decision Outcome

Chosen option: **remove the layer entirely and record the decision here.**

**Why not "keep everything".** An inert branch in the hot-path read library is
the expensive kind of dead code. It is not free to carry: it constrains every
future change to recall, and it reads to a newcomer as a capability that works.

**Why not "remove production, keep the experiment".** This is not available.
`scene-experiment.py` drives `kb_recall.recall_hits(..., scene_prior=...)` — the
experiment measures the production path. Removing `scene_prior` from
`kb-recall.py` guts the experiment either way, so the choice is all-or-nothing.

**Why not "re-measure first".** The measurement attributed the failure rather
than merely observing it. A placebo arm with the same scene count, size
histogram and coverage but random membership scored +0.000, and the oracle arm
scored +0.040 (p < 0.0001): the mechanism works and the clustering is what
fails. Corpus growth does not make graph communities roughly fivefold better at
grouping question-relevant pairs. The latency condition is worse still — it is
structural, and a larger corpus moves it the wrong way. Re-measuring would also
need a fresh baseline, since recall numbers are only comparable within the same
index state on the same day, and the unspent holdout should not be spent on a
configuration whose outcome is predicted.

### The winner rule, and how it failed

An arm shipped only if all four held on dev. On the best arm, all four failed:

| Condition | Required | Measured |
| --- | --- | --- |
| recall@5 | >= +0.02 | +0.000 |
| recall@1 | no decrease | -0.006 |
| p50 latency | < +5 ms | +65 ms |
| memory_type groups improved | >= 2 of 4 | 1 of 4 |

### What is removed

`scripts/_scenes.py`, `scripts/build-scene-index.py`,
`scripts/scene-experiment.py`, `scripts/scene-report.py`, their four test files,
the `scene_prior` plumbing in `kb-recall.py` and `kb-eval.py`, the
`scene_retrieval` / `scene_clusterer` / `scene_floor` / `scene_boost` knobs in
`kb-retrieve.py` and `_settings.py`, and the toggle's entries in the settings
command and the upgrade skill.

### What is deliberately kept

`docs/research/l2-scene-retrieval-2026-08.md`, the design spec, the
implementation plan and the CHANGELOG history. Those are the record of a
measured decision; deleting them would leave a future reader with an absent
feature and no reason, which is an invitation to rebuild it.

`_querycache.py` stays. It was extracted from the scene experiment in TASK-190
and is now used by rank-factors and rerank-ceiling; it has outlived its origin.

### What would reopen this decision

The oracle arm is the reason this is a removal and not a refutation. A
clustering that cannot be blamed — gold memory and a retrieved memory placed in
the same scene, with filler so sizes match community's shape — scored recall@5
0.796 against a 0.756 baseline, winning 39 and losing 5, surviving Bonferroni
correction over every arm in the study. Community clustering, by contrast, won 7
and lost 7 at every seeds setting.

So the tier is worth roughly +0.040 recall@5 **if** a clusterer exists that
beats graph communities by about fivefold. Of the three clusterers measured, one
produced a usable index; the LLM (large language model) variant died on a single-shot 32k-token prompt
over 1508 notes, and a chunked formulation was deliberately not built because
that task measured three clusterers rather than building a fourth. Chunked LLM
clustering is therefore the open thread, and it needs new code regardless of
whether this plumbing survives.

Reopening requires a clusterer that clears the same winner rule on a fresh
baseline. Re-adding the plumbing without one recreates exactly what this ADR
removes. When a measurement does clear the rule, delete
`tests/test_no_scene_layer.py` in the same change that re-adds the layer.

MADR 4 (Markdown Any Decision Records) is used for consistency with ADR-005 through ADR-007, and because the
option structure is the load-bearing part here: the "keep the experiment"
compromise looks obviously right until the call graph rules it out.

### Confirmation

Verification requires:

* `tests/test_no_scene_layer.py` proving `recall_hits`/`memory_hits` carry no
  `scene_prior`, no scene script ships, no scene knob is read, and both the
  research report and this ADR survive;
* the same file proving `_querycache.py` still exists;
* the full pytest suite green with the four scene test files removed rather
  than skipped;
* a repository-wide sweep showing no `scene` identifier left in `scripts/`
  outside `_querycache.py`'s docstring note about its own origin.

## Related Decisions

None supersedes or is superseded by this decision. Adjacent context:
`0001-embedding-model-default.md` chose the embedding model whose vectors the
scene index was built from, and the
`graph_retrieval` toggle (TASK-87, no ADR) is the surviving graph-based
retrieval feature this layer is often confused with — that one passed its A/B
gate and stays.

## References

* `docs/research/l2-scene-retrieval-2026-08.md` — the full measurement this
  decision rests on (winner rule, placebo, oracle ceiling).
* `docs/superpowers/specs/2026-08-05-l2-scene-retrieval-design.md` — the design
  and the pre-registered winner rule.
* `tests/test_no_scene_layer.py:1` — the guard that keeps the removal honest.
* TASK-134 (measurement) and TASK-205 (this removal) in `backlog/tasks/`.
* MADR profile: <https://adr.github.io/madr/>

## Consequences

Good: the hot-path read library loses a branch nothing reached; roughly 1800
lines leave the repository; a measured rejection becomes visible in the code
rather than living only in a report.

Bad: resuming the experiment now costs restoring the schema and clusterers from
git history rather than flipping a toggle. This is accepted because the follow-up
needs a clusterer that does not exist, so it is new work either way.

Neutral: `kb-scene.db` may remain in deployed vaults. It is derived, has no
automated builder, and can be deleted at any time.
