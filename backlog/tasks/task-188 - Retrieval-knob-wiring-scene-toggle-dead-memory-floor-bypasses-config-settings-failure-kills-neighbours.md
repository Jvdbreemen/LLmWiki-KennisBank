---
id: TASK-188
title: Retrieval knob wiring: scene toggle dead, memory floor bypasses config, settings failure kills neighbours
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

Three knob-wiring defects in the retrieval path, one task because they
share the retrieve_params contract ('any new retrieval knob must be added
here, not resolved inline'):

1. scene_retrieval is declared in _settings.DEFAULTS and its knobs
resolved in retrieve_params (kb-retrieve.py:196), but no production path
reads the toggle or passes a scene_prior — the documented setting is a
silent no-op, the exact DEFAULTS-toggle-no-surface-honors drift
test_knob_consistency.py was written against. Wire it or remove the key
until the pre-registered winner rule is met; add it to the knob guard
either way.

2. MEMORY_MIN_COS (kb-recall.py:400, 0.60->0.45 recalibration) is read
once at import from KB_MEMORY_THRESHOLD only — no config key, bound into
memory_hits' default argument, unre-tunable in long-lived processes (MCP
server, sidecar) and invisible to kennisbank-embed.json tuning.

3. kb-recall.py:182: when _settings fails to load, the except branch sets
use_graph=False — silently disabling a default-ON feature; the legacy
fallback that still produced a neighbour was removed in the same release.
The except branch should match the shipped default (True).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 scene_retrieval either reaches production retrieval or the settings key is removed; covered by test_knob_consistency
- [ ] #2 Memory floor resolves through retrieve_params (env + config key + default), passed per call
- [ ] #3 Settings-load failure preserves the documented graph_retrieval default instead of inverting it
- [ ] #4 Eval harness and hook resolve all three identically (TASK-86 parity holds)
<!-- AC:END -->

## Close-out (2026-08-16)

Fixed on chore/backlog-zero: scene_retrieval is wired through scene_prior_params() (one resolver for hook and eval, default OFF), the memory floor resolves per call via retrieve_params with the new memory_threshold config key, and a failed _settings LOAD no longer silently disables the default-ON graph neighbor. Guards: floor must agree across three surfaces; every retrieval toggle must have a production reader.
