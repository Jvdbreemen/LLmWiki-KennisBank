# PRD: Vault-onderhoud & denkgereedschap-laag

**Project:** LLmWiki-KennisBank · **Doel-release:** v0.8 → v0.10 (gefaseerd) · **Eigenaar:** Jim · **Status:** draft

> **Gereconcilieerd tegen v0.7.0 (2026-06-21).** v0.6-v0.7 leverden al een swappable embedding-backend (`scripts/_embeddings.py`), een push-retrieval-hook (`scripts/kb-retrieve.py`) en een index-builder (`scripts/build-embed-index.py`). De retrieval-eisen hieronder bouwen daarop voort in plaats van iets nieuws. De lifecycle-skills `kennisbank-upgrade`/`kennisbank-contribute` raken alleen *tooling*, niet wiki-*inhoud*, dus de onderhoud-eisen (R1-R5) blijven ongebouwd.

## Problem Statement

De vault groeit alleen aan: `/wiki` voegt artikelen toe, `/stale` markeert verouderde, maar niets **herschrijft, verzoent of bevraagt** bestaande kennis. Daardoor stapelen dubbele en tegenstrijdige artikelen zich op, en blijft kennis passief liggen in plaats van het denken te ondersteunen. De concurrent (`obsidian-second-brain`) lost dit op met een zelf-herschrijvende vault, maar tegen de prijs van cloud-API's en Google-koppelingen die niet bij deze stack passen. Doel: dezelfde sprong maken, lokaal-first en met git als vangnet.

## Goals

1. `/wiki` **verbetert** bestaande artikelen waar dat kan, in plaats van standaard nieuw aan te maken (kwaliteit boven aantal).
2. Tegenstrijdigheden tussen artikelen worden **gedetecteerd en opgelost** met een natraceerbaar audit-spoor.
3. De vault wordt **bevraagbaar als denkpartner** (beslissing uitdagen, cross-domein bruggen), niet alleen als archief.
4. Vault-context wordt **gelaagd geladen** (L0-L3) zodat sessies minder tokens kosten en cozempic-hygiëne automatisch is.
5. Elke wijziging aan bestaande kennis is **omkeerbaar en reviewbaar** (git + diff-preview), nooit stilzwijgend destructief.

## Non-Goals

1. **Geen cloud-research-providers** (Grok, Perplexity, Gemini). Research blijft via de bestaande `/autoresearch`-skill en lokale Ollama. Reden: strijdig met lokaal-first en no-Google.
2. **Geen Obsidian-koppeling of plugin.** Markdown blijft de bron, Obsidian is gedemoot. Reden: portabiliteit.
3. **Geen real-time / watch-mode** auto-herschrijven tijdens sessies. Onderhoud draait op commando of geplande job. Reden: voorspelbaarheid, geen verrassende edits.
4. **Geen multi-platform adapters** (Codex, OpenCode). Claude Code blijft de enige doel-runtime in deze fase. Reden: focus.
5. **Geen volledig autonome verwijdering** van artikelen zonder menselijke bevestiging. Reden: confirm-before-destructive.

## User Stories

**Onderhoud (self-rewrite + reconciliation)**
- Als vault-eigenaar wil ik dat `/wiki` bij een nieuw sessielog eerst checkt of er een passend bestaand artikel is, zodat ik geen vierde variant van hetzelfde onderwerp krijg.
- Als vault-eigenaar wil ik een **diff zien** voordat een groot artikel wordt herschreven, zodat ik kan ingrijpen voor er kennis verdwijnt.
- Als vault-eigenaar wil ik dat kleine edits (typo, dode link, één sectie bijwerken) **automatisch** gebeuren, zodat ik niet voor elke triviale wijziging hoef te klikken.
- Als vault-eigenaar wil ik dat tegenstrijdige claims tussen twee artikelen worden gevlagd met **bron en datum**, zodat ik kan zien welke versie recenter of beter onderbouwd is.
- Als vault-eigenaar wil ik dat een opgeloste tegenstrijdigheid een **audit-regel** achterlaat (wat, waarom, wanneer), zodat ik later kan reconstrueren waarom de vault iets beweert.

**Denken (thinking-tools)**
- Als journalist/maker wil ik een beslissing of aanname kunnen **laten uitdagen tegen mijn eigen vault-historie**, zodat ik blinde vlekken zie voor ik iets publiceer.
- Als maker wil ik **bruggen tussen ongerelateerde onderwerpen** kunnen opvragen, zodat ik onverwachte invalshoeken vind.

**Context (L0-L3)**
- Als gebruiker wil ik dat een sessie standaard alleen mijn **identiteit + actieve staat** laadt (L0/L1) en pas dieper graaft op verzoek, zodat ik tokens spaar zonder relevante context te missen.

## Requirements

### P0 — Must-have (v0.6): veilig-bewerken-fundament + self-rewrite

**R1. Safe-edit engine (gedeelde primitive).** Eén Python-module die alle bestaande-artikel-mutaties afhandelt: leest huidig artikel, genereert voorgestelde nieuwe versie, classificeert de wijziging als *klein* of *groot*, en past de hybride-autonomieregel toe.
- *Given* een voorgestelde wijziging onder de drempel (config: bijv. < N gewijzigde regels, geen sectie/claim-verwijdering), *when* de engine draait, *then* wordt de edit direct toegepast en gelogd.
- *Given* een wijziging boven de drempel of met verwijdering, *when* de engine draait, *then* wordt een diff getoond en wacht de engine op expliciete bevestiging.
- *Given* een toegepaste edit, *when* ik achteraf kijk, *then* staat de wijziging als losse git-commit met een herkenbare message (`wiki-rewrite:` / `reconcile:`).
- Drempel is configureerbaar via env/config, in lijn met de bestaande tiling-thresholds.

