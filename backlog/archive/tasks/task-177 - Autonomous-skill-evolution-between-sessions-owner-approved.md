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

**Model policy (owner constraint, 2026-08-15): the rewrite ALWAYS uses the
client model — the best one available — never the local judge model.** A
skill is agent-facing prose whose quality ceiling is the model that writes
it; the local 4b is measured and kept for gating, not authoring. Concretely:

- The evolution rewrite goes through the client channel — `_llm.py` already
  ships an opt-in `claude-cli` provider that shells the `claude` binary on
  the user's existing auth; the design doc extends the same pattern to the
  Codex and Copilot CLIs so every installed client can serve its own model.
- "Best" is an explicit, documented ordering over the models the installed
  clients expose (strongest available first), resolved at run time — not a
  hardcoded model id that rots. If no client channel is available, the pass
  SKIPS and logs; it never silently falls back to the local model for the
  rewrite.
- The division of labor stays: client model writes, local grounded verifier
  gates (the asymmetry above), deterministic rails decide. The verifier and
  kb-state-audit remain local, so the quality gate never depends on a cloud
  call.
- Consent boundary: the client model is the channel the owner already uses
  for sessions, but this task sends SKILL CONTENT through it in background
  runs. That is inside the existing claude-cli consent boundary (C4 records
  claude-cli as a cloud provider) and must be named in the design doc and
  the toggle's documentation — the "lokaal, altijd" default is deliberately
  overridden here by owner decision, for this pass only.

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
- [ ] #8 The rewrite is produced by the client model, selected best-first from an explicit documented ordering resolved at run time; no client available means skip-and-log, never a silent local fallback
- [ ] #9 Gating stays local: grounded verifier and kb-state-audit run on the local model regardless of which client model wrote the rewrite
- [ ] #10 The consent boundary documentation names this pass as sending skill content through the client channel in background runs
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->

## Close-out (2026-08-16) — parked

Nothing started: no design doc in docs/superpowers/specs, no evolution pass, no EverOS format study on record. Parked with its direction fully preserved in this task's description (owner decision 2026-08-15, commit 5da8c3b) and the EverOS section of docs/research/agent-memory-field-review-and-strategy.md. One thing changed since filing that lowers the design risk: kb-autoreview.py (TASK-195, PR #132) shipped the exact 'client model writes, local verifier gates, behind an explicit cloud-consent toggle' pattern ACs #8-#10 call for — the design doc should reuse that channel rather than invent one. Design-first, behavior-changing, multi-day: not a do-now.

**Evidence:** No design doc: docs/superpowers/specs/ listing contains nothing on skill evolution (latest spec is 2026-08-16-autonomous-memory-review-design.md). No code: grep 'EverOS|skill evolution' hits only task files and the research doc. TASK-175 (new-skill promotion, the paired half) still status: To Do. Precedent now shipped: scripts/kb-autoreview.py (TASK-195, PR #132, commit 10993ac) implements the client-LLM-writes/local-gates channel behind auto_review_llm.

**Remaining work (when reopened):** Design doc in docs/superpowers/specs (incl. EverOS skill-record study), then the evolution pass: off-hot-path toggle, grounded strengthen-only asymmetry, git-commit + closed-log + provenance frontmatter, kb-state-audit hard gate, client-model rewrite channel (reuse the kb-autoreview pattern), acceptance-rate measurement before default-on.
