---
id: TASK-162
title: Give trust and noise something to read
status: To Do
assignee: []
created_date: '2026-08-14 16:32'
updated_date: '2026-08-15 12:42'
labels:
  - retrieval
  - memory
  - ranking
  - design
dependencies: []
priority: medium
ordinal: 155700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Design: `docs/superpowers/specs/2026-08-14-trust-and-noise-design.md`. Written first, on request, before any code.

> **Settled by TASK-163 before this starts: grounded verification may raise trust and may never lower it.** `supported` was returned 49 times in 60 with zero fabricated quotes (0/60, upper bound 6.0%), while `unsupported` is right about half the time (4/8, Wilson 22–79%) — and its errors are structural, not tunable: from inside a passage, a retrieval miss and a false memory are indistinguishable, so no coverage short of exhaustive separates them. Evidence and reasoning in `docs/research/llm-trust-verification-2026-08-15.md`. Note also that the same work found a real extraction-invention rate of 2 in 60 (3.3%, 0.9–11.4%), which is what a verification pass would be catching.

Two of the five factors in `_rank.rerank` were measured to do literally nothing (TASK-160): `no trust` and `no noise` produce byte-identical results to production, zero flips at k=1 and k=5. The reasons differ and so do the fixes.

**Trust is broken.** All 1732 current memories carry `evidence_basis: agent`, so `trust_factor` returns 0.95 for every one of them and a uniform multiplier cannot reorder. It is not neutral, it is constant — which is worse, because it reads as a working signal in the code and in any future measurement that does not check the distribution. It will also begin reordering silently the first time a `getypt` or `import` memory appears.

**Noise is not broken, it is unused.** The human-gated input path exists (`kb-noise.py <stem>`), the penalty is bounded, and nobody has ever made a marking. What is missing is an occasion to make one.

Proposed, in the sequence the design argues for:

1. **Contradiction penalty** — feed `kb-state-audit`'s CONTRADICTED pile into the ranking. Smallest change, deterministic, no model, and the only proposal whose input set is already known correct (four memories on this vault, every one asserting a superseded embedding model at full injection strength).
2. **Corroboration as trust** — count how many *distinct sessions* independently asserted a memory, instead of who produced it. The signal is already computed and discarded: the dedup branch in `memory-sweep.py` fires exactly when a second independent observation arrives, increments a counter and drops it.
3. **A noise queue in /kennisbank:review** — memories injected N times and used zero times, oldest first, with "mark as noise" as the action. Connects an existing input to an existing mechanism; no new factor.

Grounded in the field rather than invented: an ablation over seven cognitively grounded factors puts learned weighting at 0.770 against recency-alone at 0.368 and finds reliability dominant (arXiv 2606.12945); open-domain extraction scores facts by frequency of the value across independent sources (ODKE+); Mem0 damps unused memories toward 0.3x where this repo's usage factor floors at 1.0.

**Two problems are stated in the design before anything is built.** At the current dedup threshold (0.92) corroboration would fire on 0.9% of candidates — a factor that is zero everywhere, which is the failure this work exists to fix. And corroboration correlates with age, so it may cancel the recency distortion or merely replace it. Both need TASK-161's labelled pairs.

Blocked on TASK-161 for everything except the contradiction penalty and the noise queue.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The contradiction penalty reads kb-state-audit's output, is bounded, and is exactly 1.0 when the audit finds nothing
- [ ] #2 Corroboration counts distinct sessions, not repeated chunks of one transcript, and is capped
- [ ] #3 The corroboration threshold is justified against labelled pairs rather than chosen
- [ ] #4 trust_factor's behaviour when the first non-agent memory appears is decided explicitly, not discovered
- [ ] #5 The noise queue proposes candidates and never marks autonomously
- [ ] #6 Every change is measured on TASK-161's set as well as the existing one, and both are reported
- [ ] #7 python -m pytest tests -q is green
<!-- AC:END -->
