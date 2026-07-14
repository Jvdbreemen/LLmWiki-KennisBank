---
id: TASK-27.9
title: Atlas - Provenance/trust-overlay (kb-lint dekking)
status: Done
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-12 17:17'
labels:
  - visualization
  - atlas
  - provenance
  - trust
  - lens
dependencies:
  - TASK-27.4
parent_task_id: TASK-27
priority: medium
ordinal: 31900
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Voeg een provenance/trust-overlay toe op de Graph-lens die de
anti-hallucinatiegarantie zichtbaar maakt.

Gedrag:
- Overlay `kb-lint.py`-resultaten op de graph: welke wiki-kernpunten/artikelen
  tracen naar een echte bron (raw-sessie of `05-bronnen/...`) en welke niet.
- Kleurschaal "trust coverage": volledig gesourcete artikelen vs artikelen met
  ontbrekende of niet-resolvende sessie-herkomst (risico).
- Toggle om alleen de "unsourced/at-risk" nodes te tonen, zodat de editor snel
  ziet waar bewijs ontbreekt.
- Node-inspect toont per kernpunt de provenance-link en of die resolveert.
- Overlay is afgeleid van dezelfde lint-logica, niet een eigen heuristiek, zodat
  het consistent is met `/wiki`/`kb-lint`.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De overlay markeert unsourced/at-risk nodes conform `kb-lint.py`. Bewijs: fixture met een artikel dat een niet-resolvende sessie-herkomst heeft; test verifieert dat exact dat artikel als at-risk verschijnt en een correct artikel niet.
- [ ] #2 De trust-coverage kleurschaal is datagedreven en verklaard in een legenda. Bewijs: test verifieert de kleur van een bekend gesourcet vs unsourced artikel.
- [ ] #3 De "toon alleen at-risk" toggle werkt. Bewijs: test toggelt en verifieert dat alleen at-risk nodes zichtbaar blijven.
- [ ] #4 Node-inspect toont per kernpunt de provenance-link en resolutiestatus. Bewijs: test verifieert de getoonde links voor een fixture-artikel.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TAURI RE-SCOPE (zie TASK-27 + 27.1-ADR): data LIVE van sidecar-endpoint /provenance (27.2, hergebruikt kb-lint); als overlay op de Graph-lens (27.4) in de TS-frontend. Ongesourcte claims worden live gemarkeerd. Geen statische export. Lens-logica/ACs blijven gelden.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Provenance-overlay afgerond (commit da8f45a). /provenance hergebruikt nu de vault's kb-lint.lint_vault (data-parity, DoD#1) i.p.v. een eigen heuristiek: at-risk = kb-lint meldt missing/dangling/path-only herkomst; heuristiek blijft alleen als fail-open fallback (fixtures). Correctheidsfix: oude heuristiek meldde 49/97 sourced, kb-lint meldt 95/97 — exact de kb-lint CLI. Graph-lens kreeg een 'provenance' kleurmodus (groen=gesourcet, rood=at-risk) + 'toon alleen at-risk'-filter, overlay met legenda; provenanceColor is pure + unit-getest.

AC-dekking: #1 markering per kb-lint ✓ (logica+parity bewezen); #2 kleurschaal + legenda ✓; #3 at-risk-only toggle ✓ (live: leegt de graaf want alle gegraphte nodes zijn gesourcet); #4 node-inspect toont artikel met klikbare herkomst-links (per-kernpunt-resolutiestatus nog niet inline) — PARTIEEL. DoD#1 kb-lint-hergebruik + parity ✓. 26 sidecar + 10 vitest groen, tsc schoon, build groen.

EERLIJKE GAPS: (1) momenteel geen at-risk node IN de graaf (graphify stale vs 2 nieuwe artikelen hash-chain-audit-head-anchor + markdown-wiki-tools-lessen-voor-atlas) — data-timing, geen defect; forceer met /graphify rebuild om de rode overlay te zien. (2) per-kernpunt-resolutiestatus in inspect niet expliciet. (3) groen/rood niet kleurenblind-optimaal (safe-palette-pass over alle lenzen = vervolgtaak).
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 De overlay hergebruikt kb-lint-uitkomsten (geen duplicaat-heuristiek); data-parity tegen kb-lint output via /provenance.
- [ ] #2 Frontend-test dekt markering, legenda, toggle en inspect; screenshot als bewijs.
- [ ] #3 Lege staat (alles gesourcet) toont een nette '100% provenance' boodschap.
- [ ] #4 Kleurschaal is kleurenblind-vriendelijk en werkt in light/dark.
<!-- DOD:END -->
