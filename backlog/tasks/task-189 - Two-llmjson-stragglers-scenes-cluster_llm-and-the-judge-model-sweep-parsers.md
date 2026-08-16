---
id: TASK-189
title: Two _llmjson stragglers: scenes cluster_llm and the judge-model-sweep parsers
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

_llmjson.py was added to eliminate the wide-span raw.find('{')/rfind('}')
parse and its silent-{} failure mode, and production (_judge, _reconcile,
_extract) migrated. Two stragglers in the same release:

1. _scenes.py:232 cluster_llm writes the wide-span pattern fresh — a
model appending commentary after its JSON yields {} -> 'no scenes' ->
baseline recall, precisely the failure the module documents as 'exactly
the wrong one'.

2. judge-model-sweep.py:188-229: three parse_* functions claim to mirror
production parses that no longer exist — the harness scores candidate
models against a stricter parser than production runs, misreporting
parse-failure rates and steering the judge-model choice on wrong data
(its own docstring names this drift as the thing to avoid).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 cluster_llm parses via _llmjson.first_object
- [ ] #2 The sweep's three parsers delegate to _llmjson + per-seam field checks, so they cannot drift from production
- [ ] #3 A repo-wide grep guard rejects new wide-span find/rfind JSON parses in scripts/
<!-- AC:END -->
