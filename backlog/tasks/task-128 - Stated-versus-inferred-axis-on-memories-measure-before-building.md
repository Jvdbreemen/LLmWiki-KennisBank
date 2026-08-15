---
id: TASK-128
title: Stated versus inferred axis on memories — measure before building
status: To Do
assignee: []
created_date: '2026-08-15 10:00'
updated_date: '2026-08-15 10:00'
labels: []
dependencies: []
ordinal: 102300
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Adopted from the Honcho review (see docs/research/honcho-memory-architecture.md),
with a deliberate measurement gate in front of it.

Honcho separates *deductive* conclusions (the peer stated this) from *inductive*
ones (the peer probably prefers this). KennisBank has three axes that each cover
part of that distinction and none of it cleanly:

- `status` — unverified | current | superseded | retracted | expired: has this
  been judged, not how it was arrived at.
- `evidence_basis` — getypt | cc-sessie | audio | import | autoresearch | agent:
  the channel it arrived through. `getypt` is close to "stated" and
  `autoresearch` close to "inferred", but both conflate channel with inference:
  a `cc-sessie` fragment may be a verbatim quote or a model's generalisation.
- `memory_type` — feit | voorkeur | procedure | beslissing: what kind of claim.

So an inference dressed as a fact is currently indistinguishable from a quoted
fact once both reach `status: current`. That matters directly for the system's
first non-negotiable constraint (no wrong or stale recall): the two failure
modes are not equally likely, and one score cannot express both.

Gate before building: this is a schema change to the layer whose ranking is
already tuned, so it earns its place only with a number. Run against the memory
eval set (kb-memory-eval-set.example.json) and answer: of the wrong-recall
cases, what fraction are inferences presented as facts? Below a meaningful
threshold, close this and record the measurement — the axes above are enough.
Above it, add the field and let the quality gate weigh it.

Anti-goal: a fourth overlapping axis that authors must reason about at capture
time. If it ships it must be judge-assigned, never hand-maintained.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Measurement over the memory eval set: what fraction of wrong-recall cases are inferences presented as stated fact
- [ ] #2 The measurement is written down with its method, whichever way it points
- [ ] #3 If below threshold: task closed as measured-and-rejected, no schema change
- [ ] #4 If above threshold: field is judge-assigned at capture, never hand-maintained, and the quality gate weighs it
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->
