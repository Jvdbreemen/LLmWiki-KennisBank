---
id: TASK-15
title: >-
  cluster_promote_pass markeerde 0 tijdens backfill: embed-cache timing
  uitzoeken
status: To Do
assignee: []
created_date: '2026-07-03 18:39'
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
