---
id: TASK-14
title: 'Over-extractie temmen: extractie-cap of dedup-drempel voor mega-transcripts'
status: To Do
assignee: []
created_date: '2026-07-03 18:38'
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
