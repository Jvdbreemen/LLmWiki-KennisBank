---
id: TASK-126
title: 'Embedmodel-sweep: kwaliteit vs hot-path-latency op eigen eval-sets'
status: In Progress
assignee: []
created_date: '2026-08-02 00:15'
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
- [ ] #1 Sweep-harnas draait reproduceerbaar over meerdere ollama-embedmodellen zonder de live vault aan te raken
- [ ] #2 Per model gemeten: warme p50/p95/cold embed-latency, recall@1/3/5 en MRR op zowel de wiki- als de memory-eval-set
- [ ] #3 Instructieprefixen (query- en documentzijde) zijn configureerbaar, zodat e5-achtige modellen niet oneerlijk gemeten worden
- [ ] #4 Drempels zijn per model gekalibreerd of buiten beschouwing gelaten, niet blind op de qwen3-waarde 0.60 gelaten
- [ ] #5 Eindadvies benoemt het Pareto-punt met cijfers, of stelt expliciet vast dat geen kandidaat binnen 0.6s de baseline-kwaliteit haalt
<!-- AC:END -->
