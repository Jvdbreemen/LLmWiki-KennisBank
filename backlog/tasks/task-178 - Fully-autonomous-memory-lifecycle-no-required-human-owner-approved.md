---
id: TASK-178
title: Fully autonomous memory lifecycle — no required human (owner-approved)
status: To Do
assignee: []
created_date: '2026-08-15 22:40'
updated_date: '2026-08-15 22:40'
labels: []
dependencies: ['TASK-179']
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner decision, 2026-08-15: "For memory I want no human in the loop. It should
really be fully autonomous based on the LLM judge and sweep loop." This task
makes the memory lifecycle complete without a human anywhere on the required
path. The human remains an OPTIONAL override (git, memory-doctor, review
commands stay available) — but nothing waits for them.

What is already autonomous and stays unchanged: capture (extract → dedup →
reconcile → judge), supersession with valid_until, the expire pass, the
closed-log, kb-state-audit.

What currently requires a human, and what replaces it:

1. **The unverified quarantine has no autonomous exit.** Today a fragment the
   judge did not promote waits for `/kennisbank:review` (TASK-89) — and
   principle #3 says what requires manual discipline does not happen, which
   the recall-after-growth numbers confirm: 649 of 2389 files sat outside
   `current` at the last count. Replacement: an autonomous second-pass
   promoter in the sweep loop, using the two signals that are already
   validated or designed —
   - the grounded verifier (llm-trust-verification, usable per TASK-163):
     `supported` against its own source transcript promotes to `current`.
     The measured asymmetry is the safety argument: supported had 0/60
     fabricated quotes; promotion on it is evidence-based.
   - corroboration (TASK-162 design): a second independent session asserting
     the same content promotes, using the dedup counter the sweep already
     computes and discards.
   A fragment neither verified nor corroborated after N sweeps expires from
   quarantine (deterministic, logged) instead of waiting forever.

2. **Demotion stays deterministic — never a lone LLM verdict.** `unsupported`
   is right about half the time (4/8, Wilson 22–79%), so no autonomous
   demotion on the verifier alone. The autonomous demotion paths are the ones
   that already exist: supersession, expiry, and kb-state-audit contradiction
   (deterministic, authority-based). This keeps constraint #1 (no wrong
   recall) intact without a human gate.

3. **Noise marking is currently human-gated by design** (_usage.py: "MENS-
   GATED... geen judge, geen autonome down-weight" — the TASK-17 yesmem
   lesson). The owner decision overrides the gate, not the lesson: the
   penalty stays bounded and deterministic (_rank.noise_factor unchanged),
   but the INPUT becomes a signal instead of a hand-marking — injected N
   times with zero detected use over M sessions. Depends on TASK-179: with
   the current detection blind spot, "never used" partly measures "snippet
   was sufficient", and autonomous noise-marking on a broken detector would
   down-weight the best memories first. Do not enable before TASK-179 lands.

4. **TASK-89 (human review surface) is re-scoped by this decision**: it
   becomes an audit/override surface, not a required stage. Its queue should
   empty from the autonomous promoter, not from human labor.

Record in CHANGELOG when shipped: this deliberately diverges from the
"system proposes, human merges" line for the MEMORY layer only. The wiki
(curated, human-read) keeps its editor: dreaming writes drafts there
(TASK-174), it does not merge them.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A memory can go capture → quarantine → current with zero human actions, via grounded verification or corroboration, in the sweep loop
- [ ] #2 No autonomous demotion on a lone LLM verdict: demotion paths remain supersession, expiry, and state-audit contradiction only
- [ ] #3 Quarantine is bounded: unpromoted fragments expire deterministically after N sweeps, logged in the closed-log pattern
- [ ] #4 Autonomous noise input is gated on TASK-179 shipping first, and the penalty stays bounded exactly as _rank.noise_factor defines it
- [ ] #5 Every autonomous transition is logged with its evidence (verifier verdict, corroborating session, or deterministic rule) — auditable after the fact, reversible via memory-doctor
- [ ] #6 Measured before default-on: on a real vault, the promoter's decisions on a hand-checked sample, with the acceptance rate recorded; below a stated threshold the promoter demotes itself to proposal mode and that is the finding
- [ ] #7 TASK-89's surface re-scoped to audit/override; nothing in the lifecycle waits on it
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->
