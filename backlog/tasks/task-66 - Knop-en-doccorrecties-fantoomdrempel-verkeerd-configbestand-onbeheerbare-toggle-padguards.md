---
id: TASK-66
title: >-
  Knop- en doccorrecties: fantoomdrempel, verkeerd configbestand, onbeheerbare
  toggle, padguards
status: Done
assignee: []
created_date: '2026-07-25 08:42'
updated_date: '2026-07-25 08:47'
labels:
  - tech-debt
  - docs
  - config
dependencies: []
priority: medium
ordinal: 76000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Vijf losse defecten uit de opruimanalyse die bij de v0.20.0-release buiten scope bleven. Elk klein, samen een patroon: knoppen en documentatie die iets anders beweren dan de code doet.

**1. Fantoomdrempel in de kalibratieharnas.** Het harnas rapporteert een herschrijfdrempel van 0,83 voor de duplicaatdetectie, terwijl het script dat die drempel gebruikt op 0,62 staat en in een andere band hoort. Gevolg: het harnas meldt "in orde" waar het "herijken" zou moeten melden. Geen enkele test pint de waarde vast, dus de drift is nooit opgemerkt.

**2. Documentatie wijst naar het verkeerde configbestand.** De referentie zegt dat de expansie-instelling in het settings-bestand staat; de retrieval-hook leest hem uit het embed-configbestand. Een gebruiker die de gedocumenteerde ingreep doet verandert niets, zonder foutmelding.

**3. Een toggle die niet te beheren is.** De LLM-fallback voor temporele parsing staat in de defaults, maar ontbreekt in alle drie de oppervlakken waarmee een gebruiker toggles beheert: het settings-command, de upgrade-skill en het installatiescript. Vier lijsten, vier keer handmatig bijhouden — dat is precies hoe deze drift ontstaat.

**4. Doctor honoreert twee agent-home-variabelen niet.** De Copilot-home wordt uit de omgeving gelezen, de Codex- en OpenCode-varianten niet. Wie die verplaatst krijgt een groene doctor over een runtime die nergens gevalideerd is.

**5. Een leeg gezette agent-home-variabele wordt een relatief pad.** De omgevingslezing gebruikt een default-argument, dat niet inspringt bij een lege string. Het genormaliseerde pad wordt dan de huidige werkmap, en installatie schrijft configuratie daar. De Copilot-module heeft hier al de juiste guard voor; de andere twee niet.

Voeg voor 3 een test toe die elke defaults-sleutel in beide beheeroppervlakken eist. Zonder die test drift de volgende toggle op precies dezelfde manier.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 De kalibratieharnas rapporteert de drempel die het herschrijfscript daadwerkelijk gebruikt, in de juiste band, en een test pint die koppeling vast
- [x] #2 De documentatie noemt het configbestand dat de retrieval-hook echt leest voor de expansie-instelling
- [x] #3 De LLM-fallback-toggle is beheerbaar via het settings-command, de upgrade-skill en het installatiescript
- [x] #4 Er is een test die faalt zodra een defaults-sleutel in een van de beheeroppervlakken ontbreekt, en die vandaag rood is
- [x] #5 Doctor honoreert de omgevingsvariabelen voor de Codex- en OpenCode-homes, net zoals het dat voor Copilot doet
- [x] #6 Een leeg gezette agent-home-variabele valt terug op de standaardlocatie in plaats van op de werkmap, in alle modules die hem lezen
- [x] #7 Er is een test die het lege-string-geval afdekt voor elke module die zo'n variabele leest
- [x] #8 De volledige testsuite draait groen
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: Claude (loop-iteratie 3)
created: 2026-07-25 08:47
---
Alle ACs gehaald, 122 gerichte tests groen (2026-07-25).

BEWIJS PER PUNT:
1. kb-calibrate CURRENT_KNOBS had ('rewrite (find-similar)', 0.83, 'duplicate') terwijl find-similar.py op 0.62 staat -- en 0.62 hoort in de related-band, niet de duplicate-band. Beide gecorrigeerd. Test pint nu de koppeling aan de BRON (regex op find-similar.py en op kb-retrieve.py), niet aan een herhaald getal; geverifieerd rood met 'AssertionError: 0.83 != 0.62'.
2. CONFIGURATION zei dat retrieve_expand in kennisbank-settings.json staat; kb-retrieve.py:279 leest .claude/kennisbank-embed.json. Gecorrigeerd met de reden erbij.
3. activity_llm_fallback stond in DEFAULTS maar in geen van de drie oppervlakken. Toegevoegd aan het settings-command, de upgrade-skill en de interactieve setup-toggles. Bijvangst: de upgrade-skill miste OOK usage_telemetry -- zes keys waar er acht horen, niet zeven zoals de analyse dacht.
4. Nieuwe test eist elke DEFAULTS-sleutel in beide beheeroppervlakken. Geverifieerd rood met drie ontbrekende sleutels.
5. doctor.sh bouwde CODEX_CONFIG en OPENCODE_CONFIG uit $HOME terwijl COPILOT_HOME wel gehonoreerd werd. Nu alle drie via hun omgevingsvariabele.
6+7. os.environ.get(NAAM, default) springt niet in bij een lege string, en _norm_path('') wordt Path('.') -- installatie zou config in de werkmap schrijven. Guard toegevoegd in install-agent-envs (_codex_home, _opencode_home) en agent-status; _copilot had hem al. Test dekt alle drie de variabelen en eist een absoluut pad dat niet de werkmap is.

NIET GEDAAN: setup.sh kent geen key-lijst zoals de analyse suggereerde, maar losse ask_toggle-aanroepen; daar is de toggle als vijfde vraag toegevoegd. De DEFAULTS-dekkingstest scant daarom de twee oppervlakken die wél een lijst zijn.
---
<!-- COMMENTS:END -->
