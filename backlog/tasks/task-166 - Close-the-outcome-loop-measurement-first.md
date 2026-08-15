---
id: TASK-166
title: Close the outcome loop — measurement first
status: To Do
assignee: []
created_date: '2026-08-15 11:00'
updated_date: '2026-08-15 11:00'
labels: []
dependencies: []
ordinal: 102700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the field review (docs/research/agent-memory-field-review-and-strategy.md).
This is the one item that changes what category of system KennisBank is.

The field's central distinction for long-term memory is Experience (knowledge
validated by task outcomes) versus Memory (information without reference to
outcomes). KennisBank captures experience-shaped content — lessons, bug fixes,
decisions, dead ends — and stores it as memory-class records: everything the
system knows about a fragment's worth is assigned before it is ever used.
`importance` and `status` come from the judge at capture, `trust_factor` from
`evidence_basis`. The one post-hoc signal, usage telemetry, answers *was it
referenced*, not *did it help*. A memory that was injected, read, and sent the
session down a wrong path scores exactly like one that saved an hour.

PRINCIPLES.md #5 promises the outcome side ("niet twee keer dezelfde fout"). The
loop that would deliver it does not exist.

THIS IS ALREADY BINDING, and the project reached the same conclusion from the
other direction. docs/research/recall-after-growth-2026-08-14.md, on the sweep
that grew the corpus 14% and failed the pre-registered recall gate:

  "The set cannot answer whether new captures are useful, only whether they
   crowd. Questions generated from memories written after the baseline would
   measure the other side of the trade, and until that exists every
   corpus-growth decision is being made on half the evidence."

The eval set prices the cost of a bigger corpus (dilution at k) and cannot price
the benefit (a memory that answered something), because benefit is an outcome and
nothing records outcomes. TASK-145's caps were correctly frozen on that half-
evidence. Every future capture-versus-precision decision hits the same asymmetry:
the cost is measurable, the benefit is not, so the system optimises toward a
smaller tidier corpus — the opposite of what it is for.

The cheap version needs no RL and no trajectory modelling. The session-end hook
exists, transcripts are archived, and injected stems are already logged. What is
missing is a weak outcome signal per session — did it end in a commit, did the
suite go green, was an injected memory contradicted or superseded shortly after —
and a link from that signal back to the stems injected into that session. Weak
and noisy, and still strictly more than the system has now.

SCOPE OF THIS TASK IS MEASUREMENT ONLY. Land the link, look at whether outcome
correlates with anything, and stop. Ranking on it is a separate decision that
must pass the TASK-163 bar; a signal this noisy could easily make retrieval worse
while looking principled.

Constraints: off the hot path entirely (session-end or idle, never recall-time);
local only; and no outcome heuristic that requires the user to remember to do
something, per principle #3.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A weak per-session outcome signal is defined and derived from sources that already exist locally, with its failure modes stated
- [ ] #2 Injected stems are linked to the outcome of the session they were injected into
- [ ] #3 Nothing runs on the hot path; recall latency is unchanged and shown to be unchanged
- [ ] #4 A first correlation report: do stems in good-outcome sessions differ measurably from stems in bad-outcome ones
- [ ] #5 Explicitly out of scope: using the signal in ranking (separate task, must pass the TASK-163 bar)
- [ ] #6 States what it would take to price the benefit side of a corpus-growth decision, so the TASK-145 cap question can eventually be reopened on full evidence
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->
