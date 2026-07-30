---
id: TASK-113
title: >-
  Figure spec: resolve the seven-component contradiction with the C4 component
  model
status: To Do
assignee: []
created_date: '2026-07-30 05:43'
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
- [ ] #1 The contradiction is stated explicitly in the task notes: c4-component.md's seven are Retrieval Engine, Knowledge Processing, Index Store, Agent Integration, Atlas App, Measurement and Outward Integration, and Distribution and Quality Gate. The figure spec's Part G counts H1, D1 to D4, R2 and the S1+S2 storage layer as seven, which promotes storage to a component and demotes Distribution and Quality Gate (drawn as M1) out of the count
- [ ] #2 A single interpretation is chosen and justified in one or two sentences: either storage is a component (and the component model is amended) or M1 is the seventh component drawn deliberately outside the boundary (and the figure spec is amended)
- [ ] #3 Part A3 item 7 and the Part G checklist are reworded to match the chosen interpretation, with no remaining sentence claiming seven component boxes inside the boundary if the seventh is drawn outside it
- [ ] #4 c4-component.md is left factually unchanged unless the chosen interpretation requires amending it; if it is amended, the change is a decision recorded in the task, not a silent edit
<!-- AC:END -->
