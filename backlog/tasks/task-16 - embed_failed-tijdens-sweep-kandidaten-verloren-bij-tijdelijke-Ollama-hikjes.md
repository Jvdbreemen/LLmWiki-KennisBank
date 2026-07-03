---
id: TASK-16
title: 'embed_failed tijdens sweep: kandidaten verloren bij tijdelijke Ollama-hikjes'
status: To Do
assignee: []
created_date: '2026-07-03 18:39'
updated_date: '2026-07-03 19:35'
labels: []
dependencies: []
ordinal: 18000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
WAARNEMING (2026-07-03, geheugen-backfill). De sweep-heartbeat rapporteerde embed_failed: 18. Dat zijn 18 kandidaat-memories die zijn OVERGESLAGEN omdat emb.embed(body) None teruggaf (tijdelijke Ollama-storing/timeout tijdens de lange --all run). Zie memory-sweep.py: als vec is None -> s['embed_failed'] += 1; continue (een memory zonder vector is niet te dedupliceren, dus terecht overgeslagen — de skip zelf is correct gedrag, GEEN bug).

HET PROBLEEM: deze 18 zijn PERMANENT verloren voor deze run. De .swept-watermark is append-only en wordt per transcript gezet zodra het transcript verwerkt is (ss.mark), OOK als sommige kandidaten binnen dat transcript op embed_failed strandden. Bij een normale (niet --all) vervolg-sweep worden die transcripts niet opnieuw bekeken -> de 18 komen nooit terug, tenzij je een volledige --all rebuild draait (die dan dubbele van alle andere memories zou opleveren — niet aan te raden).

IMPACT: laag en eenmalig. 18 op 503 geschreven (~3.5%), en het waren kandidaten uit de mega-sessies waar toch overvloed was. Geen stabiliteitsprobleem. Maar het is een STIL dataverlies-pad dat bij een grote of trage backfill (of een Ollama die onder druk staat) groter kan worden.

MOGELIJKE INGREPEN (afwegen op kosten/baat — mogelijk WONTFIX):
1. Retry-op-embed binnen de chunk-loop: bij vec is None, N keer opnieuw met korte backoff voordat je opgeeft (Ollama-hikjes zijn meestal transient). Kleinste, meest gerichte fix.
2. Transcript NIET als swept markeren als er >0 embed_failed in zaten, zodat een vervolg-sweep ze opnieuw probeert. RISICO: kan een transcript herhaaldelijk deels-herverwerken -> dubbele memories voor de kandidaten die WEL slaagden (dedup vangt veel maar niet alles). Vereist per-kandidaat i.p.v. per-transcript watermarking — grotere ingreep.
3. embed_failed loggen naar een dead-letter lijst (welke transcript+chunk) zodat je gericht kunt her-verwerken zonder volledige --all. Middenweg.
4. WONTFIX: accepteren dat een zeldzame transient embed-fail een enkele kandidaat kost; het model dat er echt toe doet komt vaak in meerdere sessies terug en wordt later alsnog gevangen.

AANBEVELING: begin met optie 1 (retry) als de goedkoopste risico-arme verbetering; optie 2/3 alleen als embed_failed structureel hoog blijkt bij normale sweeps (nu was het een --all backfill-fenomeen). Meet eerst of embed_failed bij reguliere per-sessie sweeps uberhaupt >0 is voordat je meer bouwt.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Gemeten of embed_failed bij NORMALE per-sessie sweeps >0 is, of dat het een --all/backfill-fenomeen was
- [ ] #2 Als ingegrepen (optie 1): embed-retry met backoff in de chunk-loop, met een test die de retry-op-None-tak dekt; fail-soft blijft (na max retries nog steeds skip, geen crash)
- [ ] #3 Geen per-kandidaat herverwerking die dubbele memories introduceert zonder dedup-garantie (optie 2 alleen met per-kandidaat watermarking)
- [ ] #4 Beslissing gedocumenteerd, inclusief WONTFIX-optie als de impact verwaarloosbaar blijkt
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
GEMETEN UITBREIDING (2026-07-03, cosine + body-hash audit van de 588 memories). embed_failed heeft een TWEEDE, ernstiger gevolg dan alleen verloren kandidaten: het laat EXACTE DUPLICATEN door dedup glippen.

BEWIJS: de vault bevat nu 25 exacte-body duplicaat-paren (588 memories, 563 unieke bodies, 4.3% exact dubbel). 18/25 spreiden over meerdere datums. Cosine-audit bevestigt: 26 paren >= 0.92 (dedup-drempel), ~23 op cosine 1.000 (identieke body). Patronen: cross-datum (2026-07-02-X.md + 2026-07-03-X.md, zelfde body) en zelfde-dag -2-suffix (X.md + X-2.md).

MECHANISME: de backfill liep over de middernachtgrens en werd meermaals gekilld/herstart. Elke memory-sweep --all negeert de watermark en her-extraheert ALLE transcripts. dedup (_dup_skip, 0.92) moet re-extracties vangen via de existing-pool (_dedup_items), die per file get_cached(recompute=True) aanroept. Onder Ollama-druk gaf dat None voor de ~83 vector-loze memories -> die vallen uit de dedup-pool ('if not v: continue') -> hun her-geextraheerde tweeling ontsnapt en wordt geschreven met nieuwe datum of -2-suffix.

STRUCTURELE FIX (hoger geprioriteerd dan de embed-retry alleen): voeg een DETERMINISTISCHE body-hash pre-dedup toe VOOR de cosine-stap. Exacte-duplicaat-detectie mag nooit van Ollama afhangen; de cosine-0.92-dedup is voor NEAR-duplicaten. Een body-hash check (md5 van de gestripte body) tegen zowel de bestaande 09-memory files als de binnen-run geschreven set had alle 25 gevangen, ongeacht embed-toestand, en maakt --all reprocessing idempotent voor exacte re-extracties. Dit is klein, deterministisch, fail-open (geen model nodig) en past bij het 'deterministisch waar mogelijk'-principe.

REVISIE PRIORITEIT: van 'laag/eenmalig' naar 'medium' — de dedup-escape is een doorlopend risico bij elke --all/rebuild-memory reprocessing, niet alleen een eenmalig backfill-verlies. De embed-retry (oorspronkelijke optie 1) blijft nuttig maar lost de dedup-escape NIET volledig op (een retry kan alsnog falen); de body-hash pre-dedup wel.

BESTAANDE CRUFT: 25 exacte duplicaten staan nu in de vault (deterministisch identificeerbaar via body-hash). Aparte opruim-actie mogelijk (behoud 1 per paar, superseded of verwijder de andere) -> 588 zou naar 563 zakken. Raakt retrieval: twee identieke hits verspillen top-k slots. Vault-content-mutatie, dus met mens-akkoord.
<!-- SECTION:NOTES:END -->
