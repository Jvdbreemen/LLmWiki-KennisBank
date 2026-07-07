---
id: TASK-14
title: 'Over-extractie temmen: extractie-cap of dedup-drempel voor mega-transcripts'
status: In Progress
assignee: []
created_date: '2026-07-03 18:38'
updated_date: '2026-07-07 09:26'
labels: []
dependencies: []
ordinal: 16000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
GEMETEN PROBLEEM (ship-and-settle, 2026-07-03). Na de eenmalige geheugen-backfill over 31 transcripts (rebuild-memory --all) telt 09-memory 588 memories. De nieuwe per-laag kb-eval baseline (qwen3-embedding:8b):
- memory (memory-only): recall@1 0.529, recall@3 0.882, recall@5 0.882, MRR 0.686.
- wiki (wiki-only, referentie): recall@1 0.914 — gezond.

De lage rang-1 (0.529) komt door OVER-EXTRACTIE op de mega-sessies: twee transcripts leverden 148 en 130 memories (source_session-telling). Een sessie hoort te destilleren naar ~5-20 duurzame feiten. Gevolg: veel bijna-duplicaat FACETTEN van hetzelfde onderwerp (bv. tientallen 'SessionEnd-hook'- en 'truth-maintenance'-memories) concurreren om rang 1. Twee kb-eval-missers bevestigen dit exact: 'Waarvoor dient de SessionEnd-hook' en 'truth-maintenance optie B' worden door hun facet-broers verdrongen.

BELANGRIJKE NUANCE — mogelijk YAGNI. Dit is grotendeels een BACKFILL-artefact, geen doorlopend probleem:
- De backfill-runner draaide bewust met max_chunks=999 (volle dekking, geen cap) om lange transcripts volledig te dekken.
- De NORMALE per-sessie sweep (memory-sweep.py:153 run_sweep) heeft max_chunks=6 als default, dus reguliere sessies over-extraheren niet zo.
- _extract.extract_candidates heeft al max_n=8 kandidaten per chunk (_extract.py:37).
- Dedup draait op cosine 0.92 (_sweeputil.is_duplicate) — vangt bijna-identiek, NIET bijna-duplicaat-facetten.
- Retrieval-injectie toont top-3, en memory recall@3 = 0.882 is gezond. Als top-3 in de praktijk volstaat is er GEEN probleem.

TRIGGER om dit op te pakken: pas als een week echt gebruik (usage-telemetrie aan) laat zien dat de facet-ruis de injectie-kwaliteit schaadt (bv. usage-scan toont dat geinjecteerde memories zelden 'used' zijn, of je merkt irrelevante memory-hits in de context). Meet met kb-eval memory-only voor/na elke ingreep.

MOGELIJKE INGREPEN (kies op basis van de meting, niet vooraf):
1. Extractie-cap per transcript in run_sweep (bv. max N memories per source_session), zodat een mega-transcript niet 148 facetten dumpt.
2. Facet-merge pass: post-extractie de bijna-duplicaten binnen een transcript samenvoegen (hogere-recall dedup op bv. 0.85 binnen dezelfde source_session).
3. Dedup-drempel verlagen (0.92 -> lager) — RISICO: kan legitiem-verschillende feiten mergen; herijk met kb-calibrate.
4. Opruimen van de bestaande 588: een eenmalige cluster-merge over 09-memory (raakt aan cluster_promote_pass).

Meet elke optie met kb-eval memory-only (recall@1 moet omhoog zonder recall@3 te schaden) EN met kb-calibrate na een drempelwijziging. Geen enkele optie zonder meting.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Beslissing gebaseerd op een week usage-data + kb-eval memory-only, niet op onderbuik: is de facet-ruis een echt injectie-probleem?
- [ ] #2 Als ingegrepen: memory recall@1 stijgt meetbaar (kb-eval memory-only) zonder recall@3 te verlagen
- [ ] #3 Een drempelwijziging wordt geherijkt met kb-calibrate.py; de reguliere per-sessie sweep (max_chunks=6) blijft ongewijzigd tenzij bewezen nodig
- [ ] #4 Geen legitiem-verschillende feiten worden gemerged (steekproef-verificatie na een facet-merge of dedup-verlaging)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
CORRECTIE OORZAAK (2026-07-03, na code-verificatie memory-sweep.py:230, regel 'chunk_iter = chunks if ignore_watermark else chunks[:max_chunks]').

