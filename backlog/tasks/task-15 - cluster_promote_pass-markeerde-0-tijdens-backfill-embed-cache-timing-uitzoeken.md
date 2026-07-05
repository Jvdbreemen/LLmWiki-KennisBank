---
id: TASK-15
title: >-
  cluster_promote_pass markeerde 0 tijdens backfill: embed-cache timing
  uitzoeken
status: To Do
assignee: []
created_date: '2026-07-03 18:39'
updated_date: '2026-07-04 04:20'
labels: []
dependencies: []
ordinal: 17000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
WAARNEMING (2026-07-03, geheugen-backfill). De sweep-heartbeat na rebuild-memory --all rapporteerde promote_marked: 0, terwijl er 588 memories met veel facet-overlap in 09-memory staan. Bij zoveel verwante current-memories zou cluster_promote_pass (die memories met >=2 verwante buren op cosine >0.80 markeert als promote_candidate: true voor /wiki) er verwacht meerdere moeten vinden. Nul is verdacht.

WAARSCHIJNLIJKE OORZAAK (te verifieren):
_maintenance.cluster_promote_pass (scripts/_maintenance.py:188, threshold=0.80, min_neighbors=2) leunt op current_items(), dat per memory de embedding via emb.get_cached ophaalt en items ZONDER gecachte vector overslaat ('if not vec: continue', _maintenance.py rond regel 49). Tijdens de backfill worden memories net geschreven; hun embeddings zitten mogelijk nog niet in de embed-cache (kb-index.db wordt pas ge(her)bouwd door build-kb-index.py in een aparte SessionStart-hook/handmatige run, niet door de sweep zelf). De onderhoudspas draait aan het EIND van run_sweep, direct na het schrijven — als de cache dan koud is, ziet current_items bijna geen vectoren -> geen buren -> promote_marked 0.

Ter contrast: reconciled_superseded=5 en superseded=6 vuurden WEL, dus het LLM-pad leeft; het is specifiek de vector-afhankelijke cluster-stap die leeg bleef.

TE ONDERZOEKEN:
1. Reproduceer: draai cluster_promote_pass los OP DE HUIDIGE 588 memories (embed-cache is nu warm na de post-backfill build-kb-index run) en kijk of het nu WEL kandidaten vindt. Zo ja: bevestigt de koude-cache-hypothese.
2. Als bevestigd: moet de onderhoudspas (of alleen de cluster-stap) de embeddings zelf verzekeren (recompute-on-miss) i.p.v. op een mogelijk-koude cache leunen? get_cached heeft een recompute-parameter (current_items geeft die door) — check of cluster_promote_pass die pad gebruikt of dat de cache-miss stil wordt overgeslagen.
3. Overweeg of cluster-promotie uberhaupt zinvol is DIRECT na een mega-backfill (honderden nieuwe memories) of beter als aparte, latere pas op een warme index draait.

RISICO/NUANCE: dit is diagnose, geen bevestigde bug. Mogelijk is 0 correct (de facetten liggen net onder 0.80 cosine, of current_items werkte prima maar de clusters haalden min_neighbors=2 niet). Eerst reproduceren en meten voordat je code wijzigt. Fail-soft: de pas is al fail-soft per _maintenance-aanroep in run_sweep, dus een lege pas breekt niets — dit is kwaliteit, geen stabiliteit.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Gereproduceerd: cluster_promote_pass los gedraaid op de huidige 588 memories (warme cache) — vindt het nu wel/niet kandidaten? Uitkomst vastgelegd
- [ ] #2 Root-cause bevestigd of weerlegd: koude embed-cache tijdens de sweep-onderhoudspas vs een legitieme 0 (clusters onder drempel/min_neighbors)
- [ ] #3 Als het een cache-timing-bug is: fix zodat de cluster-stap op betrouwbare vectoren draait (recompute-on-miss of pas op warme index), met een test die de cache-miss-tak dekt
- [ ] #4 Geen wijziging als 0 correct blijkt; dan documenteren waarom (drempel/min_neighbors-gedrag) zodat het niet opnieuw als bug wordt opgepakt
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
GEMETEN CONCLUSIE (2026-07-03, read-only diagnostic op de 505 current-memories mét vector). De koude-cache-hypothese is GEFALSIFIEERD; promote_marked=0 is CORRECT gedrag, geen bug.

Bewijs:
1. Cache is WARM, niet koud: 505/544 current-memories hebben een geldige vector in embeddings-cache.json (576 entries). De vermoede store-mismatch (kb-index.db vs JSON-cache) is niet de oorzaak.
2. current_items recompute't sowieso live op cache-miss: get_cached default recompute=True (_embeddings.py:200); current_items' lambda (_maintenance.py:37) geeft recompute niet door maar de default is True -> op miss embedt hij live via Ollama.
3. Zelfde-run bewijs: supersede_pass (ook via current_items) vond WEL 6 paren -> current_items leverde een gevulde lijst met vectoren.

Buren-distributie (numpy, cosine-matrix over 505 items, self-diagonal 0):
- 0.80: 445 items 0 buren, 60 items 1 buur, 0 items 2+ buren.
- 0.85 en 0.90: idem, geen enkel item met 2+ buren.
- max cosine tussen twee memories: 1.000 (er is 1 exact-duplicaat-paar), maar geen enkele CLUSTER (item met >=2 buren).

ECHTE OORZAAK: (a) qwen3-embedding:8b (4096-dim) spreidt verwante-maar-verschillende tekst ver uiteen; 0.80 zit aan het PLAFOND van het matchbereik (config-noot: 'echte match 0.73-0.80'). min_neighbors=2 op 0.80 is praktisch onbereikbaar. (b) de over-extractie levert diverse atomaire facetten, geen duplicaten -> topisch verwant maar semantisch te ver uiteen voor clusters.

GEVOLG - dit is een KALIBRATIE-vraag, geen bug: cluster_promote_pass vuurt bij dit model/deze drempel vrijwel nooit (near-dead code). Opties (afwegen, niet nu): (1) min_neighbors verlagen naar 1 -> promote op paren i.p.v. clusters; (2) drempel verlagen -> RISICO, 0.80 is al het matchplafond, lager = ruis; (3) accepteren dat de puur-cosine cluster-stap geen bereik heeft en op de LLM-judge-paden (supersede) leunen. Ties aan kb-calibrate (drempels per embeddingmodel). Herclassificeer deze task van 'diagnose bug' naar 'kalibratie-beslissing cluster_promote'.

--- BEVESTIGD via kb-calibrate per-paar diagnose (2026-07-04, zie TASK-19) ---
cluster-drempel 0.80 ligt BOVEN elk gemeten related-paar (related max cosine = 0.773 op qwen3-embedding:8b, 42-paren kalibratieset). cluster_promote_pass(threshold=0.80, min_neighbors=2) kan daardoor vrijwel nooit vuren: geen enkel legitiem-gerelateerd paar haalt 0.80. Dit is GEEN cache-timing-bug (die hypothese was al gefalsifieerd) maar een drempel-boven-bereik. Beslissing: (a) verlaag threshold naar ~0.75 om top-related clusters te vangen, OF (b) verlaag min_neighbors naar 1, OF (c) accepteer near-dead en documenteer als bewuste keuze. Meet met kb-eval memory-only voor je (a)/(b) houdt.
<!-- SECTION:NOTES:END -->
