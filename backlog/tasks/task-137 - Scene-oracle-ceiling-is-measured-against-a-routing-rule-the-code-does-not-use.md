---
id: TASK-137
title: Scene oracle ceiling is measured against a routing rule the code does not use
status: To Do
assignee: []
created_date: '2026-08-11 06:15'
labels:
  - bug
  - retrieval
  - measurement
dependencies: []
references:
  - scripts/scene-report.py
  - scripts/kb-recall.py
  - docs/research/l2-scene-retrieval-2026-08.md
priority: medium
ordinal: 131700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`scene-report.py::oracle_ceiling` counts a missed question as reachable when the gold memory shares a scene with **any** of the retrieved hits. `kb-recall.py::_scene_members_for` nominates a scene from the **top hit only** (`prior["seeds"]`, default 1). The reported ceiling is therefore an upper bound on a mechanism that is not the one running.

Measured on the TASK-134 dev split (209 baseline misses at k=5):

| Clusterer | reachable from the top hit | reachable from any of the top 5 |
| --- | --- | --- |
| community | 14 | 47 |
| oracle upper bound | 120 | 166 |

For the community clusterer that is the difference between a ceiling of +0.016 recall@5 and the +0.055 the report printed. The winner rule demands +0.02, so the shipped configuration was judged against a bound its own routing could never reach — the null result was derivable from the code before any arm ran.

The docstring of `_scene_members_for` already documents this failure mode for centroid routing ("the implementation could not realise the bound it was being judged against"). The switch to top-hit routing kept the gap; nobody re-derived the bound afterwards.

Two defensible fixes: make `oracle_ceiling` take the seeds parameter and count only scenes nominated by the first N hits, or report both numbers side by side and label which one the current configuration can realise. Either way the ceiling must never be quoted without the routing rule it assumes.

Found while measuring TASK-134; see docs/research/l2-scene-retrieval-2026-08.md, section "Follow-up".
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 oracle_ceiling accounts for the seeds routing rule, or prints the top-hit and any-hit bounds separately with an explicit label
- [ ] #2 A test pins the reachability count for a fixture where the gold shares a scene with hit 3 but not hit 1, proving the two bounds differ
- [ ] #3 docs/research/l2-scene-retrieval-2026-08.md is not silently invalidated: any ceiling it quotes states the routing rule it assumes
- [ ] #4 python -m pytest tests -q is green
<!-- AC:END -->
