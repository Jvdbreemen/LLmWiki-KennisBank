---
id: TASK-52
title: Write-only activity-tabellen droppen met migratie
status: Done
assignee: []
created_date: '2026-07-25 03:34'
updated_date: '2026-07-25 07:50'
labels:
  - tech-debt
  - performance
  - migration
  - temporal
dependencies: []
priority: medium
ordinal: 66000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Vier tabellen in de activity-database worden bij elke indexbouw gevuld en door geen enkele query gelezen. Repo-brede verificatie: alleen CREATE, DELETE en INSERT, nul SELECT. Het onderwerpfilter dat de FTS-tabel zou moeten gebruiken doet in werkelijkheid een substring-vergelijking in Python.

Op de vault van de auteur: samen ongeveer 23,7 van 57,7 MB, met 84.969 rijen in de onderwerpentabel, 15.193 in de entiteitentabel en 4.234 in de artefactentabel.

De ruimte is niet de hoofdreden. De DELETE op de FTS-tabel gebruikt een niet-geïndexeerde kolom en doet dus een volledige scan: gemeten 45 ms per event tegen 0,26 ms voor een normale tabel, en die DELETE draait twee keer per event. Dat is kwadratisch gedrag op een volledige rebuild — in de orde van minuten, op een pad dat de sessiestart raakt.

**Implementatievereisten die niet optioneel zijn.** Verwijder per tabel de CREATE, de DELETE en de INSERT samen; alleen de CREATE weghalen breekt de eerste upsert op een verse vault. Zet in de schema-initialisatie een expliciete DROP-instructie terug, anders blijven de rijen eeuwig wees in elke bestaande installatie: de incrementele bouw hergebruikt het databasebestand en alleen een volledige rebuild verwijdert het. Bump de schemaversie NIET — doctor en de statusrapportage zetten dan elke gedeployde vault op waarschuwing tot de gebruiker handmatig een volledige rebuild draait.

Verwacht dat het bestand niet direct krimpt: een DROP geeft pagina's vrij aan de freelist en pas een VACUUM of volledige rebuild verkleint het bestand.

Impactnotitie, geen werk: de Atlas-sidecar leest deze database. Controleer of hij een van de vier tabellen aanraakt en meld het resultaat; wijzig niets onder atlas/.

De kolom voor de datum zonder tijd in de eventtabel is eveneens bewezen dood, maar die verwijderen vergt een kolom-drop op een bestaande database. Die is bewust NIET in scope en wacht op een migratie die toch een rebuild forceert.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De vier write-only tabellen worden niet meer aangemaakt en niet meer gevuld
- [ ] #2 De schema-initialisatie verwijdert de tabellen op bestaande databases, zodat er geen weesrijen achterblijven
- [ ] #3 De schemaversie is ongewijzigd, zodat gedeployde vaults geen waarschuwing krijgen
- [ ] #4 Een test bewijst dat een incrementele bouw op een database die de oude tabellen bevat, ze verwijdert
- [ ] #5 Een test bewijst dat een verse vault een volledige indexbouw doorloopt zonder fouten
- [ ] #6 Het onderwerpfilter en de zoekfunctionaliteit gedragen zich onveranderd; bestaande tests daarvoor blijven groen
- [ ] #7 De documentatie die deze tabellen beschrijft is bijgewerkt
- [ ] #8 Er is vastgesteld en gerapporteerd of de Atlas-sidecar een van de vier tabellen leest; onder atlas/ is niets gewijzigd
- [ ] #9 De volledige testsuite draait groen
<!-- AC:END -->
