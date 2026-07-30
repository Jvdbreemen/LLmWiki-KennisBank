---
id: TASK-113
title: >-
  Figure spec: resolve the seven-component contradiction with the C4 component
  model
status: Done
assignee:
  - '@claude'
created_date: '2026-07-30 05:43'
updated_date: '2026-07-30 17:55'
labels:
  - docs
  - c4
  - architecture
dependencies: []
ordinal: 115700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The drawing specification and c4-component.md both claim seven components, but they do not agree on which seven, so a reader who trusts one is misled about the other. This is a semantic decision, not a typo: it needs a deliberate choice, then consistent wording.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The contradiction is stated explicitly in the task notes: c4-component.md's seven are Retrieval Engine, Knowledge Processing, Index Store, Agent Integration, Atlas App, Measurement and Outward Integration, and Distribution and Quality Gate. The figure spec's Part G counts H1, D1 to D4, R2 and the S1+S2 storage layer as seven, which promotes storage to a component and demotes Distribution and Quality Gate (drawn as M1) out of the count
- [x] #2 A single interpretation is chosen and justified in one or two sentences: either storage is a component (and the component model is amended) or M1 is the seventh component drawn deliberately outside the boundary (and the figure spec is amended)
- [x] #3 Part A3 item 7 and the Part G checklist are reworded to match the chosen interpretation, with no remaining sentence claiming seven component boxes inside the boundary if the seventh is drawn outside it
- [x] #4 c4-component.md is left factually unchanged unless the chosen interpretation requires amending it; if it is amended, the change is a decision recorded in the task, not a silent edit
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The contradiction, stated precisely.

c4-component.md names seven components: Retrieval Engine, Knowledge Processing, Index Store, Agent Integration, Atlas App, Measurement and Outward Integration, and Distribution and Quality Gate. Storage is not among them; the SQLite databases and the vault filesystem appear there as external systems, alongside Ollama, the harness and GitHub.

The figure spec's Part G checklist counted a different seven: H1, D1 to D4, R2, and S1+S2 taken together as a storage layer. That promotes storage to a component and drops Distribution and Quality Gate out of the count, even though the plate already draws it as M1. Part A3 compounded it by asserting seven component boxes inside the boundary, which cannot be true if the seventh is deliberately drawn outside.

Interpretation chosen: the component model is the authority, and the plate was already right. It draws all seven components (H1, D1 to D4, R2 inside the boundary, M1 below it) and correctly treats S1, S2, R1 and R3 as external systems. Only the spec's own arithmetic was wrong, so only the spec changed.

c4-component.md was left untouched, as the last acceptance criterion requires. Nothing in it needed amending under this interpretation, which is itself an argument for the interpretation: the alternative would have required editing the level that the drawing is derived from.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Resolves a contradiction between the drawing specification and the C4 component model, where both claimed seven components and disagreed on which seven.

c4-component.md's seven are Retrieval Engine, Knowledge Processing, Index Store, Agent Integration, Atlas App, Measurement and Outward Integration, and Distribution and Quality Gate. Storage appears there as an external system, not a component. The figure spec's Part G instead counted the storage layer as a component and excluded Distribution and Quality Gate, while Part A3 asserted that all seven boxes sit inside the boundary.

Resolved in favour of the component model, because the plate already draws all seven correctly: six inside the boundary (H1, D1 to D4, R2) and the seventh, M1, outside it precisely because it never runs inside a session. Only the spec's own counting was wrong.

Part A3 and the Part G checklist now say six inside plus M1 outside, and name S1, S2, R1 and R3 as external systems that are not counted. c4-component.md is unchanged.

Tests: tests/test_docs_consistency.py, 5 passed.
<!-- SECTION:FINAL_SUMMARY:END -->
