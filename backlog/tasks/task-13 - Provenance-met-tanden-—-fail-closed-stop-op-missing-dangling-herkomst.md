---
id: TASK-13
title: Provenance met tanden — fail-closed stop op missing/dangling herkomst
status: Done
assignee: []
created_date: '2026-07-03 04:21'
updated_date: '2026-07-03 18:44'
labels: []
dependencies: []
ordinal: 15000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Vandaag is er nergens een fail-closed grens op wiki-herkomst. Een destillatie-hallucinatie die een [[raw-sessie]]-link sloopt (missing/dangling artikel) kan ongezien op de vault landen — precies de faalmodus uit kb-lint.py's eigen docstring (regels 5-9). De bestaande poorten zijn allemaal zacht: /wiki stap 4.5 (commands/wiki.md:82-88) is een model-prompt met expliciete ontsnapping ('waarschuwingen mag je laten staan'), en doctor.sh 13d (scripts/doctor.sh:308-329) mapt lint-findings naar report_warn (nooit FAIL). Detectie bestaat dus al en is deterministisch (kb-lint.py, exit 0/1/2, --json); wat ontbreekt zijn de tanden.

Uitkomst van een voorstander-vs-scepticus panel over 6 steel-ideeen uit het GitHub-vergelijkingsonderzoek (research: ~/Claude/research/2026-07-03-llmwiki-implementaties-vergelijking.md). Dit was het ENIGE idee met echte, door-de-code-bevestigde meerwaarde — maar bewust in de SMALLE variant. NIET als green-CI merge-gate (die inhoud staat in ~/KennisBank, niet in de repo; een Action zou de soevereine vault naar de cloud pushen — schendt local-first) en NIET als git-pre-commit-hook (setup.sh doet nooit git init op de vault, dus inert op de default-topologie; en bij bus-factor-1 leidt een vervelende gate tot reflexief --no-verify → signaal dood).

Kies EEN van twee even-goede plekken (beide binnen de bestaande Claude-hook/command-laag, werkt op elke topologie, geen nieuw mechanisme):
(A) /wiki stap 4.5 deterministisch maken: laat het command kb-lint ECHT draaien op de zojuist geschreven/herschreven artikelen en HARD stoppen op missing/dangling VOOR commit/afronding (path-only en oudere-artikel-warnings blijven advisory).
(B) doctor.sh 13d provenance-lint van WARN naar een FAIL-tier promoveren voor missing/dangling (path-only blijft WARN).

Alleen missing/dangling worden fail-closed; path-only en pre-existing warnings blijven advisory (anders begraaf je de signalen die er WEL toe doen). Governance-hardening, geen feature — ~10-20 regels. Geen LLM-kosten (kb-lint is stdlib-deterministisch).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Missing- of dangling-herkomst in een nieuw/herschreven artikel leidt tot een harde stop (niet-nul exit of expliciete block), niet enkel een WARN
- [x] #2 path-only en pre-existing (oudere-artikel) warnings blijven advisory — alleen missing/dangling is fail-closed
- [x] #3 Werkt op de default-topologie (vault buiten de repo, geen git in de vault); geen cloud-push, geen nieuw git-hook/CI-mechanisme
- [x] #4 kb-lint blijft stdlib-deterministisch en fail-open bij eigen fouten (geen vault → geen valse block); nul LLM-kosten
- [x] #5 Gedocumenteerd in CONFIGURATION.md en de /wiki- of doctor-sectie; unit-test dekt de fail-closed tak
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Provenance met tanden geïmplementeerd in de smalle, dominante variant (panel-advies): een deterministisch primitief in kb-lint + beide consumenten bedraad, geen git-hook/CI/cloud.

- kb-lint.py: HARD_TYPES onderscheidt missing/dangling (niet-auditeerbaar) van path-only (advisory). Nieuw --strict: exit 2 ALLEEN op HARD, path-only geeft 0. JSON-rapport draagt een 'hard'-teller. Exit 1 blijft operationele fout (fail-open, geen valse block).
- doctor.sh 13d: HARD -> report_fail (FAIL-tier), path-only -> report_warn, schoon -> report_pass.
- commands/wiki.md stap 4.5: draait kb-lint --strict als HARDE STOP vóór afronden; exit 2 = fix eerst, niet afronden.

Deterministisch, nul LLM-kosten, werkt op elke topologie. Bewust NIET als green-CI merge-gate (vault buiten repo -> zou soevereiniteit schenden).

Verificatie: 36 kb-lint-tests groen (incl. 7 subprocess exit-code integratietests voor --strict), volledige suite groen. Live: schone Kluis-vault (69 art) -> --strict exit 0 + doctor PASS; temp-vault met dangling link -> --strict exit 2 [HARD] + doctor 13d-branch FAIL. Gedeployed naar vault + global command.
<!-- SECTION:FINAL_SUMMARY:END -->
