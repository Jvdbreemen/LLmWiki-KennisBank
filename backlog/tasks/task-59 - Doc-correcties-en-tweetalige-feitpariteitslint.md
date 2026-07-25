---
id: TASK-59
title: Doc-correcties en tweetalige feitpariteitslint
status: Done
assignee: []
created_date: '2026-07-25 05:07'
updated_date: '2026-07-25 08:26'
labels:
  - docs
  - tech-debt
  - adr-0002
dependencies:
  - TASK-53
priority: high
ordinal: 69000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
De documentatie bevat claims die aantoonbaar niet met de code overeenkomen. Eén daarvan is actief schadelijk, de rest ondermijnt vertrouwen.

**Actief schadelijk.** `TROUBLESHOOTING.md` beweert dat het vaultpad "in elk script" hardcoded staat en draagt de lezer op padconstanten per script te wijzigen. Dat is precies de regressie die ADR-0002 verbiedt: alle scripts resolven de vault via `_vaultpath.vault_root()`, dat `KENNISBANK_VAULT` eerbiedigt. Een gebruiker die dit opvolgt sloopt de resolver. De tekst is sinds 2026-05-08 onaangeraakt terwijl de env-var op 2026-06-14 landde.

**Contractleugen.** `AGENTS.md` stelt op vijf plekken dat Codex en Copilot hookless zijn en dat validatie geen hooks verwacht. Dat volgde uit ADR-005, die inmiddels Superseded is door ADR-006. De configuratievalidatie eist juist dat elke lifecycle-hook exact één keer voorkomt. AGENTS.md presenteert zichzelf als het agent-facing deploycontract, dus een agent die het volgt keurt een correcte installatie af. README en de integratiedocumentatie zijn wél bijgewerkt; dit bestand is achtergebleven.

**Kleinere onwaarheden.** Beide README-varianten beloven sub-seconde retrieval terwijl het plafond twee seconden is en alleen op de embed-call slaat; het CHANGELOG spreekt zichzelf daarover in één zin tegen. Beide README's noemen drie MCP-primitieven waar het er zes plus een resource zijn. `POST-INSTALL.md` drukt een verzonnen doctor-transcript af in een formaat dat het script nooit uitzendt. `TROUBLESHOOTING.md` documenteert een omgevingsvariabele voor de Ollama-endpoint die geen enkele regel code leest — de shell-voorbeelden kloppen wel, want de CLI leest hem; alleen het proza is fout.

**De onderliggende oorzaak, en het eigenlijke werk.** Documentatie wordt per opsomming bijgewerkt: wat niet op de lijst staat blijft staan. Eén commit raakte beide README's maar corrigeerde alleen de Engelse alinea, waardoor de Nederlandse de superseded tekst behield. De `.nl`-varianten zijn geen forks maar mee-geredigeerde vertalingen — vier paren, identieke koppenvolgorde — dus vertaling propageert fouten in plaats van ze te vangen. Een lint die tweetalige feitpariteit en code-afgeleide feiten bewaakt, is de enige duurzame oplossing.

Scope de lint subtractief (alle markdown minus changelog, ADR's, backlog en atlas), niet via een handonderhouden lijst: die lijst wordt anders zelf de volgende verouderde doc. Verbied de concrete claim, niet het woord — "sub-second" staat legitiem in de principes- en waardendocumenten als noordster.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 De TROUBLESHOOTING-passage draagt niet langer op om padconstanten per script te wijzigen, maar verwijst naar de omgevingsvariabele en de resolver
- [x] #2 De vijf onjuiste hook-claims in AGENTS.md beschrijven wat de code doet: hooks worden geïnstalleerd en validatie eist ze
- [x] #3 Beide README-varianten en het CHANGELOG beschrijven de embed-timeout naar waarheid, en noemen het juiste aantal MCP-primitieven
- [x] #4 Het verzonnen doctor-transcript in POST-INSTALL.md is vervangen door echt gevangen uitvoer
- [x] #5 De proza-claim over de Ollama-omgevingsvariabele is gecorrigeerd; de shell-voorbeelden blijven staan
- [x] #6 Er is een lint die voor elk markdown-paar met een .nl-variant de verzameling backticked identifiers, paden en variabelen vergelijkt en bij verschil faalt
- [x] #7 Er is een lint die code-afgeleide feiten controleert: het aantal MCP-primitieven en de embed-timeout, plus gedocumenteerde omgevingsvariabelen die nergens gelezen worden
- [x] #8 De lint bepaalt zijn bestandenlijst subtractief, niet via een handonderhouden opsomming
- [x] #9 De lint verbiedt de concrete claim en niet het losse woord, zodat de noordster-formuleringen in de principes- en waardendocumenten blijven staan
- [x] #10 De volledige testsuite draait groen
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: Claude (loop-iteratie 1)
created: 2026-07-25 08:26
---
AC#4 gesloten (2026-07-25). Bij v0.20.0 liet ik dit open met de redenering dat echt gevangen doctor-uitvoer een vault vereist die niet van mij is. Dat klopte niet: setup.sh bouwt een volledige vault in een wegwerpmap, en dat is echte uitvoer zonder persoonlijke paden.

Gevangen via een temp-HOME met `bash setup.sh --yes --agents claude --skip-model-check`, daarna `doctor.sh`, met het temp-pad ge-sed naar $HOME. Werkelijke uitvoer: 137 regels, footer `Summary / [PASS] 113 / [WARN] 1 / [FAIL] 0 / [INFO] 14`. Het verzonnen transcript beweerde `[ok]`-regels en `Done. 0 errors, 2 warnings.` -- doctor.sh emit geen van beide en heeft dat nooit gedaan.

De vervangende sectie legt ook de vier tiers uit, want die betekenen verschillende dingen en dat stond nergens.

BIJVANGST ALS BEWIJS: de verse install rapporteert `[PASS] temporal locales: 74 maandwoorden, 50 dagwoorden`. Dat is onafhankelijke bevestiging dat de locale-deployfix uit TASK-45 end-to-end werkt -- vóór die fix zou die tabel op een schone installatie leeg zijn geweest.

Nieuwe guard in tests/test_docs_consistency.py: documentatie die doctor-uitvoer citeert mag geen markers gebruiken die het script niet emit. Geverifieerd rood tegen de oude tekst, groen erna.
---
<!-- COMMENTS:END -->
