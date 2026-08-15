---
id: TASK-177
title: Autonomous skill evolution between sessions (owner-approved)
status: To Do
assignee: []
created_date: '2026-08-15 22:20'
updated_date: '2026-08-15 22:20'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner decision, 2026-08-15: copy EverOS's autonomous skill evolution
(github.com/EverMind-AI/EverOS, Apache 2.0 — "agent skill records stored as
.md files", refined between sessions as part of offline memory evolution).
This deliberately overrides the propose-and-stop boundary the field review
recorded for skills: evolution of an EXISTING skill runs autonomously.
Creation of a NEW skill (TASK-175 promotion) still proposes — a new behavior
surface is a different risk than refining one that already exists. The owner
can flatten that split later; it is recorded here so the asymmetry is a
decision, not an accident.

Why this fits the vault's own principles rather than fighting them:
PRINCIPLES.md #3 says what requires manual discipline does not happen, and the
memory subsystem already runs autonomously behind quality gates (judge,
quarantine, default-on toggles). Skills are agent-facing procedures, not the
curated wiki — editor-in-chief applies to knowledge a human reads, and a skill
is executed, not read. The reversibility net is git, which the vault already
trusts as the wiki's safety floor.

Mechanism (KennisBank-native, not a port of EverOS's):

- **Off the hot path.** Runs at session end or idle, behind a settings toggle,
  default on (the memory-subsystem precedent: core functionality defaults on,
  uitzetbaar). Never at session start, never at recall.
- **Evidence in, prose out.** Input is what the session actually shows: usage
  telemetry (which skills were exercised), the transcript's evidence of a step
  failing, a flag changing, a better sequence — the same session sources the
  memory sweep already reads. The pass rewrites the skill .md with the change.
- **The grounded-verifier asymmetry applies** (llm-trust-verification,
  TASK-163): a skill may be strengthened or extended autonomously on grounded
  evidence; a weakening or removal of a step demotes to a proposal. Supported
  is trustworthy, unsupported is right half the time — the same reason memory
  status can be promoted on evidence but not demoted on one verdict.
- **Every evolution is a git commit** with the evidence reference in the
  message, plus an append to a skill-evolution log (the closed-log pattern
  from TASK-150/155: nothing changes invisibly, everything has a way back).
  Provenance stamped in frontmatter: model_id + prompt version, the TASK-90 E5
  pattern, so a bad prompt generation is selectable afterwards.
- **kb-state-audit is a hard gate:** an evolution that would contradict the
  config/constants authority does not write; it files as a contradiction
  finding instead.
- **No autonomous deletion.** A skill the evidence says is obsolete gets
  `status: deprecated` proposed, never removed.
- **Silent when idle** (principle #4): no sessions touching a skill means no
  run, no output, no log entry.

Design-first: this is a behavior-changing subsystem, so a design doc in
docs/superpowers/specs precedes implementation, and reading EverOS's
skill-record format and refinement pass (Apache 2.0 — reuse with notice is
allowed) is part of that design work, as already noted in TASK-175.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Design doc in docs/superpowers/specs, including what was learned from EverOS's implementation and where this design deliberately differs
- [ ] #2 Evolution pass runs off the hot path behind a default-on toggle; session start and recall latency are unchanged
- [ ] #3 Strengthen/extend runs autonomously on grounded evidence; weaken/remove/deprecate demotes to a proposal — the asymmetry is enforced in code, not convention
- [ ] #4 Every autonomous change is a git commit with evidence reference, a log entry, and frontmatter provenance (model_id + prompt version); a human can revert any evolution with plain git
- [ ] #5 An evolution contradicting kb-state-audit's authority does not write
- [ ] #6 A session that exercises no skill produces no run and no output
- [ ] #7 Measured on real sessions before default-on ships: a sample of autonomous evolutions is hand-checked and the acceptance rate recorded — if a human would have rejected most of them, the default flips to proposal mode and that is the finding
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->
