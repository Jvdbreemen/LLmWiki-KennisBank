---
id: TASK-171
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

External evidence raising the prior (added 2026-08-15): Hindsight (arXiv
2512.12818, MIT, the top LongMemEval scorer at 94.6%) is built on exactly this
axis — three epistemically distinct memory networks (world facts, experience,
opinions) with separate extraction and retrieval per network — and its ablation
found that collapsing the networks into unified storage "substantially reduces
reasoning quality, particularly when distinguishing between observed facts and
derived beliefs." That is the strongest published support yet for the axis this
task gates on. It does not replace the local measurement (their corpus is
conversational, this vault is not), but it moves the expected outcome: the
question is now less "does the axis matter" and more "does it matter at this
vault's scale and error profile."

Instrument note (added after the v0.31.1 rebase): the grounded verifier from
docs/research/llm-trust-verification-2026-08-15.md is the natural measuring
tool here — it already judges a memory against its own source passage,
deterministically at temperature 0, and TASK-163 is making its verdicts usable.
"Stated versus inferred" is a finer cut of the same question that verifier
answers ("does this passage say this"), so the measurement this task gates on
should reuse that machinery rather than invent a second judge. Its measured
asymmetry also applies here: `supported` is trustworthy, `unsupported` is right
about half the time, so a fragment may be *promoted* to stated on evidence but
never demoted to inferred on a single verdict.
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

## Close-out (2026-08-16) — parked

Parked, nothing started: the gate measurement (what fraction of wrong-recall cases on the memory eval set are inferences presented as fact) has not been run and no schema field exists. The instrument it prescribes is now real — the grounded verifier (scripts/_groundcheck.py, scripts/kb-verify.py, TASK-163 Done) plus kb-memory-eval-set.example.json — so the task is executable, just not started. The direction and its evidence live in docs/research/honcho-memory-architecture.md (queued item, CHANGELOG Unreleased), plus the Hindsight (arXiv 2512.12818) prior recorded in this task's description; archiving the task loses nothing beyond the description itself, so keep the Hindsight and verifier-asymmetry paragraphs with wherever it lands. Not do-now: it needs an eval run, isolation of wrong-recall cases, and per-case labeling — multi-hour.

**Evidence:** No stated/inferred field in scripts/ (grep: only false positives in rerank-ceiling.py docstrings); no measurement doc in docs/research/; CHANGELOG.md:44-49 (Unreleased) records it as queued behind a measurement. Instrument now shipped: scripts/_groundcheck.py + scripts/kb-verify.py (TASK-163 Done), eval set kb-memory-eval-set.example.json present.

**Remaining work (when reopened):** Run the memory eval against the deployed vault, collect the wrong-recall cases, label each as inference-presented-as-fact vs other (reusing kb-verify.py grounded verdicts; promote-to-stated on supported only, per the measured verdict asymmetry), write the measurement to docs/research/, then either close as measured-and-rejected or add a judge-assigned field to the quality gate.
