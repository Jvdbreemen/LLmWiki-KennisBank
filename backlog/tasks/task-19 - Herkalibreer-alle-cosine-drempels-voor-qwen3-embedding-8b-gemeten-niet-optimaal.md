---
id: TASK-19
title: >-
  Herkalibreer alle cosine-drempels voor qwen3-embedding:8b (gemeten: niet
  optimaal)
status: Done
assignee:
  - '@claude'
created_date: '2026-07-03 21:56'
updated_date: '2026-07-06 20:45'
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
--- MEETRESULTAAT set-uitbreiding + per-paar diagnose (2026-07-04) ---
Set uitgebreid 24 -> 42 paren (14/14/14), 06-claude/kb-calibrate-set.json (UNCOMMITTED in vault, gebruiker commit zelf). kb-calibrate exit 2: BEIDE grenzen overlappen nu (duplicate-grens 0.712 met overlap; was schoon 0.786 op 24 paren; related-grens 0.333 overlap onveranderd).

PER-PAAR DIAGNOSE (embed alle 42, cosine gesorteerd) bewijst dat dit GEEN labeling-fout is maar een MODEL-eigenschap. Alle labels correct geverifieerd. Cruciale overlap:
  0.773 related    PROGMEM-ESP8266 <-> F()/PSTR()-RAM (twee ESP8266-feiten, veel gedeelde woorden)
  0.758 duplicate  sessiestart-hook herbouwt index (parafrase)
  0.705 duplicate  Marvin brein-als-planeet <-> chronische depressie (parafrase, andere woorden)
  0.651 duplicate  hybride retrieval <-> sqlite-vec+FTS5 via RRF (parafrase, concreet vs abstract)
Klasse-spreiding: duplicate 0.651-0.915, related 0.269-0.773, unrelated 0.143-0.396.

CONCLUSIE (hard onderbouwd): qwen3-embedding:8b volgt LEXICALE overlap, niet SEMANTISCHE equivalentie, op korte teksten. Een vocabulair-disjuncte parafrase (RRF 0.651) zakt ONDER een lexicaal-overlappend related-paar (PROGMEM 0.773). Geen cosine-drempel scheidt duplicate van related. Het kalibratie-harnas levert hier een NEGATIEF resultaat: voor dit model zijn geen schone drempels afleidbaar. Dat is de meting, niet een setgebrek.

HERIJK-BESLISSINGEN (data-onderbouwd, GEEN blinde tweak):
- dedup 0.92: KEEP. Lager zetten merget related-feiten (PROGMEM 0.773 zou bij dedup<=0.77 gemerged worden). 0.92 is de VEILIGE keuze: alleen bijna-identieke tekst, accepteert dat vocabulair-disjuncte parafrasen ontsnappen (TASK-14/16).
- cluster 0.80: LIGT BOVEN ELK related-paar (related max 0.773). cluster_promote kan dus vrijwel nooit vuren -> bevestigt TASK-15. Kies: verlaag naar ~0.75 om top-related te vangen, OF accepteer near-dead + documenteer.
- reconcile 0.75 / conflict 0.62 / retrieve 0.60: verdedigbaar tegen de related-spreiding (0.27-0.77). retrieve 0.60 vangt de bovenste helft related (gewenst voor recall); reconcile 0.75 vuurt alleen op near-duplicate (juist voor supersede). KEEP.
- FACET-ESCAPE (TASK-14/16) is NIET met een drempel op te lossen: een lagere dedup merget related-feiten. Echte fix = ander mechanisme: exacte body-hash pre-dedup (vangt identieke facetten) OF een parafrase-getraind model/cross-encoder ALLEEN voor de dedup-beslissing, niet voor retrieval.

MODEL-KEUZE-IMPLICATIE: voor threshold-gebaseerde parafrase-dedup is qwen3 ongeschikt; cosine != parafrase-detectie hier. Retrieval-rol mag qwen3 blijven (relevance-ranking werkt). Overweeg een paraphrase/STS-model (of cross-encoder rerank) uitsluitend voor de dedup/supersede-beslissing. Zie [[embedding-model-keuze]]. Model-specifiek: herhaal deze meting bij elke modelwissel.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Geklopt als meet- en documentatietaak: de kalibratieset is uitgebreid, de qwen3-embedding:8b-metingen zijn vastgelegd en de conclusie is dat er geen schone cosine-scheidingen zijn voor alle knoppen tegelijk. De bestaande thresholds blijven daarom bewust staan; CONFIGURATION.md, CHANGELOG.md en de task-notes dragen de herhaalbare procedure en de model-specifieke conclusie. Geen runtime-code aangepast.
<!-- SECTION:FINAL_SUMMARY:END -->
