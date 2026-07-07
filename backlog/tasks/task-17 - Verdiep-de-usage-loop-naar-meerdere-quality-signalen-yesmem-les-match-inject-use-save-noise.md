---
id: TASK-17
title: >-
  Verdiep de usage-loop naar meerdere quality-signalen (yesmem-les:
  match/inject/use/save/noise)
status: In Progress
assignee: []
created_date: '2026-07-03 21:48'
updated_date: '2026-07-07 09:26'
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
CODE-VOORBEELDEN + YESMEM-BRONREFERENTIES (2026-07-03)

CORRECTIE op het aantal signalen: de README noemt "match/inject/use/save/noise" (marketing), maar de echte mechaniek (docs/features/cognition.md, sectie "Cognitive Signals & Reflection" + "Learning Clustering") gebruikt DRIE persisted kolommen: inject_count, use_count, noise_count. "match/save/fail collapse into inject_count". De aggregatie zit in IncrementClusterScore() en is SIGNED:

  yesmem (docs/features/cognition.md, functie IncrementClusterScore):
    clusterScore = 1.0 + useRate - noiseRate*0.5
  signalen: _signal_learning_used vs _signal_noise (increment_use / increment_noise)

Dat is de kern-steel: een SIGNED score die ONDER 1.0 kan. Ons usage_factor is boost-only:

  HUIDIG (scripts/_rank.py, usage_factor):
    USAGE_BOOST_RECENT = 1.10   # <=30d
    USAGE_BOOST_WARM   = 1.05   # <=90d
    def usage_factor(last_used_iso, today=None) -> float:
        if not last_used_iso: return 1.0
        age = _age_days(last_used_iso, today or date.today())
        if age <= 30: return USAGE_BOOST_RECENT
        if age <= 90: return USAGE_BOOST_WARM
        return 1.0            # <-- vloer 1.0: kan NOOIT straffen

VOORGESTELD (spiegelt yesmem's signed aggregate; noise_count naast used):
  # _usage.py: usage-tabel krijgt een noise-kolom
  #   usage(stem PK, injected, used, noise, last_injected, last_used, last_noise)
  # en een mark_noise(stems) analoog aan mark_used.

  # _rank.py: signed factor i.p.v. boost-only
  def usage_factor(injected, used, noise) -> float:
      if not injected: return 1.0
      use_rate   = used  / injected
      noise_rate = noise / injected
      # begrensd (anti-runaway), kan onder 1.0 zakken (yesmem-patroon)
      return max(0.8, min(1.10, 1.0 + 0.10*use_rate - 0.10*noise_rate))

STAP 1 (goedkoopst, doe eerst): fix de vals-positief in kb-usage-scan.py.
Nu telt regel 82 een enkel GENOEMDE stem als "used":
    used = [stem for stem in pending if stem and stem in text]
  Probleem: kb-retrieve injecteert die [[stem]]-links met "raadpleeg bij twijfel",
  het model praat ze na -> we tellen onze eigen injectie. Scheid GENOEMD van
  LOAD-BEARING (alleen tellen als de stem in een tool_use-input voorkomt = echt
  geraadpleegd, niet enkel in prozaverwijzing):
    used = [s for s in pending if s in toolcall_text]      # load-bearing
    # optioneel zwak signaal: s in prose_text zonder toolcall = geen 'use'
  Meet met kb-eval memory-only voor/na.

Bronbestanden yesmem (Go, Apache-2.0, github.com/carsteneu/yesmem):
- docs/features/cognition.md — IncrementClusterScore, inject/use/noise_count, signed aggregate.
- internal/daemon/handler_learnings.go, internal/extraction/consolidate.go — waar de counters worden bijgewerkt.

--- OB1-CHECK (2026-07-04): GEEN steel-doel hier, wel validatie ---
Bron: OB1 (github.com/NateBJones-Projects/OB1), geverifieerd via 35-agent adversariele pass (~/Claude/research/2026-07-04-ob1-openbrain-vs-kennisbank.md). OB1 heeft recall_traces + recall_items (ranking_score, used-bool) + een /recall/{id}/usage endpoint + audit_events -> maar dat is TELEMETRIE/observability voor een dashboard; het voedt de ranking-score NIET terug (geverifieerd: rankMemory gebruikt provenance/policy/review/confidence, GEEN usage-signaal).

CONCLUSIE: OB1 zit op precies onze PRE-fix staat (usage = telemetrie, niet in de rank). Dus OB1 levert hier GEEN over te nemen mechaniek. Het valideert wel de premisse: zelfs een systeem met 4070 sterren laat usage als losse telemetrie liggen -> een echte usage->rank feedbackloop met signed noise (deze task) zou ons juist ONDERSCHEIDEN, niet imiteren. YesMem (IncrementClusterScore, signed) blijft de enige referentie met usage-in-de-score. Geen wijziging aan de aanpak; OB1 bevestigt dat de YesMem-route de juiste is.

2026-07-06: eerste stap doorgevoerd. `kb-usage-scan.py` telt nu alleen `tool_use`-inputs als gebruik; losse prose-verwijzingen worden niet meer als load-bearing gebruik gemarkeerd. Tests toegevoegd voor tool-call gebruik en prose-only false positives. De noise-signal-beslissing blijft open totdat er meetbewijs is dat boost-only tekortschiet.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @claude
created: 2026-07-06 21:03
---
2026-07-06: start van de task. False-positive gebruiksmeting is aangescherpt; noise-signaal nog niet toegevoegd.
---

author: codex
created: 2026-07-07 09:26
---
Drain-check 2026-07-07: false-positive fix voor kb-usage-scan.py is aanwezig en tests voor tool_use versus prose-only zijn groen, maar AC#1 vereist nog kb-eval memory-only voor/na en AC#2/#4 vereisen bewijs dat boost-only tekortschiet. Lokale omgeving mist C:\Users\rvdbr\KennisBank\.claude\kb-usage.db en eval-data; daarom geen zelfstandig sluitbare noise-signal beslissing.
---
<!-- COMMENTS:END -->