De eerdere framing ('mijn backfill-runner draaide met max_chunks=999') was misleidend. De 999 was een RODE HARING: in --all-modus (ignore_watermark=True) wordt max_chunks VOLLEDIG GENEGEERD — alle chunks worden verwerkt, ongeacht de cap. Mijn runner-waarde deed er dus niet toe.

De echte oorzaak is VERSCHEEPT gedrag: het officiele /kennisbank:rebuild-memory command draait memory-sweep.py --all, en die uncapped-chunk-tak geldt voor ELKE gebruiker die een backfill draait op grote transcripts, niet alleen voor mijn runner. Concreet:
- Per-sessie sweep (run_sweep zonder --all): chunk_iter = chunks[:max_chunks], max_chunks=6 -> GECAPT, over-extraheert niet.
- rebuild-memory / --all (ignore_watermark=True): chunk_iter = chunks -> ONGECAPT + geen per-transcript memory-cap -> een mega-transcript dumpt 148 facetten.

GEVOLG voor de ingrepen: optie 1 (extractie-cap per transcript) moet specifiek de --all/rebuild-pad raken, niet de reguliere sweep (die is al gecapt). Een per-source_session memory-cap in run_sweep werkt voor beide paden en is topologie-onafhankelijk. Overweeg ook: rebuild-memory zou vooraf kunnen waarschuwen bij extreem grote transcripts, of --all een expliciete --max-per-transcript N kunnen geven.

MEET-VERFIJNING VAN DE LEVER (2026-07-03, uit de TASK-15 buren-analyse). De over-extractie is GEEN duplicatie: op de 505 current-memories heeft 445 nul buren boven cosine 0.80 en niemand >=2 buren. De 148 facetten uit één mega-sessie zijn dus semantisch DIVERS (atomaire, zelfstandige uitspraken), niet near-duplicaat.

GEVOLG voor de ingreep-opties: optie 3 (dedup-drempel verlagen) en een facet-merge-pass RAKEN DEZE FACETTEN NAUWELIJKS — ze liggen te ver uit elkaar in de embedding-ruimte om gemerged te worden zonder legitiem-verschillende feiten samen te klappen. De effectieve lever is dus optie 1 (EXTRACTIE-CAP per source_session in run_sweep, raakt zowel --all als de reguliere sweep) of importance-gebaseerd snoeien (alleen judge-importance >= drempel bewaren), NIET similarity-merging. Prioriteer optie 1.

2026-07-06: toegevoegd `max_memories_per_transcript` (default 20) aan `scripts/memory-sweep.py`; de cap stopt de kandidaat-loop na N geschreven memories per source_session, ook in `--all`/rebuild-pad. CLI uitgebreid met `--max-per-transcript N`. Regresstest toegevoegd die een backfill met meerdere kandidaten op 2 geschreven memories begrenst. Gerichte `tests.test_memory_sweep` draait groen; volledige suite time-outte na 124s.

2026-07-07: documented `--max-per-transcript` in CONFIGURATION.md and CHANGELOG.md. Local environment still lacks an installed `~/KennisBank` vault / `kb-usage.db` / memory eval-set files, so the acceptance-criteria piece that depends on real week usage-data + memory-only kb-eval cannot be re-run on this machine.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: codex
created: 2026-07-06 21:49
---
Cap per transcript geïmplementeerd in `memory-sweep.py` en gedekt met een regressietest op de `--all`-route. Ik heb nog geen week-usage / kb-eval-meting herhaald in deze turn, dus ik laat de task status voorlopig op In Progress.
---

author: codex
created: 2026-07-07 08:07
---
Cap en docs zijn bijgewerkt, maar de gevraagde live usage-baseline ontbreekt lokaal: geen geïnstalleerde vault, geen kb-usage.db en geen memory-eval-set in de omgeving. Daardoor kan ik de task hier niet eerlijk als volledig bewezen sluiten.
---

author: codex
created: 2026-07-07 09:26
---
Drain-check 2026-07-07: code/doc-pad voor max_memories_per_transcript is aanwezig en gericht getest, maar AC#1/#2/#4 blijven meet-afhankelijk. Lokale omgeving mist C:\Users\rvdbr\KennisBank\09-memory, 01-raw\transcripts, .claude\kb-usage.db en memory-eval-set data; daarom kan ik hier geen week-usage + kb-eval memory-only bewijs leveren en de taak niet eerlijk sluiten.
---
<!-- COMMENTS:END -->
