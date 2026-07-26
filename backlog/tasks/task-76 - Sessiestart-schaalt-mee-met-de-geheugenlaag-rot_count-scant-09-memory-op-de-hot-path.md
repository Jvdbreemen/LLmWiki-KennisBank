---
id: TASK-76
title: >-
  Sessiestart schaalt mee met de geheugenlaag: rot_count scant 09-memory op de
  hot path
status: In Progress
assignee: []
created_date: '2026-07-25 21:33'
updated_date: '2026-07-26 09:01'
labels:
  - performance
  - hooks
  - sessiestart
  - geheugen
dependencies:
  - TASK-74
references:
  - 'scripts/memory-notify.py:28'
  - 'scripts/memory-doctor.py:73'
  - scripts/memory-sweep.py
priority: medium
ordinal: 86000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
memory-notify.py roept bij ELKE sessiestart _rot() aan, en die komt uit op memory-doctor.rot_count(48). Dat leest ELK .md-bestand in 09-memory en parseert de frontmatter (memory-doctor.py:79 `for f in mdir.glob("**/*.md")`).

GEMETEN 2026-07-25, vault met 1185 geheugenbestanden, mediaan van 3 runs:
  _rot()                 509,3 ms
  notice() (hele hook)   543,0 ms      -> _rot is 94%
  _sweepstate.pending()   14,4 ms

Het absolute getal is niet het echte bezwaar -- na TASK-74 staat de koude sessiestart op 1.289 ms, ruim binnen het doel van 3 s. Het bezwaar is de GROEIRICHTING: deze kost is O(n) in de omvang van de geheugenlaag. Elke memory die KennisBank erbij leert, maakt de sessiestart trager. Dat is precies wat noord-ster 1 uitsluit ("zware verwerking off de hot path") en het is het soort regressie dat niemand opmerkt, omdat hij per sessie een paar milliseconde bedraagt.

De uitkomst is bovendien geen live feit: het aantal 'unverified memories ouder dan 48u' verandert alleen wanneer de sweep/judge draait -- en die draait al in de losgekoppelde worker.

RICHTING: memory-sweep.py schrijft al een heartbeat die memory-notify uitleest (model_unreachable, errors, last_run). Zet de telling daarbij in, en laat notice() hem aflezen in plaats van berekenen. Aandachtspunten:
  - de telling moet ook geschreven worden wanneer het model onbereikbaar was; het is een lokale scan en staat los van Ollama
  - ontbreekt de sleutel (oude heartbeat, sweep nog nooit gedraaid), dan de melding overslaan in plaats van alsnog scannen -- zelfherstellend, want de worker draait bij elke sessiestart
  - de melding wordt daarmee hoogstens een sweep-cyclus oud, wat voor 'sweep promoot ze niet' ruim voldoende is

APART OPGEMERKT, niet de kern van deze taak: memory-doctor.py:77 doet `date.today() - timedelta(hours=hours)`. Date-rekenen kapt op hele dagen, dus voor hours < 24 wordt de cutoff vandaag en telt de check feitelijk 'ouder dan 0 uur'. Bij de gebruikte 48 uur klopt het toevallig (precies 2 dagen). Meenemen of los oppakken.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 memory-notify leest de rot-telling af in plaats van 09-memory te scannen
- [x] #2 De sessiestart-kosten van memory-notify groeien niet meer met het aantal memories; bewezen met een meting op de echte vault
- [x] #3 De telling wordt ook bijgewerkt wanneer het embed/LLM-model onbereikbaar was
- [x] #4 Ontbrekende telling laat de sessiestart niet alsnog scannen en breekt de melding niet
- [ ] #5 Volledige suite groen
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
UITGEVOERD 2026-07-26.

De telling verhuisde van de sessiestart naar de sweep. memory-sweep._write_heartbeat schrijft nu `rot` en `rot_hours`; memory-notify leest die af.

GEMETEN:
  memory-notify.notice()   543,0 ms -> 8,9 ms   (61x)
  _rot_count() in de worker              427 ms   (dezelfde scan, nu gratis)
  koude sessiestart        1214 ms -> 1183 ms

De sessiestart-winst is kleiner dan de 509 ms die uit de hook verdween, en dat klopt: de notificaties draaien PARALLEL, dus alleen het maximum van de groep telt. memory-notify was met ~700 ms dat maximum; nu is git-upstream-check (493 ms) dat.

SCHRIJFPLEK BEWUST IN _write_heartbeat, niet in run_sweep. Die functie wordt op ELK uitgangspunt aangeroepen -- ook wanneer memory_capture uit staat en wanneer het model onbereikbaar is. Daarmee is AC #3 structureel geregeld in plaats van per pad; de telling is een lokale scan en heeft met Ollama niets te maken.

GEEN TERUGVAL OP ZELF SCANNEN bij een ontbrekende sleutel. Dat zou de kosten terugbrengen op precies het pad waar ze weg moesten. De melding zwijgt dan een sessie lang; de worker draait bij elke sessiestart, dus hij is de volgende keer gevuld. Waargenomen bij het deployen: direct na de deploy was de melding leeg omdat de heartbeat de sleutel nog niet kende -- het zelfherstellende pad, zoals ontworpen.

test_rot_zonder_telling_zwijgt_en_scant_niet legt dat vast EN bewijst tegelijk dat er niet meer gescand wordt: er ligt een rottende memory op schijf en de melding blijft toch leeg.

DAGGRANULARITEIT-BUG uit de taakomschrijving meegenomen. memory-doctor deed `date.today() - timedelta(hours=hours)`; date-rekenen gooit de restfractie stilzwijgend weg, dus onder de 24 uur werd de cutoff vandaag en telde de check feitelijk 'ouder dan vandaag'. Nu expliciet `timedelta(days=max(1, hours // 24))`, met de reden erbij. Bij de gebruikte 48 uur verandert er niets.

Tests: 5 nieuwe (3 notify, 2 sweep). Suite 874 groen.
<!-- SECTION:NOTES:END -->
