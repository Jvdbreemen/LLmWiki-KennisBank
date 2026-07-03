---
id: TASK-17
title: >-
  Verdiep de usage-loop naar meerdere quality-signalen (yesmem-les:
  match/inject/use/save/noise)
status: To Do
assignee: []
created_date: '2026-07-03 21:48'
labels: []
dependencies: []
ordinal: 19000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
STEEL-IDEE uit de KennisBank-vs-YesMem vergelijking (2026-07-03, research: ~/Claude/research/2026-07-03-kennisbank-vs-yesmem.md). YesMem (github.com/carsteneu/yesmem, Apache-2.0, productie sinds mrt 2026) meet retrieval-kwaliteit met ZES onafhankelijke signalen: match / inject / use / save / noise. Onze net-gebouwde usage-feedbackloop (v0.9.0) meet er effectief TWEE.

HUIDIGE STAAT (geverifieerd):
- _usage.py: usage-tabel met injected + used counters (+ last_injected/last_used). kb-retrieve logt injected; kb-usage-scan.py (SessionEnd) markeert used als een geinjecteerde [[stem]] in assistant-tekst/tool-calls voorkomt.
- _rank.usage_factor: boost-only (USAGE_BOOST_RECENT 1.10 <=30d, WARM 1.05 <=90d, vloer 1.0 -> nooit <1.0). Een geciteerd-maar-fout document scoort dus identiek aan geciteerd-en-correct.

TWEE ZWAKTES DIE MEER SIGNALEN OPLOSSEN:
1. Geen NEGATIEF signaal: usage_factor kan alleen omhoog. YesMem's 'noise'-signaal markeert expliciet slecht-gebleken kennis zodat die kan zakken. Wij hebben dat niet.
2. 'used' is te grof / vals-positief-gevoelig: kb-usage-scan.py:82 telt 'stem in text' als used, terwijl kb-retrieve die links juist injecteert met 'raadpleeg bij twijfel' -> het model praat ze na -> we tellen deels onze eigen injectie als gebruik. YesMem scheidt 'inject' (aangeboden) van 'use' (echt load-bearing) van 'save' (expliciet bewaard) van 'noise' (expliciet slecht).

MOGELIJKE INGREPEN (gefaseerd, meet met kb-eval memory-only voor/na):
1. Fix de vals-positief eerst (goedkoopst, ~5-10 LOC): scheid in kb-usage-scan 'genoemd' van 'load-bearing' (bv. alleen tellen als de stem in een tool_use-input voorkomt = echt geraadpleegd, niet enkel in prozaverwijzing). Meet of memory recall@1 verbetert.
2. Voeg een 'noise'-signaal toe: een expliciet-slecht-signaal (mens of judge markeert een geinjecteerde memory als niet-nuttig) dat usage_factor ONDER 1.0 laat zakken. Kleinste governance-conforme vorm: een mens-gated markering, geen autonome down-weight.
3. Optioneel 'save'-signaal: memories die de mens actief promoveert/bewaart krijgen een boost boven puur-gebruikt.

BEGRENZING/PRINCIPES: houd het deterministisch waar mogelijk (de scan is deterministisch; een noise-judge is LLM en botst met 'deterministisch waar mogelijk' + mens=update-autoriteit -> liever mens-gated). Elke boost blijft klein en begrensd (anti-terugkoppel-runaway, zoals de bestaande 1.05/1.10). GEEN uitbreiding zonder dat kb-eval memory-only aantoont dat het huidige used-signaal tekortschiet — begin dus met optie 1 (de vals-positief-fix) en MEET.

Raakt: TASK-16 (usage-scan-tuning werd daar al genoemd als de echt-bijtende zwakte).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Vals-positief in kb-usage-scan gemeten en gefixt (scheid genoemd van load-bearing); kb-eval memory-only voor/na toont het effect
- [ ] #2 Beslissing over een negatief 'noise'-signaal: wel/niet, en zo ja mens-gated (geen autonome down-weight) — onderbouwd met een meting dat boost-only tekortschiet
- [ ] #3 Elke nieuwe factor blijft klein/begrensd (anti-runaway) en deterministisch waar mogelijk; geen LLM in de SessionEnd-hotpath zonder expliciete rechtvaardiging
- [ ] #4 Geen signaal-uitbreiding zonder kb-eval-bewijs dat het huidige used-signaal tekortschiet; gefaseerd, meet elke stap
<!-- AC:END -->