**R2. Self-rewriting `/wiki`.** De compileerstap zoekt eerst een kandidaat-artikel (hergebruik de gedeelde `_embeddings.py`-backend en de embed-cache, net als `semantic-tiling.py` en `kb-retrieve.py`) voor er een nieuw wordt aangemaakt.
- *Given* een nieuw sessielog met onderwerp dat ≥ similarity-drempel matcht met een bestaand artikel, *when* `/wiki` draait, *then* stelt het een herschrijving van dat artikel voor via de safe-edit engine i.p.v. een nieuw bestand.
- *Given* geen match boven de drempel, *when* `/wiki` draait, *then* gedraagt het zich als nu (nieuw artikel).
- *Given* een herschrijving, *then* blijft de oorspronkelijke frontmatter-historie behouden (geen verlies van `created`, tags, backlinks).

**R3. Git-vangnet verplicht.** De engine weigert te draaien in een niet-git vault of met een vuile working tree, tenzij geforceerd.

### P1 — Should-have (v0.7): contradiction-reconciliation + eerste thinking-tool

**R4. Conflict-detectie.** Een script (`conflict-scan.py`, broertje van `stale-check.py`) dat paren artikelen met hoge semantische overlap maar tegenstrijdige claims vlagt.
- *Given* twee artikelen die elkaar tegenspreken op een feitelijke claim, *when* `/reconcile` draait, *then* verschijnt een rapport met beide claims, bron en datum.
- Detectie mag false positives geven; het rapport is een voorstel, geen automatische edit.

**R5. Reconciliation met audit-trail.** Oplossen van een gevlagd conflict via de safe-edit engine, met een audit-regel in het artikel of een centraal `reconciliation-log.md`.
- *Given* een bevestigde oplossing, *then* wordt de verliezende claim bijgewerkt/verwijderd én een audit-regel toegevoegd (datum, gekozen bron, reden).

**R6. `/uitdaag` (challenge-tool).** Neemt een stelling of beslissing, haalt relevante vault-artikelen op via de bestaande retrieval-laag (`kb-retrieve.py` / `_embeddings.py`) plus graphify, en confronteert de stelling met wat de vault al weet.
- *Given* een stelling, *when* `/uitdaag` draait, *then* komen er tegenargumenten/precedenten uit de eigen vault, met links naar bronartikelen.

### P2 — Future / architectuur-verzekering (v0.8)

**R7. `/brug` (cross-domein).** Vindt niet-voor-de-hand-liggende verbanden tussen twee ver uit elkaar liggende artikelen/clusters.

**R8. Progressive context-budgets L0-L3.** Gelaagd context-laadschema (L0 identiteit, L1 actieve staat/open loops, L2 relevante artikelen via `kb-retrieve.py`, L3 volledige bron), aangestuurd door een budget. Integreert met de cozempic-context-hygiëne in plaats van die te dupliceren.
- Ontwerpregel nu al respecteren: vault-briefing (`/sessiestart`) zo bouwen dat lagen later los aan/uit kunnen.

## Success Metrics

**Leading (dagen-weken)**
- Aandeel `/wiki`-runs dat een bestaand artikel verbetert in plaats van nieuw aanmaakt: streef **≥ 40%** binnen een maand gebruik (stretch 60%).
- Aantal near-duplicate-paren dat `semantic-tiling` rapporteert: **dalende trend** na invoer self-rewrite.
- Aantal door `/reconcile` opgeloste conflicten met audit-regel: meetbaar > 0, en **geen** stilzwijgend verloren claims (steekproef).

**Lagging (weken-maanden)**
- Vault groeit in **kwaliteit niet in aantal**: artikelaantal stabiliseert terwijl sessie-input doorloopt.
- Subjectieve recall-betrouwbaarheid: ik leun bij research vaker op de vault zonder te hoeven dubbelchecken (eigen logboek-oordeel, niet door Claude zelf te beoordelen).
- Tokens per sessie dalen meetbaar na L0-L3 (vergelijk cozempic-context-metingen voor/na).

## Open Questions

- **(engineering)** Drempel klein-vs-groot: regels-geteld, of semantisch (claim-verwijdering = altijd groot)? Blokkerend voor R1.
- **(data)** Hoe conflict-detectie betrouwbaar maken zonder vloed aan false positives? Niet-blokkerend; R4 mag ruw starten.
- **(product/Jim)** Moet self-rewrite ook tijdens `/sessielog` draaien, of alleen bij expliciete `/wiki`? Niet-blokkerend.
- **(engineering)** L0-L3 bovenop cozempic bouwen of ernaast? Moet voor R8, niet voor P0.
- **(product/Jim)** Verzelfstandigen tot publieke feature van de repo (issue-tracker, docs) of privé-only? Niet-blokkerend.

## Timeline / fasering

- **v0.8 (P0):** R1-R3. Het fundament. Levert al directe waarde (geen duplicaten meer).
- **v0.9 (P1):** R4-R6. Reconciliation + eerste denkgereedschap, hergebruikt de engine.
- **v0.10 (P2):** R7-R8. Brug-tool + gelaagde context.

Regel tegen scope-creep: elke nieuwe eis komt met een verwijdering of een release-verschuiving. R8 stuurt nu alleen ontwerpkeuzes, wordt pas in v0.8 gebouwd.
