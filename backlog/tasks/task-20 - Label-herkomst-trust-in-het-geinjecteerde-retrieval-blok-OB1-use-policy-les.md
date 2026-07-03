---
id: TASK-20
title: Label herkomst/trust in het geinjecteerde retrieval-blok (OB1 use-policy-les)
status: To Do
assignee: []
created_date: '2026-07-03 22:58'
labels: []
dependencies: []
ordinal: 22000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
STEEL-IDEE uit de OB1-vergelijking (2026-07-04, research: ~/Claude/research/2026-07-04-ob1-openbrain-vs-kennisbank.md, geverifieerd via 35-agent adversariele pass). OB1 dwingt op DB-niveau af dat een memory NIET als instructie/autoriteit gebruikt mag worden tenzij de herkomst mens-gesourced is (CHECK (can_use_as_instruction=false OR provenance_status IN ('user_confirmed','imported')), schemas/agent-memory/schema.sql). Dat scheidt 'mag als autoriteit tellen' van 'mag als hint tellen'.

ONS GAT (geverifieerd): de retrieval-hook injecteert ALLE current memories met GELIJKE autoriteit. Een autonoom door een agent geextraheerde memory (evidence_basis 'agent') verschijnt in het context-blok naast een door de mens getypte memory ('getypt') zonder enig onderscheid. Het consumerende model kan niet zien wat mens-autoriteit is en wat een onbevestigde agent-gok is. Dat botst met ons kernprincipe mens=update-autoriteit, en de memory-poisoning-literatuur (arxiv 2605.12493, uit de llmwiki-research) noemt herkomst-labeling in de context expliciet als mitigatie.

HET IDEE (bewust ANDERS dan TASK-18): TASK-18 weegt trust in de RANK (welke memories surfacen). Deze task labelt herkomst in de INJECTIE (hoe het model de gesurface memories BEHANDELT). Complementair, ander mechanisme. Governance-conservatiever: we verbergen niks (geen suppressie), we MARKEREN — mens/model beslist. Een onbevestigde of agent-geextraheerde memory blijft zichtbaar maar krijgt een tag zodat het model hem kan discounten.

MOGELIJKE INGREEP (klein, deterministisch):
- kb-retrieve: toon per geinjecteerde memory een compacte herkomst/status-tag, bv. '(bron: agent, onbevestigd)' vs '(bron: getypt)'. Deterministische lookup op evidence_basis + status, geen LLM.
- Alleen memories; wiki-artikelen zijn al gecureerd (evergreen), die niet taggen.
- Formuleer de tag zo dat het model 'getypt/mens-in-lus' als autoritatief leest en 'agent/onbevestigd' als hint.

BEGRENZING/PRINCIPES: puur presentatie in de injectie, GEEN filter/suppressie, GEEN nieuw veld (evidence_basis + status bestaan al), geen LLM in het pad. Meet niet met kb-eval (recall verandert niet — de set die surfacet blijft gelijk); dit is een kwalitatieve/gedrags-verbetering, dus verifieer met een handmatige inspectie van een paar injectie-blokken dat de tags kloppen en leesbaar zijn. Relevantie NU concreet: de SessionStart-hook meldt 8 unverified memories >48u — die worden nu ongelabeld als autoriteit geinjecteerd.

Raakt: kb-retrieve (injectie-formattering), _memory.py (evidence_basis + status als bron voor de tag), TASK-18 (rank-trust; deze is de injectie-tegenhanger, plan ze samen), TASK-13 (provenance-fail-closed; zelfde herkomst-as, ander punt in de pijplijn).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 kb-retrieve toont per geinjecteerde MEMORY een compacte deterministische herkomst/status-tag (evidence_basis + current/unverified); wiki-hits blijven ongetagd
- [ ] #2 Tag-formulering laat mens-herkomst (getypt/mens-in-lus) als autoritatief lezen en agent/onbevestigd als hint; geverifieerd op een handvol echte injectie-blokken
- [ ] #3 Puur presentatie: geen filter/suppressie, geen nieuw veld, geen LLM in het injectie-pad
- [ ] #4 Bewust-niet-gemeten-met-kb-eval gedocumenteerd (recall-set verandert niet); i.p.v. handmatige inspectie dat de tags kloppen en leesbaar zijn
<!-- AC:END -->
