---
id: TASK-179
title: Usage detection — close the in-context blind spot and verify per client
status: To Do
assignee: []
created_date: '2026-08-15 22:40'
updated_date: '2026-08-15 22:40'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner directive, 2026-08-15: "make sure usage detection works." Read of the
pipeline (kb-retrieve pending → kb-usage-scan at SessionEnd) says it works as
specified and the specification has a structural blind spot.

THE BLIND SPOT. kb-usage-scan counts a stem as used only when it appears in a
tool-call INPUT (a Read of the article). Assistant text is deliberately
excluded (a model naming a stem proves nothing) and hook/user messages are
excluded (the injection would count itself). Both exclusions are locally
sound — and their intersection is that the most successful injection is
invisible: when the injected snippet was sufficient, the agent acts on it
without ever issuing a Read, and the memory scores "not used". Detection is
anti-correlated with injection quality at exactly the point where injection
works best.

This is the likely reason usage_factor measured as indistinguishable from
noise in rank-factors-2026-08-14 (10 gained / 13 lost, p = 0.68): the factor
may be fed by a signal that fires mainly on the failure mode (snippet
insufficient, agent had to open the file). Nobody can currently tell weak
signal from broken sensor — which is what this task fixes: MEASURE DETECTION
ITSELF, not its downstream rank effect.

Method: labelled synthetic sessions, per client (Claude Code, Codex, Copilot
CLI — transcript formats differ and the scan assumes Claude-style JSONL;
verify each adapter's SessionEnd path actually feeds the scan). Three
labelled cases per client: (a) injected and used via a tool call, (b)
injected and used in-context only — the snippet visibly steered the answer,
no Read, (c) injected and genuinely ignored. Report the confusion matrix.
Case (b) is the one that matters; today it is guaranteed to score as (c).

Candidate fixes to evaluate AGAINST that measurement, not before it:
- count a wikilink/stem reference in the assistant's FINAL message (the
  injection asks the agent to cite; distinguish citing from mere mention);
- content-overlap between the injected snippet and subsequent assistant
  actions (fuzzy — may be unmeasurable in practice; if so, record that);
- an explicit cheap protocol: the injection block asks the agent to emit a
  one-line `[kb-used: stem]` marker when an injected memory materially
  helped — detection becomes exact at the cost of prompt space (and its
  failure mode, the agent not complying, is measurable per client).

Also verify plumbing while in there: pending is cleared even when the
transcript is missing (silent data loss, fail-open by design — count how
often it happens in practice); the 20 MB transcript cap; stems short enough
to substring-collide.

Downstream dependents, why this matters beyond hygiene: TASK-178's
autonomous noise-marking must not run on a detector that mistakes "snippet
sufficed" for "never used"; TASK-175's promotion gate reads recall
frequency from this data; TASK-173's outcome loop attributes outcomes to
injected stems. All three inherit whatever this sensor gets wrong.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Labelled synthetic sessions per client (Claude Code, Codex, Copilot) covering used-via-tool-call, used-in-context, and ignored; confusion matrix reported
- [ ] #2 The in-context case (b) is detectable by some shipped mechanism, or the measurement shows why every candidate fails and that is recorded as the finding
- [ ] #3 Each client's SessionEnd path is verified to actually feed kb-usage-scan with a readable transcript; gaps fixed or documented
- [ ] #4 Missing-transcript frequency measured; if material, pending entries survive to the next session instead of being cleared
- [ ] #5 Detection changes are measured against the labelled set before shipping; the rank-factor question (weak signal vs broken sensor) gets an explicit answer
- [ ] #6 TASK-178 and TASK-175 are unblocked or explicitly told what the sensor still cannot see
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->
