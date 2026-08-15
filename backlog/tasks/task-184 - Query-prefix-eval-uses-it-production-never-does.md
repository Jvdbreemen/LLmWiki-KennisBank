---
id: TASK-184
title: Query prefix: eval uses it, production never does
status: To Do
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

_embeddings.embed() gained kind="query"/"doc" prefixes; the index build
applies the doc prefix and embed_id() folds it into the index identity.
The eval harnesses embed queries with kind="query" (kb-eval.py:191,
rerank-eval.py:138, recall-ablation.py:153) — but no production path
does: kb-retrieve.py:353, kb-search.py:155, kb-presearch.py:116, kb-mcp,
kb-ask, and both sidecar call sites embed bare. The moment a query prefix
is configured (the module's own docstring recommends one for qwen3 and
calls e5-instruct without it 'a different model than you meant to
measure'), kb-eval — which claims production parity — measures prefixed
retrieval while the live hook runs unprefixed against doc-prefixed
vectors, silently and permanently.

Adjacent: embed_id() folds only the DOC prefix, so query-side caches
keyed on it (scene-experiment QueryCache, reused by rank-factors and
rerank-ceiling) survive a query-prefix change and mix vector spaces.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 One embed_query() seam used by every production query path and the evals alike; call sites cannot forget the kind
- [ ] #2 A guard test asserts the production hook path sends the configured query prefix
- [ ] #3 Query prefix participates in the identity used by query-vector caches, or those caches key on both prefixes
- [ ] #4 rank-factors.py and rerank-ceiling.py embed queries the same way as the rest of the eval family
<!-- AC:END -->
