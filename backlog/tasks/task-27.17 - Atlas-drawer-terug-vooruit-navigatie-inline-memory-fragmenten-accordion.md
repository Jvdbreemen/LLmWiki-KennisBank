---
id: TASK-27.17
title: 'Atlas: drawer terug/vooruit-navigatie + inline memory-fragmenten (accordion)'
status: Done
assignee: []
created_date: '2026-07-13 22:38'
updated_date: '2026-07-14 18:23'
labels:
  - atlas
  - frontend
  - ux
dependencies: []
references:
  - >-
    docs/superpowers/specs/2026-07-14-atlas-drawer-navigatie-inline-memories-design.md
parent_task_id: TASK-27
priority: medium
ordinal: 47000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
UX-fix voor de inspect-drawer op basis van gebruikersfeedback: (1) wikilink-navigatie heeft geen weg terug; (2) memory-ingangen vervangen het artikel i.p.v. inline te tonen.

Ontwerp goedgekeurd, zie docs/superpowers/specs/2026-07-14-atlas-drawer-navigatie-inline-memories-design.md.

Kern: back/forward-stacks + ←/→ knoppen in de drawer-kop (Alt+←/→), reset bij sluiten of nieuw root-document; memory-entry-points worden accordion-items die het fragment lazy laden via client.doc en cachen per stem, artikel blijft staan. Alleen frontend (inspect.ts, style.css). Na implementatie Tauri-bundle opnieuw bouwen.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 ←/→ knoppen in de drawer-kop navigeren door de documenthistory; disabled bij lege stack; Alt+←/→ werkt
- [x] #2 History reset bij drawer sluiten en bij openen van een nieuw root-document vanuit een lens
- [x] #3 Klik op memory-ingang klapt het fragment inline uit (▸/▾), lazy geladen en per stem gecachet; artikel blijft staan
- [x] #4 Wikilinks binnen een uitgeklapt fragment gebruiken de drawer-navigatie met werkende terug-knop
- [x] #5 Laadfout in een fragment toont één foutregel, artikel blijft intact
- [x] #6 Vitest-tests voor history-stack en accordion toggle/cache draaien groen
- [x] #7 Tauri-bundle (MSI/NSIS) opnieuw gebouwd met de wijzigingen
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Geïmplementeerd in commit 4cf26b6 (history.ts + DocHistory-tests, inspect.ts herschreven, accordion-CSS). Typecheck schoon, 28 vitest-tests groen. Tauri-bundle opnieuw gebouwd via npx @tauri-apps/cli build op 2026-07-14 00:48 (MSI 41.2 MB + NSIS 40.0 MB, verse timestamps geverifieerd; nieuwe code aantoonbaar in dist-bundle via insp-nav/acc-marker grep). Let op: `cargo tauri` bestaat niet op deze machine — bundelen gaat via de npm-CLI; BUILD.md stap 3 wijkt daarin af. AC 1-5 zijn code-af en unit-getest maar wachten op handmatige smoke-test in de app door Robert.

Bugfix na smoke-test Robert: gebundelde app toonde permanent 'sidecar onbereikbaar: Failed to fetch'. Root cause: PyInstaller-sidecar cold start duurt seconden tot tientallen seconden (eerste boot na install + AV-scan; gemeten 6-20s, onder load >60s), terwijl de frontend één health-fetch zonder retry deed. Fix in commit 42ba5a5: readiness.ts waitUntilReady-poll (400ms basis, 1.5x backoff cap 2s, 60s budget), eerste lens-render gegated op health-OK, statusbar toont nu ook het geresolvede vault-pad uit KENNISBANK_VAULT ter verificatie. 4 nieuwe tests, 32 totaal groen. Bundle herbouwd 2026-07-14 08:02/08:03 (MSI+NSIS), readiness-code geverifieerd aanwezig in dist-bundle.

E2e-validatie als standalone app (2026-07-14): NSIS silent-install (/S, currentUser) naar C:\Users\rvdbr\AppData\Local\KennisBank Atlas, registry-entry aanwezig (DisplayVersion 0.1.0). App gestart: kennisbank-atlas.exe pid 58940 responding, sidecar-kind atlas-sidecar.exe luistert op 127.0.0.1:34592. /health: status ok, vault=D:\Users\Robert\Documents\Claude\Projects\Kluis (uit KENNISBANK_VAULT), alle 6 bronnen live. /graph: 101 nodes, 166 links. /doc: wiki-index rendert. Bijvangst: 5 wees-sidecar-processen opgeruimd, waaronder 2 uit een verwijderde oude Program Files-install — sidecar-orphaning bij abnormale shutdown is een bekend risico; overweeg een parent-PID-watchdog in de sidecar als aparte taak.

Derde en beslissende root cause gevonden en gefixt (commit 13930b4): CORS-regex stond alleen https://tauri.localhost toe terwijl Windows WebView2 http://tauri.localhost gebruikt — elke fetch in de gebundelde app faalde daardoor permanent, los van timing. Bewezen met curl + Origin-headers tegen de live sidecar (header ontbrak op http-variant, aanwezig na fix). Bundle herbouwd (NSIS 29MB, onedir), silent geïnstalleerd, e2e gevalideerd met screenshots: (1) native app met graph geladen en statusbar 'sidecar ok · vault: Kluis · 6 bronnen'; (2) drawer met Memory-ingangen; (3) accordion inline uitgeklapt; (4) wikilink-navigatie met ← enabled; (5) terug bij bronartikel, ← disabled/→ enabled (programmatisch geverifieerd). AC 1-3 aangetoond; AC 4-5 code-af en unit-getest maar niet apart visueel gedemonstreerd. Interactie-bewijs via Playwright op de gebouwde frontend (vite dist op 127.0.0.1:18091) tegen de sidecar van de geïnstalleerde app (poort 58176); native app zelf toont graph correct. Recall-lens gaf 'degraded' tijdens test (Ollama-embed traag) — los issue, niet deze taak.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Drawer terug/vooruit-navigatie (DocHistory, Alt+←/→, verse history per root-open) en memory-fragmenten als inline accordion. Onderweg drie gebundelde-app-blockers gevonden en gefixt: (1) CORS-regex miste http://tauri.localhost (Windows WebView2) — dé oorzaak van permanente "Failed to fetch"; (2) startup-race — frontend pollt nu onbegrensd met zichtbare teller en toont het geresolvede vault-pad; (3) PyInstaller onefile → onedir (geen 76MB her-extractie + AV-rescan per start; cold start 4-8s). Commits 4cf26b6, 42ba5a5, 4009e19, 13930b4, 614d28d (warmth-404). E2e gevalideerd als geïnstalleerde standalone app met screenshots; UX door Robert bevestigd.
<!-- SECTION:FINAL_SUMMARY:END -->
