---
id: TASK-86
title: 'Evidence-first eval harness: production parity, latency, and 100+ example sets (Spoor A)'
status: In Progress
assignee: []
created_date: '2026-07-28 08:00'
labels:
  - eval
  - retrieval
  - llm-wiki-adoption
dependencies: []
ordinal: 96000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Gatekeeper for every llm_wiki-ecosystem feature adoption. Standing rule from the owner: **nothing gets adopted from any project without evidence — build the feature as an experiment, try it, and measure it on eval sets of at least 100 examples per layer. No measurement = no merge.**

Three defects make the current harness unable to carry that rule:
1. `kb-eval.py` `_live_hits_fn` calls `recall_hits()` without `expand=` and `min_cos=`, while production (`kb-retrieve.py`) passes both — the eval measures a different pipeline than the hook runs.
2. The eval sets are far too small (3 wiki / 17 memory questions); the measured "ceiling" (wiki recall@5 = 1.000, TASK-70) mostly proves the ruler is too short.
3. Nothing verifies the injection path end-to-end. Lesson from claude-mem v13.12.4: a whole memory category silently fell out of context injection for months. The harness must check what actually lands in the injected text, not only what the ranking returns.

Work: extract `retrieve_params(cfg)` + `load_embed_cfg()` from kb-retrieve (behaviour-neutral refactor); make `_live_hits_fn` production-faithful; add `--expand/--no-expand` for offline A/B; add `--latency` (p50/p95 per layer); add an injection-path test; build `scripts/kb-eval-gen.py` that generates candidate questions (deterministic layer + optional local-LLM paraphrases) into `*.draft.json` for human curation, typed `single-hop|keyword|paraphrase|temporal|multi-hop`; record the first honest baseline. Numbers will shift vs TASK-70 — first honest measurement, not a regression.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `_live_hits_fn` passes the same `expand` and `min_cos` as production resolves from config/env (parity test with stubbed `recall_hits`)
- [ ] #2 `kb-eval --latency` reports p50/p95 wall time per layer (text + `--json`)
- [ ] #3 An injection-path test parses full `kb-retrieve` hook output and verifies expected stems appear in the injected text
- [ ] #4 `kb-eval-gen.py` writes only `*.draft.json`, never touches live sets; output loads via `kb_eval.load_set`; non-LLM layer deterministic
- [ ] #5 Curated eval sets reach >=100 questions per layer (wiki and memory) with type labels — blocks every adoption gate downstream
- [ ] #6 Baseline (recall@1/3/5, MRR, per-type, latency) recorded here and in CHANGELOG
- [ ] #7 Existing suites stay green
- [ ] #8 EVIDENCE OF IMPROVEMENT: before/after report proving the harness now measures production (parity diff on identical sets: old call path vs new on the real vault) + honest baseline numbers recorded here; eval-gen drafts generated on the real vault as input for curation
<!-- AC:END -->
