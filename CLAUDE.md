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

## Lokaal, altijd

Niets gaat zonder expliciete toestemming naar de cloud. Lokale opslag (SQLite, markdown),
lokale embeddings (Ollama), lokale MCP (stdio). Zie de specs in `docs/superpowers/specs/`.
