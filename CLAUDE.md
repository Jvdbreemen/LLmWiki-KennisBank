# CLAUDE.md — KennisBank ontwikkelprincipes

Operationele installatie-instructies staan in `AGENTS.md`. Dit bestand legt vast
*hoe KennisBank moet aanvoelen* — leidend bij elke ontwerp- en codebeslissing in deze repo.

## Noord-ster: onzichtbaar, snel, uit de weg

KennisBank moet voelen alsof het er niet is. Het hoort de gebruiker te helpen met zijn
echte werk — redactie, coding, gewoon werk — zonder zelf aandacht op te eisen.

1. **Performance vóór alles.** Optimaal voor dagelijks gebruik. Zware verwerking gebeurt
   off de hot path (write-time, idle, scheduled). De interactieve weg (recall, prompts)
   blijft sub-seconde. Betaal vooraf, haal snel op.
2. **Kennis-retrieval staat voorop.** De kerntaak is: de juiste, actuele context op het
   juiste moment terugvinden en aanreiken. Alles daaromheen is ondersteunend.
3. **Automatiseren boven handwerk.** Wat handmatige discipline vereist, gebeurt in de
   praktijk niet. Borg kwaliteit autonoom; vraag de gebruiker alleen wat alleen hij kan
   beslissen.
4. **Feitelijke output, geen cruft.** Onderdruk gerust log-ruis. Geef in plaats daarvan
   heldere samenvattingen en status-updates, zodat de gebruiker wéét wat er gebeurt —
   zonder hem te bedelven. Geen ceremonie, geen filler.
5. **Niet twee keer dezelfde fout.** Het systeem onthoudt lessons learned en oude bugs,
   en helpt actief voorkomen dat ze terugkeren.
6. **Spontaan, maar hoog-precies, helpen.** "Hé, hier liep je twee maanden geleden ook
   tegenaan" — proactief surfacen mag, maar alleen boven een hoge relevantie-drempel.
   Onterechte onderbrekingen zijn precies de cruft die we vermijden.

## KISS

Bij elke keuze: simpel en uitlegbaar boven slim en opaak. Weeg opties kritisch, kies de
helderste aanpak, en houd performance + retrieval leidend. Liever één begrijpelijk
mechanisme dan drie clevere.

## Backlog.md — altijd taken vastleggen

Dit repo gebruikt Backlog.md (`backlog/`) als bron van waarheid voor werk. Regel:

- **Na elk plan, vóór uitvoer:** maak een Backlog-taak aan (titel, beschrijving,
  acceptatiecriteria, milestone, dependencies). Geen uitvoer zonder taak.
- **Bij starten:** zet de taak op `In Progress`.
- **Na afronden:** zet de taak door naar de volgende status en rond af (`Done`)
  zodra het werk gereviewd en groen is.

Gebruik de `mcp__backlog__*`-tools (of de `backlog` CLI). Houd taken klein genoeg
om los af te ronden.

## Pull requests — lees de review vóór je merget

GitHub Copilot plaatst automatisch een review op elke PR. Die review is onderdeel
van de workflow, geen bijvangst: **wacht erop en verwerk hem vóór de merge**, en
bij een release vóór de tag. Wachten kost minuten; een merge terugdraaien kost
meer.

De review-comments zitten niet in `gh pr view` — haal ze apart op:

```bash
gh api repos/<owner>/<repo>/pulls/<n>/comments \
  --jq '.[] | "=== \(.path):\(.line // .original_line) [\(.user.login)]\n\(.body)\n"'
```

Behandel elke opmerking als mogelijk terecht en toets hem aan de code of een
meting — verwerp niets op gevoel, en neem niets over zonder verificatie. Fix wat
klopt in een vervolgcommit op dezelfde branch. Laat je een opmerking bewust
liggen, zeg dan waarom.

**Groene CI is geen vervanging.** CI toetst gedrag; het toetst niet of een guard
dekt wat hij beweert te dekken. Op PR #54 (v0.20.0) was CI groen terwijl een
nieuwe ADR-0002-guard 23 ingesprongen codefences oversloeg doordat zijn regex op
kolom 0 verankerd stond. Drie andere opmerkingen wezen op docs en een comment die
nog een tabel noemden die een latere commit in diezelfde PR had verwijderd — het
klassieke "bijwerken per opsomming, en wat niet op de lijst staat blijft staan".

Releasevolgorde: suite groen → push → PR → review verwerken → merge → **`git fetch`
en vaststellen dat `origin/main` de commits echt bevat** → pas dan taggen op die
SHA → release publiceren. Nooit taggen op een branch-tip in de aanname dat de
merge geslaagd is.

## Vault-root: altijd via `vault_root()`, nooit hardcoded

Scripts bepalen de vault-root uitsluitend via `from _vaultpath import vault_root`
en dan `vault_root()`. Schrijf NOOIT een hardcoded default zoals
`Path.home() / "KennisBank"` of een letterlijk absoluut pad buiten `_vaultpath.py`.
De resolver eerbiedigt `KENNISBANK_VAULT` en houdt scripts portable over machines
en vault-namen (bv. `Kluis`). Dit is ADR-0002 (`docs/adr/0002-cross-platform-scripts.md`);
het gaat keer op keer fout wanneer een deploy-kopie de resolver vervangt door een
hardcoded pad, dus behandel elk hardcoded vault-pad als een regressie.

## Lokaal, altijd

Niets gaat zonder expliciete toestemming naar de cloud. Lokale opslag (SQLite, markdown),
lokale embeddings (Ollama), lokale MCP (stdio). Zie de specs in `docs/superpowers/specs/`.
