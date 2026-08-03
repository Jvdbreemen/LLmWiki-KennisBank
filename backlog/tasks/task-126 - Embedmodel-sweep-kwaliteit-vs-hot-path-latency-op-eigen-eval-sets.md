---
id: TASK-126
title: 'Embedmodel-sweep: kwaliteit vs hot-path-latency op eigen eval-sets'
status: Done
assignee: []
created_date: '2026-08-02 00:15'
updated_date: '2026-08-03 08:20'
labels:
  - retrieval
  - embeddings
  - performance
dependencies: []
priority: high
ordinal: 93500
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Zoek het optimum tussen recall en embed-latency voor de KennisBank-retrieval. Baseline is qwen3-embedding:8b. Budget: <0.6s per query-embed op het hot path.

Aanleiding: het onderzoeksrapport "Lichte NL/EN embedding-modellen als alternatief voor Qwen3-Embedding-8B" (1 aug 2026) geeft de relatieve ordening op MTEB-NL/BEIR-NL, maar geen enkele publieke benchmark meet deze vault. Eigen meting is de enige scheidsrechter bij marges van 2-4 punten.

Eerste meting (baseline, 2 aug 2026): qwen3-embedding:8b warm p50=529ms, maar p95=47s en cold=32s. Oorzaak is VRAM-contentie: het model claimt 8.4GB op een 16GB GPU waar LM Studio al ~7GB houdt, dus het wordt tussentijds geevicteerd. Het latency-probleem is dus niet puur parametertelling.

Aanpak: scratch-vault (kopie van 02-wiki + 09-memory + eval-sets), per model index herbouwen en kb-eval draaien met drempel 0.0 (rang-only), plus een losse latency-probe.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Sweep-harnas draait reproduceerbaar over meerdere ollama-embedmodellen zonder de live vault aan te raken
- [x] #2 Per model gemeten: warme p50/p95/cold embed-latency, recall@1/3/5 en MRR op zowel de wiki- als de memory-eval-set
- [x] #3 Instructieprefixen (query- en documentzijde) zijn configureerbaar, zodat e5-achtige modellen niet oneerlijk gemeten worden
- [x] #4 Drempels zijn per model gekalibreerd of buiten beschouwing gelaten, niet blind op de qwen3-waarde 0.60 gelaten
- [x] #5 Eindadvies benoemt het Pareto-punt met cijfers, of stelt expliciet vast dat geen kandidaat binnen 0.6s de baseline-kwaliteit haalt
<!-- AC:END -->

## Final Summary

Nine models measured, default switched to qwen3-embedding:4b, and a similarity floor fixed that
turned out to be wrong on the old model as well. PR #96.

Result (vector-only, which isolates the embedding from lexical rescue): the 4b reaches wiki MRR
0.967 and memory MRR 0.540 at 322 ms warm p50 and 6.2 GB resident, against the 8b's 0.961 / 0.530
at 347 ms and 8.4 GB. Every candidate except snowflake-arctic-embed2 fits the 600 ms budget.
embeddinggemma:300m is the interesting runner-up: best wiki MRR of the field (0.997) at 300 ms in
621 MB, but 0.035 behind on memory.

The 47 s p95 in the original baseline was VRAM contention, not the model. The retrieval hook holds
its model for 30 minutes, so anything loaded beside it fights for the rest of a 16 GB card. Under
evict-load-warmup-measure nothing exceeded 1017 ms p95.

Thresholds were measured rather than inherited, and that produced the more consequential finding.
MEMORY_MIN_COS = 0.60 discarded 366 of 806 retrievable memory hits on the 4b, and re-measuring
against an 8b index showed it had already been discarding 260 of 798 (33%) on the model it was
chosen for. New defaults: retrieve_threshold 0.50, MEMORY_MIN_COS 0.45.

Two process notes for whoever picks this up:

- This session duplicated a harness that already existed on this branch from the interrupted run.
  The branch was never checked; `git branch -a` would have found it in seconds. Both are now
  consolidated here, with this branch's version as the base: it makes instruction prefixes a real
  production feature with tests, and folds the doc prefix into embed_id() so the cache cannot be
  reused across a prefix change. Added from the second session: evict-everything before a probe,
  and per-row VRAM recording.
- kb-calibrate.py proposes 0.311 for this model and reports OVERLAP. Do not use that number for
  retrieve_threshold: it measures text-against-text pair similarity, while the floor gates
  query-against-document similarity. Different distributions.

Left open deliberately: precision. Lowering a floor admits weaker matches and there is no labelled
set to quantify that; retrieve_top_n caps the effect at three documents. The semantic-tiling
thresholds (0.85 / 0.62) remain 8b-calibrated and run off the hot path. TASK-128 carries the
lexical-fusion finding.
