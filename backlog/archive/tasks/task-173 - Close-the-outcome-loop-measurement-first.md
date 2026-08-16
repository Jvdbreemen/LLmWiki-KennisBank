---
id: TASK-173
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
clear the bar TASK-160/TASK-161 established for ranking changes: the factor
decomposition showed hand-tuned multipliers can cost 272 questions while
looking principled, and the eval set cannot currently see what an outcome
signal is for — the same blindness TASK-161 records for recency.

Constraints: off the hot path entirely (session-end or idle, never recall-time);
local only; and no outcome heuristic that requires the user to remember to do
something, per principle #3.

PRIOR ART, found 2026-08-15 and to be read before designing: PROJECTMEM
(arXiv 2606.12329, https://github.com/riponcm/projectmem, paper CC-BY-4.0) —
"a local-first, event-sourced memory and judgment layer for AI coding agents",
whose judgment layer assesses "whether specific memories or decisions proved
beneficial or harmful during task execution". That is this task's question,
asked in this task's niche, with the same local-first constraint. Maturity
unknown (single-author repo), so treat it as a design to learn from and a
mistake-list to avoid, not a dependency. Two things to extract on reading: how
they define the outcome signal for a coding session, and how they attribute an
outcome to individual memories rather than to the session as a whole — the
attribution step is where this task expects the noise to live. Note the market
observation from the Honcho addendum still stands (no *product* sells this),
but "nobody has tried" is now false in the literature and the task descriptions
should not claim otherwise.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A weak per-session outcome signal is defined and derived from sources that already exist locally, with its failure modes stated
- [ ] #2 Injected stems are linked to the outcome of the session they were injected into
- [ ] #3 Nothing runs on the hot path; recall latency is unchanged and shown to be unchanged
- [ ] #4 A first correlation report: do stems in good-outcome sessions differ measurably from stems in bad-outcome ones
- [ ] #5 Explicitly out of scope: using the signal in ranking (separate task, gated on an eval set that can see it — the TASK-161 requirement applies to this signal too)
- [ ] #6 States what it would take to price the benefit side of a corpus-growth decision, so the TASK-145 cap question can eventually be reopened on full evidence
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->

## Close-out (2026-08-16) — parked

Parked, and the largest open direction in the memory strategy: nothing records whether an injected memory helped, so a memory that derailed a session still scores like one that saved an hour. Verified nothing shipped — kb-session-end.py has no outcome derivation, _usage.py's pending table links stems to a session_id only transiently and is cleared at session end, and docs/research/ has no correlation report. The binding evidence lives in docs/research/recall-after-growth-2026-08-14.md (corpus-growth decisions made on half the evidence), docs/research/agent-memory-field-review-and-strategy.md, and CHANGELOG Unreleased which names this task as the queued answer; the PROJECTMEM prior-art pointer (arXiv 2606.12329) lives only in this description, so keep it with the archive. Emphatically not do-now: signal definition, stem-to-outcome linking, latency proof, and a correlation report are a multi-day measurement project, and TASK-145's frozen caps stay frozen until it exists.

**Evidence:** scripts/kb-session-end.py has no outcome signal (its only 'outcome' is job-runner logging at lines 222-225); scripts/_usage.py links stems to sessions only via the transient pending table (cleared per session), records injected/used/noise but never outcome; no correlation report in docs/research/; CHANGELOG.md:36-38 names TASK-173 as 'the queued answer' to the one gap that survived all three strategy derivations.

**Remaining work (when reopened):** Read PROJECTMEM for its outcome definition and attribution step; define a weak per-session outcome signal from sources that already exist locally (commit landed, suite green, injected memory contradicted/superseded shortly after); persist the injected-stems-to-session link past session end and join it to the signal; produce the first correlation report; show recall latency unchanged; state what would price the benefit side of corpus growth so TASK-145 can reopen on full evidence. Ranking on the signal stays a separate task per AC#5.
