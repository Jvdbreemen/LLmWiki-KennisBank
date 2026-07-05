---
id: TASK-23
title: >-
  memory-doctor rejudge: her-judge fail-safe-unverified memories na een
  LLM/Ollama-outage
status: In Progress
assignee: []
created_date: '2026-07-05 10:59'
updated_date: '2026-07-05 11:00'
labels:
  - agent-geheugen
dependencies: []
ordinal: 25000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Probleem (gemeten deze sessie): tijdens een Ollama/LLM-outage laat de capture-judge memories fail-safe op status=unverified (twijfel -> unverified). Als de outage lang duurt stapelen die op (deze vault: 31 unverified, 30 >48u). Er is GEEN built-in operatie om ze na herstel te her-judgen: memory-sweep captured alleen NIEUWE transcripts en recheck_pass (cross-memory v2) re-judget alleen CURRENT memories (retract-richting), niet unverified. De health-melding ('sweep/judge promoot ze niet - check Ollama') wijst het gat aan maar biedt geen fix. Handmatig one-off script deze sessie promootte 25/31 correct (6 bleven terecht unverified: judge zei nog steeds unverified), rot 30->4, daarna kb-index herbouwd zodat de gepromote memories recallbaar werden.

Voorstel: een subcommando `memory-doctor.py rejudge [--limit N] [--dry-run]` (of `memory-sweep --rejudge-unverified`). Logica: itereer 09-memory-files met status=unverified, her-judge de body via _judge.judge, en zet status naar current ALLEEN bij een expliciet 'current'-verdict. FAIL-SAFE: twijfel/model-down/unverified-verdict laat de memory unverified; nooit retracten, nooit ruis promoten. Gebruikt de bestaande _judge + _memory.set_status seams. Referentie-implementatie staat als one-off in de scratchpad (rejudge-unverified.py). Overwegingen: (a) gate op reachability zoals de sweep-maintenance (draai niet op dode judge); (b) na promotie de kb-index verversen (of de sweep-launch build-kb-index laat dat al doen); (c) optioneel een --hours filter zodat alleen oud-genoeg unverified meegaat; (d) doctor/heartbeat kan het aantal promootbare tonen. Overweeg of dit een aparte doctor-subcommando is of een pass in de sweep-maintenance (na de reachability-gate). Verwant maar apart van TASK-16 (embed_failed/verloren kandidaten) en TASK-15 (cluster-timing).
<!-- SECTION:DESCRIPTION:END -->
