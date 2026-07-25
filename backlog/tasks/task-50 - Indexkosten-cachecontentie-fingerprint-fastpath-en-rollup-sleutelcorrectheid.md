---
id: TASK-50
title: 'Indexkosten: cachecontentie, fingerprint-fastpath en rollup-sleutelcorrectheid'
status: To Do
assignee: []
created_date: '2026-07-25 03:34'
labels:
  - bug
  - performance
  - temporal
  - indexing
dependencies: []
priority: high
ordinal: 64000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Drie kosten- en correctheidsproblemen in de indexbouwers, die alledrie op de SessionStart-fase drukken.

**1. Gedeeld tijdelijk bestand bij het wegschrijven van de embedding-cache.** `scripts/_embeddings.py` schrijft naar één vast tmp-pad naast de cache en hernoemt dat over het origineel. SessionStart start meerdere bouwers die alledrie kunnen schrijven, dus twee processen delen hetzelfde tmp-bestand en de laatste schrijver wint — een klassieke lost update. Let op bij de fix: NIET oplossen door de caches te mergen. Een merge kan geen verwijdering uitdrukken en maakt de prune-stap in `build-embed-index.py` daarmee permanent een no-op. De juiste oplossing is een procesuniek tmp-pad plus een dirty-gate bij de aanroepers, zodat er alleen geschreven wordt als er echt iets veranderd is.

**2. Hash vóór de goedkope vergelijking.** `scripts/_activity.py` berekent een sha256 over elk bronbestand vóórdat het de watermerkvergelijking doet. Op de vault van de auteur: 2220 bestanden, 376 MB, gemeten 1,67 s warm en 51,75 s koud — voor een build die meestal niets te doen heeft. Een fastpath op (mtime, grootte) met de hash als fallback brengt dat naar ~0,04 s. Bepaal expliciet waar de hash tegen beschermt dat mtime niet dekt, en of dat geval hier relevant is; ververs het watermerk in beide takken, anders blijft de trage tak elke build terugkomen.

**3. De rollup-cachesleutel mist velden en geeft een fout antwoord.** De sleutel bevat het onderwerp maar niet de event-limiet en niet het project. Gevolg, live reproduceerbaar: een `weeklog` met een lage max-events vult de cache, waarna een `what_did_i_do` over dezelfde periode die te kleine body terugkrijgt en een te laag aantal events rapporteert. Dit is een correctheidsbug, geen performanceprobleem, en staat los van de vraag of de cache überhaupt moet blijven bestaan (zie de aparte beslissingstaak).

Verder in dezelfde taak: `build-kb-index.py` doet een onvoorwaardelijke embedding-probe vóór de incrementele check. Stel die uit tot er daadwerkelijk werk is.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Het tijdelijke bestand waarnaar de embedding-cache wordt geschreven is uniek per proces
- [ ] #2 De cache wordt alleen weggeschreven wanneer er daadwerkelijk iets is toegevoegd of gesnoeid
- [ ] #3 De prune-stap in `build-embed-index.py` kan nog steeds entries verwijderen; een test bewijst dat een gesnoeide entry niet terugkomt
- [ ] #4 De fingerprint-check slaat het lezen van een bestand over wanneer mtime en grootte ongewijzigd zijn
- [ ] #5 Een bestand met gewijzigde mtime maar identieke inhoud wordt niet opnieuw geparsed, en het watermerk wordt in dat geval wél bijgewerkt
- [ ] #6 Een test telt de hash-aanroepen en eist er nul bij een schone incrementele build; er is ook een expliciete case voor een volledige rebuild, zodat een lek in de fastpath niet onopgemerkt blijft
- [ ] #7 De rollup-cachesleutel bevat de event-limiet en het projectfilter
- [ ] #8 Een test reproduceert de kruisbesmetting tussen een weeklog met lage limiet en een daaropvolgende what-did-i-do over dezelfde periode, en is vandaag rood
- [ ] #9 `build-kb-index.py` doet geen embedding-probe wanneer er geen werk te doen is
- [ ] #10 De volledige testsuite draait groen
<!-- AC:END -->
