---
id: TASK-19
title: >-
  Herkalibreer alle cosine-drempels voor qwen3-embedding:8b (gemeten: niet
  optimaal)
status: To Do
assignee: []
created_date: '2026-07-03 21:56'
labels: []
dependencies: []
ordinal: 21000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
GEMETEN PROBLEEM (2026-07-03, ship-and-settle): de cosine-drempels zijn NIET optimaal gekalibreerd voor het actieve embeddingmodel qwen3-embedding:8b (4096-dim). Ze zijn ooit getuned/geraden, maar de gemeten pairwise-verdeling over de echte vault bewijst dat meerdere drempels in dood of verkeerd gebied zitten. Deze sessie leverde het bewijs.

DE ZES/ZEVEN DREMPELS (huidige waarden):
- dedup 0.92        (scripts/_sweeputil.py is_duplicate)
- rewrite 0.83      (scripts/find-similar.py)
- supersede 0.85    (scripts/_maintenance.py supersede_pass)
- cluster 0.80      (scripts/_maintenance.py cluster_promote_pass, min_neighbors=2)
- reconcile 0.75    (scripts/_reconcile.py RECONCILE_THRESHOLD)
- conflict 0.62     (scripts/conflict-scan.py KB_CONFLICT_SIM)
- retrieve 0.60     (kennisbank-embed.json retrieve_threshold)

GEMETEN BEWIJS (numpy-analyse over 505 current-memories met vector, 127k paren):
1. Pairwise-cosine verdeling: mediaan 0.358, p95 0.493, p99 0.577, met een LEEG GAT tussen 0.85 en 0.92 (nul paren). Boven 0.92 alleen exacte duplicaten (cosine ~1.0).
2. cluster_promote (0.80, min_neighbors=2) markeerde 0 en KAN vrijwel nooit vuren: op 0.80 heeft 445/505 nul buren, 60 precies 1 buur, NIEMAND 2+ buren. Zie TASK-15 (herclassificeerd naar kalibratie-beslissing).
3. kb-calibrate nulmeting op qwen3 (24 paren): duplicate-grens SCHOON op 0.786 -> de dedup-drempel 0.92 zit VER boven de werkelijke duplicaat/related-grens (over-conservatief, vandaar dat near-duplicaat-facetten ontsnappen, zie TASK-14/16). related-grens toonde OVERLAP (exit 2) -> de set of het model scheidt related van unrelated niet schoon op de huidige drempels.
4. De config-noot in kennisbank-embed.json zegt zelf: "echte match 0.73-0.80, ruis <=0.51". 0.80 (cluster) zit dus aan het PLAFOND van het matchbereik; supersede 0.85 en dedup 0.92 liggen erboven, in dun gebied.

CONCLUSIE: de drempels zijn niet afgeleid uit de werkelijke verdeling van dit model op deze data. Dedup te hoog (mist facetten), cluster onbereikbaar, related-band niet schoon gescheiden. Het harnas kb-calibrate.py bestaat precies hiervoor maar is nog niet uitputtend ingezet.

AANPAK (meet-gedreven, geen enkele drempel wijzigen zonder bewijs):
1. Breid de kalibratieset uit: de huidige 24 paren (06-claude/kb-calibrate-set.json) gaven related-overlap. Voeg meer duplicate/related/unrelated-paren toe die REPRESENTATIEF zijn voor de echte vault (haal near-duplicaat-facetten uit 09-memory, echte gerelateerde memories, en onverwante). Doel: een schone related-grens (kb-calibrate exit 0).
2. Meet de werkelijke verdeling per klasse: draai kb-calibrate.py opnieuw; gebruik de per-grens voorstellen (duplicate-grens ~0.786, related-grens na set-uitbreiding) als DATA-afgeleide waarden i.p.v. de geraden getallen.
3. Herijk per drempel op basis van de meting, niet vooraf:
   - dedup: verlaag van 0.92 richting de gemeten duplicaat-grens (~0.79-0.86) zodat near-duplicaat-facetten wel gevangen worden -- MAAR meet met kb-eval memory-only dat je geen legitiem-verschillende feiten merget (zie TASK-14/16).
   - cluster 0.80 / min_neighbors: of verlaag min_neighbors naar 1 (promote op paren), of verlaag de drempel (RISICO: 0.80 is al matchplafond), of accepteer near-dead en documenteer (TASK-15).
   - reconcile/conflict/retrieve (related-band): herijk op de schone related-grens.
   - supersede 0.85: check tegen het gat 0.85-0.92; mogelijk verlagen naar de related-grens.
4. Verifieer met kb-eval BEIDE lagen (wiki-only + memory-only) voor/na ELKE drempelwijziging: recall mag niet dalen. Herbouw de index na een dedup/threshold-wijziging.
5. Documenteer de nieuwe waarden + de meting waaruit ze volgen in CONFIGURATION.md (secties 3b/4) en de config-noot; verwijs naar de verdeling zodat een volgende modelwissel weet welke meting te herhalen.

BELANGRIJK: dit is model-specifiek. Bij een echte modelwissel (bv. naar nomic-embed-text) MOET dit opnieuw -- de hele reden dat kb-calibrate bestaat. Leg de procedure vast zodat het herhaalbaar is, niet eenmalig.

Raakt: kb-calibrate.py (het harnas), TASK-14 (dedup te hoog -> facet-escape), TASK-15 (cluster onbereikbaar), TASK-16 (dedup-escape), alle scripts met een drempel hierboven.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Kalibratieset uitgebreid met representatieve vault-paren tot kb-calibrate.py een SCHONE related-grens geeft (exit 0, geen overlap)
- [ ] #2 Elke drempel (dedup/rewrite/supersede/cluster/reconcile/conflict/retrieve) herijkt op de GEMETEN grens uit kb-calibrate + de pairwise-verdeling, niet op geraden waarden
- [ ] #3 kb-eval BEIDE lagen (wiki-only + memory-only) voor/na elke wijziging: geen recall-daling; index herbouwd na dedup/threshold-wijziging
- [ ] #4 dedup-verlaging merget geen legitiem-verschillende feiten (steekproef-verificatie); cluster-drempel/min_neighbors-beslissing gedocumenteerd
- [ ] #5 Nieuwe waarden + de meting waaruit ze volgen vastgelegd in CONFIGURATION.md; de herkalibratie-procedure is herhaalbaar gedocumenteerd voor een volgende modelwissel
<!-- AC:END -->
