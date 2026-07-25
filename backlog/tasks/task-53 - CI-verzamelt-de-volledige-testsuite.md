---
id: TASK-53
title: CI verzamelt de volledige testsuite
status: Done
assignee: []
created_date: '2026-07-25 03:35'
updated_date: '2026-07-25 07:50'
labels:
  - ci
  - tests
  - tech-debt
dependencies: []
priority: high
ordinal: 67000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
De CI-workflow draait de tests met de unittest-discovery van de standaardbibliotheek. Een deel van de testbestanden is echter in pytest-stijl geschreven — losse module-level functies met fixtures — en die worden door unittest niet verzameld. Gemeten: unittest verzamelt 743 tests, pytest 764. Ongeveer twintig tests hebben dus nog nooit gedraaid.

Dat is niet alleen een dekkingsgat. Het bestand dat de integratie-documentatie bewaakt is er één van: er ligt al een doc-guard in de repo die nog geen enkele keer is uitgevoerd. Dat is de onderliggende oorzaak van de verouderde documentatieclaims elders in de codebase — er stond een poort, maar niemand liep erlangs.

De volledige suite onder pytest gedraaid geeft momenteel 761 geslaagd, 1 gefaald, 2 overgeslagen. Die ene fout betreft een assertie over een verwijderde client en moet als onderdeel van deze taak worden opgelost of expliciet verantwoord.

Er is een waardenkeuze: pytest toevoegen als ontwikkelafhankelijkheid, of de betreffende bestanden omzetten naar unittest-stijl. Omzetten kost ongeveer 438 regels herschrijfwerk maar laat de faalmodus verdwijnen in plaats van hem af te dekken; pytest toevoegen is één stap maar introduceert een afhankelijkheid in een repo die bewust op de standaardbibliotheek draait. Leg de gemaakte keuze vast in de taaknotities.

Voeg in beide gevallen een meta-guard toe die voorkomt dat dit terugkeert. Die guard moet de broncode parsen en eisen dat er geen test-functies op moduleniveau staan. Een stringcheck op de aanwezigheid van een unittest-basisklasse is niet voldoende: die slaagt vandaag op een bestand dat wél een dode test-functie op moduleniveau heeft.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De CI-stap verzamelt en draait alle testbestanden in de tests-map; het aantal verzamelde tests komt overeen met wat een volledige verzameling oplevert
- [ ] #2 De testafhankelijkheid staat, indien toegevoegd, in een aparte ontwikkelafhankelijkhedenlijst en niet in de runtime-requirements
- [ ] #3 De vandaag falende test is opgelost of expliciet en beargumenteerd overgeslagen
- [ ] #4 Er is een meta-guard die de testbronnen parseert en eist dat er geen testfuncties op moduleniveau staan
- [ ] #5 De meta-guard is vandaag rood op de bestaande bestanden die dit probleem hebben
- [ ] #6 De dekkingsdrempel in CI blijft gehandhaafd
- [ ] #7 De gekozen aanpak en de reden staan in de taaknotities
- [ ] #8 De volledige testsuite draait groen in CI
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Gekozen: pytest als dev-dependency (beslissing gebruiker, 2026-07-25), niet omzetten naar unittest-stijl. Reden: de ~18 nooit-gedraaide tests moeten vandaag draaien, en de deploy-kant blijft stdlib-only -- pytest raakt alleen CI en de ontwikkelmachine. Vastgelegd in requirements-dev.txt, dat requirements.txt include't; de runtime-requirements zijn ongewijzigd.

GEMETEN (Windows-ontwikkelmachine, 2026-07-25):
- unittest discover: 763 tests, OK (2 skipped), 1194 s
- pytest: 781 tests, 1 failed -> nu 782 groen, 2 skipped, 1197 s
Verschil = 18 tests in zes bestanden die nooit hebben gedraaid. De analyse sprak van vijf bestanden en 21 tests; het zijn er zes en 21 functies, waarvan 18 netto extra collectie.

De ene falende test was `test_product_surfaces_have_no_removed_client_reference`: docs/research/cross-client-hooks-plugin-architecture.md noemt Cursor als KANDIDAAT voor de toekomstige adapter-boom. Opgelost door docs/research/ uit de sweep te halen -- research is verkennend materiaal, geen productoppervlak -- niet door de assertie te verzwakken.

BIJVANGST: CI stond op timeout-minutes: 15 met een comment die '~5-8 min' beweerde. De suite duurt ~20 min. Die job zou op de klok gesneuveld zijn zodra hij de volledige collectie draaide. Verhoogd naar 30 met de gemeten cijfers in het comment.
<!-- SECTION:NOTES:END -->
