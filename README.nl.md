# LLmWiki-KennisBank

[English](README.md) · **Nederlands**

**Een soevereine geheugenlaag voor serieus AI-werk.**

Elke agent-sessie creëert waardevolle context: beslissingen, fixes, voorkeuren,
architectuur-afwegingen, doodlopende wegen, en lessen die je volgende week niet
opnieuw wilt ontdekken. Dan vergeet het model. KennisBank verandert die
tijdelijke context in een duurzaam lokaal kennissysteem voor Claude Code, Codex,
OpenCode, de GitHub Copilot CLI, en andere ontwikkelaars-agents.

Het legt vast wat er gebeurde, destilleert het tot een wiki met bronvermelding,
extraheert tijdsbewuste herinneringen, haalt de juiste kennis op vóór het
volgende antwoord, en meet of die kennis daadwerkelijk hielp. Het resultaat is
een AI-werkplek die na verloop van tijd scherper wordt zonder je privéwerk uit
handen te geven aan een gehoste geheugenleverancier.

Platte markdown. Lokale SQLite. Standaard lokale Ollama. Je eigen machine. Jij
blijft hoofdredacteur: het systeem stelt voor, plaatst in quarantaine, en
markeert, maar een mens voegt samen, vervangt, en beslist. Open de kluis in
Obsidian en het zijn gewoon notities. Zeer goed geordende notities die toevallig
een AI-geheugen aandrijven.

## Eersteklas integraties voor codeeragents

Eén `setup.sh`-flow installeert en upgradet KennisBank voor **Claude Code**,
**OpenAI Codex** en de standalone **GitHub Copilot CLI** op Windows, macOS en
Linux. OpenCode blijft ondersteund als extra lokale client.

- Skill- en promptbeschrijvingen zijn in het Engels, zodat elke client ze
  consistent kan ontdekken.
- Claude Code behoudt fail-open automatische hooks. Codex en Copilot
  installeren bewust geen KennisBank lifecycle-hooks, zodat hun clients geen
  `Running ... hook`- of `SessionStart hook (completed)`-regels tonen.
- Codex en Copilot gebruiken native persoonlijke skills plus MCP. Upgrades
  verwijderen alleen KennisBank-hooks en bewaren overige hooks.
- Dezelfde lokale stdio MCP-server en expliciet ingestelde
  `KENNISBANK_VAULT` bedienen alle geïnstalleerde clients.

Installeer of upgrade de drie eersteklas clients:

```bash
KENNISBANK_VAULT="/absoluut/pad/naar/kluis" bash setup.sh --yes --agents claude,codex,copilot
```

Gebruik na herstart `$sessiestart` en `$sessielog` in Codex, of
`/sessiestart` en `/sessielog` in Copilot.

Gebaseerd op [Andrej Karpathy's LLM Wiki-patroon](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): ruwe sessies gaan erin, gestructureerde kennis komt eruit. KennisBank breidt het patroon uit tot een gesloten lus:

```
capture ──> consolidate ──> retrieve ──> measure
   ^                                        │
   └────────────── learn <─────────────────┘
```

- **Capture**: sessie-logs, transcript-archivering, en een autonome geheugen-sweep die kandidaat-herinneringen extraheert, typeert, en beoordeelt na elke sessie.
- **Consolidate**: `/wiki` compileert sessies tot wiki-artikelen met herkomst per bewering; nieuwe feiten verzoenen zich met oude op schrijftijd (add, supersede, of drop) met een bi-temporeel geldigheidsmodel.
- **Retrieve**: hooks injecteren relevante wiki-artikelen en herinneringen in elke prompt, in elk project: hybride semantisch + trefwoord-zoeken, gerangschikt op relevantie x recentheid x belang, uitgebreid met de best-verbonden graaf-buur.
- **Measure**: een recall@k eval-harnas en een drempel-kalibratie-harnas maken elke retrieval-wijziging testbaar in plaats van op-gevoel.
- **Learn**: gebruikstelemetrie volgt welke geïnjecteerde kennis daadwerkelijk werd gebruikt, geeft warme documenten een boost en houdt recent gebruikte artikelen uit de stale-lijst.

## Waarom dit bestaat

Geheugensystemen van leveranciers (Mem0, Zep, Letta, Cognee) zijn krachtig maar cloud-gevormd: jouw kennis leeft in hun opslag, achter hun API, op hun prijsniveau. KennisBank neemt de twee mechanismen die er echt toe doen uit die literatuur - temporele geldigheid van feiten en invalidatie-op-schrijven - en herbouwt ze in platte markdown-frontmatter plus SQLite. Wat jij bezit blijft portable; wat de agent nodig heeft blijft snel.

De ontwerpvoorkeur is overal dezelfde: **deterministisch waar mogelijk, LLM alleen waar het oordeelsvermogen toevoegt, fail-open overal**. Een dood model blokkeert nooit een sessie, verliest nooit een transcript, en verwijdert nooit geverifieerde kennis.

## Functie-highlights (v0.16.2)

### Nieuw in v0.16.2

- **Geen hookregels in Codex en Copilot.** Hun KennisBank-integraties zijn
  hookloos en gebruiken native commandskills plus MCP.
- **Native sessieworkflows.** Copilot biedt `/sessiestart` en `/sessielog`;
  Codex biedt `$sessiestart` en `$sessielog` plus `/prompts:*`-compatibiliteit.

### Nieuw in v0.15
- **Meertalige temporele recall.** `/watdeedik`, `/timeline`, en `/weeklog`
  begrijpen nu kant-en-klaar data en periodes in **Nederlands, Engels, Duits,
  Frans, Spaans, en Italiaans** (`vorige week`, `letzte Woche`,
  `la semaine dernière`, `la semana pasada`, `begin april`, `vor zwei Wochen`),
  met exacte kalenderbereiken. Een optionele `dateparser`-fallback breidt de
  dekking uit naar 200+ talen, en een standaard-uitgeschakeld lokaal-LLM-laatste
  redmiddel handelt samengestelde formuleringen af zoals "het weekend voor
  afgelopen maandag".
- **Rijkere relatieve formuleringen.** Relatieve weekdagen, weekdelen
  (`begin/midden/eind vorige week`), weekenden, "N eenheden geleden" in beide
  woordvolgorden, en maandnamen met jaar-inferentie worden allemaal
  deterministisch opgelost. 138 vastgepinde testcases bewaken het gedrag.

### Nieuw in v0.14
- **Lokale LiteParse-documentintake.** `/intake` en `/import documents <path>`
  parsen PDF's, Office-bestanden, spreadsheets, presentaties, en documentachtige
  afbeeldingen tot citeerbare markdown onder `<vault>/05-bronnen/liteparse/`.
- **Bronmateriaal blijft gescheiden.** Geparste binaire documenten worden
  `type: bron`-markdown met frontmatter die terugwijst naar het oorspronkelijke
  lokale bestand, zodat wiki-artikelen ze kunnen citeren met expliciete
  `[[05-bronnen/...]]`-links in plaats van te doen alsof het sessie-logs waren.
- **OCR is expliciet.** Documenten met native tekst parsen standaard zonder OCR;
  gebruik `--ocr` alleen voor scans en alleen wanneer lokale Tesseract/tessdata
  beschikbaar is.

### Nieuw in v0.13
- **Temporele activiteit-recall.** Vraag wat er gebeurde op een datum, tijdens
  een week, of rond een onderwerp met `/watdeedik`, `/timeline`, en `/weeklog`.
  De functie bouwt een lokale `<vault>/.claude/kb-activity.db` op uit ruwe
  sessies, transcripts, herinneringen, wiki-updates, en gebruikstelemetrie.
- **Strikte tijdsbewuste retrieval.** Data en periodes worden deterministisch
  geparst in het Nederlands en Engels (`vorige week`, `2026-07-03`, `3 juli 2026`,
  `between 2026-07-01 and 2026-07-07`). Bereikfiltering is hard: gebeurtenissen
  buiten de gevraagde periode worden er niet stilletjes doorheen gemengd.
- **Onderwerptijdlijnen met bewijs.** Volg onderwerpen zoals "Codex MCP" of
  "OpenRouter" door de tijd heen met behulp van entiteiten, tags, aliassen, FTS
  en bronverwijzingen. Lokale aliassen kunnen worden geconfigureerd in
  `<vault>/.claude/activity-topic-aliases.json`.
- **MCP temporele tools.** De lokale `kennisbank` MCP-server stelt nu
  `what_did_i_do`, `timeline`, `weeklog`, en `topic_timeline` beschikbaar naast
  `recall` en `capture`, zodat Codex, OpenCode en andere lokale agents dezelfde
  API gebruiken als de slash-commando's.
- **Gemeten recall.** `kb-activity-eval.py` biedt een temporeel eval-harnas voor
  datumrecall, perioderecall, onderwerptijdlijnen, negatieve controles en
  herkomstdekking. De repo levert een niet-persoonlijke voorbeeld-evalset mee.

### Nieuw in v0.12
- **Eén setup voor installatie en upgrade.** `setup.sh` is nu het gezaghebbende
  pad voor eerste installatie, reparatie, en upgrade: het ververst tooling,
  behoudt gebruikersdata, voert migraties uit, installeert geselecteerde
  agent-integraties, en blokkeert voltooiing wanneer validatie faalt.
- **Multi-agent van opzet.** Kies `claude`, `codex`, `opencode`, of `all`.
  Claude Code krijgt native commando's en hooks; Codex krijgt gedeelde skills,
  `/prompts:*`-aliassen, hooks, MCP, en `AGENTS.md`; OpenCode krijgt commando's,
  gedeelde skills, MCP, globale regels, en een lokale plugin.
- **Geverifieerde local-first modellen.** Setup valideert de geselecteerde
  backend voordat het terugkeert. Ollama blijft de standaard voor lokale
  geheugen-extractie en -beoordeling, inclusief smoke-tests voor de
  geconfigureerde embedding- en chatmodellen.
- **OpenRouter als expliciete cloud-opt-in.** Als je een externe LLM wilt voor de
  beoordelings-/extractiestap, kan setup OpenRouter configureren met een
  model-slug en API-sleutel-omgevingsvariabele. Secrets worden nooit
  weggeschreven naar de repo of kluis.
- **Agent-vriendelijk operationeel contract.** `AGENTS.md`, `CONFIGURATION.md`, en
  de agent-integratiedocumentatie beschrijven nu het actieve kluispad,
  setup-validatie, Codex/OpenCode-gedrag, hooks, MCP, en privacygrenzen.
- **v0.12.1 Codex-hotfix.** Setup opnieuw draaien repareert nu het Codex MCP
  TOML-blok zonder `[mcp_servers.kennisbank.env]` te dupliceren, en validatie
  vangt misvormde Codex-TOML op voordat setup succes meldt.
- **v0.12.2 MCP-runtime-hotfix.** Setup installeert nu de Python MCP SDK voor
  Codex/OpenCode-targets en valideert de stdio-server met een echte
  initialize/list-tools-handshake, zodat een geconfigureerde `kennisbank`
  MCP-server niet langer pas faalt wanneer de agent start.

### Kennis (de wiki-laag)
- `/wiki` compileert ruwe sessie-logs tot onderling gelinkte wiki-artikelen, en werkt bestaande artikelen bij via een bewaakte herschrijf-engine (`safe-edit.py`) in plaats van ze te overschrijven.
- **Provenance-lint** (`kb-lint.py`): elk artikel moet herleidbaar zijn naar zijn bronnen via oplosbare wikilinks naar een ruwe sessie of een geïmporteerde bron; `/wiki` schrijft die herkomst per kernpunt weg op destillatietijd. Een hallucinatie tijdens destillatie kan niet langer een permanent "feit" worden dat niemand kan controleren.
- `/stale` vindt verouderde artikelen, en gebruikstelemetrie houdt warme artikelen uit de lijst: een artikel dat je vorige week gebruikte is niet stale, hoe oud de `updated`-datum ook is.
- Denkgereedschap: `/reconcile` brengt tegenstrijdigheden tussen artikelen naar boven, `/uitdaag` daagt een stelling adversarieel uit, `/brug` vindt conceptuele bruggen tussen twee onderwerpen.

### Geheugen (de agent-laag)
- Een autonome **capture-sweep** draait losgekoppeld op de achtergrond (gestart bij sessiestart, over transcripts die bij sessie-einde zijn gearchiveerd): kandidaten extraheren, ze typeren (`feit`, `voorkeur`, `procedure`, `beslissing`), dedupliceren, en een onafhankelijke beoordelaar laten beslissen tussen `current` en quarantaine (`unverified`) met een belangscore (1-5).
- **Bi-temporele geldigheid**: elke herinnering draagt `valid_from` (gebeurtenistijd, van de sessiedatum) los van `created` (vastlegtijd); het vervangen of laten verlopen van een feit stempelt `valid_until`. Het systeem weet niet alleen wat waar is, maar ook sinds wanneer en tot wanneer.
- **Invalidatie op schrijftijd** (Mem0-patroon, lokaal): een nieuw feit verzoent zich met de meest gelijkende bestaande herinneringen op schrijftijd: ADD, SUPERSEDE (het oude feit wordt afgesloten en gelinkt), of NOOP. Een deterministische temporele bewaker zorgt dat een ouder feit nooit een nieuwer feit kan invalideren, zodat bulk-herimports veilig zijn.
- Onderhoud over herinneringen heen: supersede-pass, ruis-hercontrole, en clusterpromotie (terugkerende thema's worden gemarkeerd als wiki-kandidaten).

### Retrieval (de hooks-laag)
- **Elke prompt, elk project**: een UserPromptSubmit-hook embedt je prompt en injecteert de best-matchende wiki-artikelen en herinneringen als context. Een PreToolUse-hook controleert de kluis voordat Claude het web doorzoekt.
- Hybride index (`kb-index.db`): semantische vectoren (sqlite-vec) gefuseerd met FTS5-trefwoordzoeken, zodat exacte termen worden gevonden zelfs wanneer embeddings ze missen.
- Rangschikking: relevantie x recentheid (halveringstijd per geheugentype) x belang, plus een gebruiksboost voor documenten die recent nuttig bleken.
- **Graaf-buur-uitbreiding**: de meest-gerefereerde wikilink-buur van je treffers lift mee als één extra vermelding, wat losse treffers omzet in een samenhangende kennisbuurt.

### Meting (de vertrouwenslaag)
- `kb-eval.py`: recall@1/3/5 en MRR tegen je persoonlijke evalset van vragen. Draai het vóór en na elke retrieval-wijziging; een daling is een regressie, geen mening.
- `kb-activity-eval.py`: temporele recall-evals voor datumvragen, periodevragen, onderwerptijdlijnen, negatieve controles en bronverwijzingsdekking.
- `kb-calibrate.py`: controleert alle cosinus-drempels (dedup, rewrite, reconcile, conflict, retrieve) tegen het actieve embedding-model met behulp van een handmatig gelabelde paren-set, en stelt grenzen voor met scheidingsmarges. Het schrijft niets weg: jij beslist. Wissel van embedding-model zonder stilletjes te degraderen.
- `doctor.sh`: één commando verifieert de hele installatie, van kluisindeling en hook-registratie tot herkomstdekking.

### Soevereiniteit (waar het om draait)
- Lokale Ollama-modellen voor zowel embeddings als beoordeling, verwisselbaar via config (`kennisbank-embed.json`, `kennisbank-llm.json`); OpenAI-compatibele endpoints ondersteund wanneer je daarvoor kiest.
- LiteParse 2.x voor lokaal parsen van PDF-/Office-/afbeeldingsdocumenten tijdens intake.
- Alles is markdown + SQLite in een map die jij bezit. Obsidian-compatibel. MIT-gelicentieerd.
- Menselijke updateautoriteit: agents verwijderen nooit stilletjes; vervangen kennis wordt afgesloten en gelinkt, in quarantaine geplaatste kennis kan geverifieerde kennis niet verdringen, en grote herschrijvingen vereisen jouw bevestiging.

## Vereisten

- Minimaal één lokale agent-client: [Claude Code](https://claude.ai/code), Codex, OpenCode, of de [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)
- Python 3.10+
- [Ollama](https://ollama.com) met:
  - `qwen3-embedding:8b` (embeddings; meertalige standaard. Kluizen met alleen Engels kunnen het lichtere `nomic-embed-text` gebruiken)
  - een chatmodel voor de geheugenbeoordeling/-extractie (standaard `gemma4:latest`; pin een ander via `<vault>/.claude/kennisbank-llm.json`)

Ollama is optioneel in de zin dat alles fail-open werkt zonder, maar de geheugen-sweep, semantische retrieval, en deduplicatie zijn het hart van het systeem: installeer het. Alleen voor de **LLM-beoordeling/-extractie** kan setup ook OpenRouter configureren als expliciete cloud-opt-in. Embeddings blijven standaard lokaal.

De setup maakt standaard twee hoofdmappen aan:
- `~/KennisBank/` - de kluis (wiki, logs, geheugen, templates, scripts)
- `~/Claude/research/` - uitvoermap voor `/autoresearch`

Beide paden zijn configureerbaar. Voor een niet-standaard kluis stel je `KENNISBANK_VAULT` in bij het draaien van setup; diezelfde waarde wordt in agent-hooks en MCP-config geschreven zodat clients niet terugvallen op `~/KennisBank`.

## Installatie

```bash
git clone https://github.com/Jvdbreemen/LLmWiki-KennisBank.git
cd LLmWiki-KennisBank
bash setup.sh           # interactive
bash setup.sh --yes     # non-interactive (recommended for AI agents)
KENNISBANK_VAULT="/absolute/path/to/vault" bash setup.sh --yes --agents claude,codex,opencode
```

In één idempotente run doet het setup-script:
- maakt de kluis-mappenstructuur aan onder `$KENNISBANK_VAULT` of `~/KennisBank/`
- kopieert scripts en templates op hun plaats
- initialiseert de settings-toggles en voert versie-gebonden migraties uit
- vraagt welke agent-omgevingen geïnstalleerd moeten worden (`claude`, `codex`, `opencode`, of `all`; standaard `claude,codex`)
- installeert Claude Code-commando's/skills/hooks wanneer `claude` is geselecteerd
- installeert Codex-commandskills, `/prompts:*`-compatibiliteitsaliassen,
  MCP-config en globale `AGENTS.md`; upgrades verwijderen oude KennisBank-hooks
- installeert OpenCode-commando's, gedeelde skills, MCP-config, globale `AGENTS.md`, en een lokale plugin-hook wanneer `opencode` is geselecteerd
- installeert Copilot-commandskills, MCP-config, persoonlijke instructies en
  een agentprofiel; upgrades verwijderen oude KennisBank-hooks
- vraagt om de LLM-backend in interactieve modus: standaard `ollama`, optioneel `openrouter` met model-slug en API-sleutel-omgevingsvariabele
- valideert de installatie voordat het terugkeert: `doctor.sh`, agent-config-controles, MCP-runtime-handshake voor Codex/OpenCode, lokale Ollama-smoke-tests, en OpenRouter-smoke-tests wanneer OpenRouter is geselecteerd

**`setup.sh` opnieuw draaien is veilig en is het upgrade-mechanisme**: het ververst tooling en repareert agent-config zonder gebruikersdata, aanpassingen, of kluisinhoud te overschrijven. De `/kennisbank-upgrade`-skill omhult het met release-tag-checkout, drift-detectie, back-ups, versie-stempeling, en dezelfde post-installatie-validatie.

Nuttige vlaggen:

```bash
bash setup.sh --yes --agents claude,codex      # default non-interactive target set
bash setup.sh --yes --agents all               # Claude Code + Codex + OpenCode + Copilot
bash setup.sh --yes --agents codex             # Codex only
bash setup.sh --yes --skip-model-check         # CI/offline validation without Ollama smoke tests
```

Voor OpenRouter schrijft setup alleen niet-geheime config naar
`<vault>/.claude/kennisbank-llm.json`: provider, model, endpoint, en
`api_key_env`. De API-sleutel zelf moet in de genoemde omgevingsvariabele staan
of, als je hem tijdens setup invoert, in het gebruikers-lokale secrets-bestand
`~/.config/kennisbank/secrets.json`. Hij wordt nooit weggeschreven naar de repo
of kluis.

Lees na installatie [POST-INSTALL.md](POST-INSTALL.md) voor de eerste-sessie-walkthrough.

### De hookset

Claude Code ontvangt de hookset hieronder in `~/.claude/settings.json`. Codex en
Copilot krijgen bewust geen KennisBank lifecycle-hooks; native skills en MCP
voorkomen client-gegenereerde voortgangs- en voltooiingsregels.

| Hook | Script | Wat het doet |
|------|--------|--------------|
| SessionStart | `build-embed-index.py` | Warm de wiki-embedding-cache op (incrementeel) |
| SessionStart | `build-kb-index.py` | Ververs de hybride vector+FTS-index |
| SessionStart | `build-activity-index.py` | Ververs de temporele activiteit-index voor `/weeklog`, `/timeline`, en MCP temporele tools |
| SessionStart | `sweep-launch.py` | Start de losgekoppelde geheugen-capture-sweep |
| SessionStart | `memory-notify.py` | Rapporteer de gezondheid van de geheugen-quarantaine |
| SessionStart | `distill-notify.py` | Rapporteer transcripts die wachten op destillatie |
| UserPromptSubmit | `kb-retrieve.py` | Injecteer matchende wiki- + geheugencontext in de prompt |
| SessionEnd | `archive-transcript.py` | Archiveer het sessie-transcript in de kluis |
| SessionEnd | `kb-usage-scan.py` | Markeer welke geïnjecteerde kennis daadwerkelijk werd gebruikt |
| PreToolUse (WebSearch\|WebFetch) | `kb-presearch.py` | Raadpleeg de kluis voordat je het web doorzoekt |

De hooks zijn fail-open van opzet: een fout betekent geen geïnjecteerde context of een overgeslagen achtergrondstap, nooit een geblokkeerde sessie.

## Commando-overzicht

| Commando | Argumenten | Wat het doet |
|---------|-----------|--------------|
| `/sessielog` | geen | Schrijft sessie-log, compileert wiki-kandidaten, draait semantische tiling |
| `/sessiestart` | geen | Leest kluiscontext, geheugen, wiki-status, stelt volgende acties voor |
| `/wiki` | optioneel onderwerp | Compileert ruwe logs (laatste 7 dagen) tot wiki-artikelen met herkomst per kernpunt, gevalideerd door kb-lint |
| `/intake` | geen | Verwerkt bestanden in `~/KennisBank/00-inbox/`, inclusief lokale LiteParse-conversie van PDF-/Office-/afbeeldingsdocumenten naar bron-markdown |
| `/stale` | geen | Detecteert artikelen ouder dan 60 dagen, en slaat recent gebruikte over |
| `/import` | `cc` \| `claudeai <path>` \| `folder <path> [prefix]` \| `documents <path> [prefix]` \| `cowork` \| `all` | Bulk-import van oude sessies uit Claude Code-geschiedenis, een claude.ai-exportbundel, een willekeurige markdown-map, documentbronnen via LiteParse, of Mac desktop Claude-data; `all` draait elke gedetecteerde bron, geen argument vraagt interactief |
| `/destilleer` | geen | Importeert gearchiveerde CC-transcripts en compileert ze tot de wiki |
| `/autoresearch` | onderwerp | Multi-ronde webresearch via de autoresearch-skill (geen commandobestand), slaat op in `~/Claude/research/` |
| `/reconcile` | optioneel onderwerp | Brengt tegenstrijdigheden tussen wiki-artikelen naar boven en produceert een reconciliatie-log |
| `/uitdaag` | stelling of beslissing | Daagt een stelling adversarieel uit op zwakke redenering of ontbrekend bewijs |
| `/brug` | twee onderwerpen | Vindt conceptuele bruggen en gedeelde principes tussen twee onderwerpen |
| `/weeklog` | optionele periode/onderwerp | Wekelijkse activiteitensamenvatting met beslissingen, releases/taken, open eindjes en bronverwijzingen |
| `/timeline` | datum/periode/onderwerp | Chronologische temporele activiteitentijdlijn met strikte bereikfiltering |
| `/watdeedik` | datum/periode/onderwerp | Compact antwoord op "wat deed ik toen?" met bewijslinks |
| `/kennisbank:settings` | geen | Toont en schakelt de achtergrond-automatiek-toggles |
| `/kennisbank:rebuild-index` | geen | Herbouwt de hybride zoekindex uit de kluis-markdown |
| `/kennisbank:rebuild-memory` | geen | Her-extraheert ALLE geheugen uit gearchiveerde transcripts (zwaar; semantische dedup maakt het bijna-idempotent) |
| `/kennisbank-upgrade` | optioneel `--dry-run` | Upgradet de gedeployde kluis naar de nieuwste release-tag |
| `/kennisbank-contribute` | optioneel `--dry-run` | PR't lokale tooling-wijzigingen terug upstream |

## Skills

Drie skills worden met het systeem meegeleverd. Claude Code krijgt ze onder `~/.claude/skills/`; Codex en OpenCode krijgen ze onder de gedeelde gebruikers-skill-locatie `~/.agents/skills/`, die beide clients ontdekken. Commando's zijn enkele prompts; skills zijn meerstaps-procedures met hun eigen guardrails.

| Skill | Aangeroepen via | Wat het doet |
|-------|-------------|--------------|
| `autoresearch` | `/autoresearch <topic>` of "research/deep dive/onderzoek [topic]" | Autonome iteratieve research-loop: multi-ronde webzoekopdrachten, synthese, en één gestructureerd document met bronvermelding in `~/Claude/research/`. Controleert eerst je eigen kluis (luie hiërarchie) zodat research gaten vult in plaats van te herhalen wat je al weet. Gebouwd op Karpathy's autoresearch-patroon. |
| `kennisbank-upgrade` | `/kennisbank-upgrade [--dry-run]` | Upgradet een gedeployde kluis naar de nieuwste officiële release-tag (nooit kale main): haalt tags op, toont de changelog-delta, detecteert lokale drift met een CRLF-agnostische diff, maakt back-ups van gedrifte categorieën, deployt via `setup.sh`, stempelt de geïnstalleerde versie, en verifieert met `doctor.sh`. |
| `kennisbank-contribute` | `/kennisbank-contribute [--dry-run]` | De omgekeerde richting: isoleert lokale tooling-wijzigingen in een gedeployde kluis (scripts, templates, commando's, skills), filtert persoonlijke kluisinhoud eruit, en maakt dan een branch, commit, push, en opent een upstream-PR. Eigenaarschap staat gelijk aan duurzaamheid: verbeteringen overleven de volgende upgrade omdat ze upstream terechtkomen. |

Upgrade en contribute zijn twee helften van één lus: `contribute` stuurt je lokale verbeteringen upstream, `upgrade` brengt uitgebrachte verbeteringen weer terug. Een kluis die beide volgt, drift nooit permanent weg van het project.

## Kluisstructuur

```
~/KennisBank/
  00-inbox/        Drop files here for processing
  01-raw/
    sessies/       Session logs (raw-sessie-YYYY-MM-DD-topic.md)
    transcripts/   Archived Claude Code transcripts (SessionEnd hook)
  02-wiki/         Compiled wiki articles
  03-projecten/    Project-specific notes
  04-templates/    Article and log templates
  05-bronnen/      Source materials and references
  06-claude/       Claude-internal context files, eval + calibration sets
  07-media/        Media descriptions and asset metadata (not the binaries)
  08-archive/      Archived articles
  09-memory/       Agent memory (typed, judged, bi-temporal; archive/ for retired items)
  .claude/
    scripts/       Python + shell tooling (incl. doctor.sh)
    kb-index.db    Hybrid vector + FTS index (refreshed incrementally each session)
    kb-usage.db    Usage telemetry (survives rebuilds and model switches)
  graphify-out/    Knowledge graph output (optional)
```

## Achtergrond-automatiek-toggles

Zeven achtergrondgedragingen zijn individuele toggles in `kennisbank-settings.json`, beheerd met `/kennisbank:settings`:

| Toggle | Standaard | Regelt |
|--------|---------|----------|
| `auto_archive` | uit | Archiveer het transcript bij sessie-einde |
| `distill_notify` | aan | Meld bij start dat transcripts in behandeling zijn |
| `embed_index` | aan | Ververs de wiki-embedding-cache bij start |
| `daily_graphify` | aan | Werk de kennisgraaf eens per dag bij |
| `memory_capture` | aan | Extraheer en beoordeel herinneringen naar `09-memory/` |
| `memory_recall` | aan | Injecteer herinneringen in context via hooks |
| `usage_telemetry` | aan | Volg welke geïnjecteerde kennis wordt gebruikt |

## Je retrieval meten

Twee harnassen houden het systeem eerlijk:

```bash
# recall@k against your personal eval set (06-claude/kb-eval-set.json)
python3 ~/KennisBank/.claude/scripts/kb-eval.py

# threshold calibration against the active embedding model
python3 ~/KennisBank/.claude/scripts/kb-calibrate.py
```

Onderhoud de evalset naarmate je kluis groeit (vragen waarvan je het antwoord kent, met het verwachte artikel), en draai beide harnassen na elke wijziging aan drempels, modellen, of rangschikking. Voorbeeldsets worden meegeleverd in de repo-root.

## Migreren vanaf oudere Claude-tooling

Het `/import`-commando vult de kluis aan vanuit bestaande Claude-geschiedenis. Het verwerkt Claude Code-sessie-JSONL-bestanden onder `~/.claude/projects/`, claude.ai-exportbundels, Mac desktop Claude (Cowork)-gespreksdata, en elke generieke markdown- of tekstmap. Elke importer schrijft ruwe sessiebestanden die `/wiki` daarna kan compileren. Voor de geheugenlaag her-extraheert `/kennisbank:rebuild-memory` alle gearchiveerde transcripts via de volledige sweep (semantische dedup maakt herruns bijna-idempotent).

Voor binaire/bron-documenten gebruiken `/intake` en `/import documents <path>`
LiteParse 2.x lokaal om PDF's, Office-bestanden, spreadsheets, presentaties,
en documentachtige afbeeldingen om te zetten naar markdown onder
`05-bronnen/liteparse/`. Dit roept geen cloud-parser of LLM aan. OCR is opt-in
(`--ocr`) zodat PDF's met native tekst niet vervuild raken door diagnostiek over
ontbrekende Tesseract/tessdata; Office-/afbeeldingsformaten kunnen nog steeds
lokale LibreOffice-/ImageMagick-tooling vereisen, zoals LiteParse rapporteert.

## KennisBank gebruiken vanuit andere agents (Codex, OpenCode, Copilot, ChatGPT)

De kluis is niet alleen voor Claude Code. `scripts/kb-mcp.py` is een lokale **MCP-server** die drie primitieven blootstelt - `recall` (zoek geheugen + wiki), `capture` (sla een nieuwe herinnering op), en een `instructions`-resource (een duwtje om te trekken vóór je extern zoekt). MCP is het ene protocol dat elke moderne agent al spreekt, dus elke client die **op deze machine** draait kan de kluis gebruiken.

**De harde grens: alleen lokaal.** De MCP-server bindt niets aan het netwerk
(stdio-transport); de kluis verlaat nooit je machine. Claude Code, Codex,
GitHub Copilot CLI, OpenCode en compatibele lokale stdio-clients bereiken hem
direct. Agents die *in de cloud* draaien (gehoste ChatGPT) kunnen geen lokale
stdio-server bereiken, en het antwoord is **niet** om je soevereine kluis naar
het internet te tunnelen - het is de handmatige brug hieronder.

### Codex CLI

`setup.sh --agents codex` installeert:

- `~/.agents/skills/<commando>/SKILL.md`, inclusief `sessiestart`, `sessielog`
  en de handgeschreven KennisBank-skills
- `~/.codex/prompts/*.md`-aliassen, aangeroepen als `/prompts:sessielog`, `/prompts:sessiestart`, `/prompts:kennisbank-upgrade`, enz.
- `~/.codex/AGENTS.md` met het actieve kluispad
- `~/.codex/config.toml` MCP-server `kennisbank`

Gebruik `$sessiestart` en `$sessielog` als native Codex-skills. De verouderde
promptcompatibiliteit is `/prompts:<name>`. KennisBank installeert geen Codex
lifecycle-hooks omdat `suppressOutput` nog niet wordt uitgevoerd. Setup bewaart
overige hooks; MCP blijft beschikbaar.

Handmatig MCP-equivalent:

```bash
py -3 -m pip install mcp==1.28.1
```


```toml
[mcp_servers.kennisbank]
command = "py"
args = ["-3", "/absolute/path/to/vault/.claude/scripts/kb-mcp.py"]

[mcp_servers.kennisbank.env]
KENNISBANK_VAULT = "/absolute/path/to/vault"
KB_LLM_PROVIDERS = "ollama"
KB_LLM_MODEL = "gemma4:12b"
KB_LLM_ENDPOINT = "http://localhost:11434"
```

### OpenCode

`setup.sh --agents opencode` installeert:

- `~/.config/opencode/commands/*.md`, aangeroepen als `/sessielog`, `/sessiestart`, `/kennisbank-upgrade`, enz.
- `~/.agents/skills/{autoresearch,kennisbank-upgrade,kennisbank-contribute}/`
- `~/.config/opencode/AGENTS.md` met het actieve kluispad
- `~/.config/opencode/opencode.json` MCP-server `kennisbank`
- `~/.config/opencode/plugins/kennisbank.js`, een fail-open lokale plugin voor sessie-onderhoudsevents

OpenCode leest globale commando's rechtstreeks uit `~/.config/opencode/commands/`, dus de commandonamen komen overeen met de Claude Code-namen. Retrieval moet de MCP-tool `recall` en de geïnstalleerde skills gebruiken; de plugin handelt achtergrondonderhoud af waar OpenCode overeenkomende events blootstelt.

### GitHub Copilot CLI - een eersteklas lokale agent

De **standalone** GitHub Copilot CLI (`npm install -g @github/copilot`, aangeroepen als `copilot`) is een beheerde KennisBank-target, precies zoals Codex en OpenCode - geen handgeschreven snippet. Eén lokale kluis, één stdio MCP-server, één lokale recall-laag, nu gedeeld over alle vier de agents. Wat je ook doet in een Copilot-sessie wordt doorzoekbare KennisBank-geschiedenis naast je Claude Code-, Codex-, en OpenCode-werk; vraag `/watdeedik` of `/timeline` en Copilots sessies verschijnen naast de rest.

```bash
KENNISBANK_VAULT="/absolute/path/to/vault" bash setup.sh --yes --agents copilot
```

`setup.sh --agents copilot` installeert, idempotent en zonder login:

- `~/.copilot/mcp-config.json` - MCP-server `kennisbank` (`recall`, `capture`, en de temporele tools), geregistreerd via een key-scoped JSON-merge en gevalideerd met een echte initialize/list-tools-handshake
- `~/.copilot/copilot-instructions.md` - een door KennisBank beheerd instructieblok
- `~/.copilot/agents/kennisbank.agent.md` - een aangepast agent-profiel, geselecteerd met `copilot --agent kennisbank`
- native slash-commandskills onder `~/.agents/skills/`, inclusief
  `/sessiestart` en `/sessielog`

KennisBank installeert geen Copilot lifecycle-hooks, omdat Copilot geen
hookveld biedt om zijn eigen tijdlijnregels te verbergen.

Draai Copilot via de wrapper om de kluis en local-LLM-env vast te pinnen: `python3 <vault>/.claude/scripts/kennisbank-copilot.py` (een triviale exec die het overdraagt aan de echte `copilot`; `--kb-doctor`, `--kb-dry-run`, en `--kb-print-env` werken zonder GitHub-login).

**De cloud-grens is precies.** Copilot is cloud-gebaseerd - een live model-beurt vereist een GitHub Copilot-abonnement en stuurt verzoeken naar GitHub. Maar dat is het *enige* dat je machine verlaat: je kluis, je recall, de MCP-server, en elke hook blijven 100% lokaal, en MCP-/hook-/instructie-installatie plus `copilot mcp list` werken allemaal **zonder** in te loggen. De integratie is opt-in en zit nooit in de standaard target-set. Volledige referentie in [docs/agent-integrations.md](docs/agent-integrations.md), ontwerp-rationale in [docs/adr/0003-copilot-cli-integration.md](docs/adr/0003-copilot-cli-integration.md), en waarom de wrapper geen Headroom-achtige proxy is in [docs/copilot-headroom-evaluation.md](docs/copilot-headroom-evaluation.md).

### GitHub Copilot (VS Code agent-modus) - werkt, met één kanttekening

Dit is Copilots **VS Code agent-modus** (MCP-tools binnen de editor) - een andere, handmatige integratie dan de standalone GitHub Copilot CLI die hierboven behandeld is. Copilots agent-modus ondersteunt MCP-**tools** over stdio, maar **geen** MCP-resources of -prompts. Dus `recall` en `capture` werken, maar het `instructions`-duwtje (een resource) komt niet naar boven. Zet het duwtje in plaats daarvan in `.github/copilot-instructions.md`:

```markdown
You have a local KennisBank via MCP tools `recall` and `capture`.
Call `recall` before searching externally; call `capture` to save a reusable fact.
```

Registreer de server in de VS Code-instellingen (`mcp.json` / `"servers"`):

```json
{
  "servers": {
    "kennisbank": {
      "command": "python3",
      "args": ["/absolute/path/to/vault/.claude/scripts/kb-mcp.py"]
    }
  }
}
```

Het bredere adapter-register en de rest van de client-snippets staan in
[docs/agent-integrations.md](docs/agent-integrations.md).

### ChatGPT - de handmatige brug (soevereiniteit eerst)

Gehoste ChatGPT kan alleen verbinden met **remote** MCP-servers op het publieke internet; een lokale server blootstellen betekent tunnelen (Secure Tunnel / ngrok / Cloudflare), wat je queries **en** de teruggegeven kennis via OpenAI's infrastructuur leidt. Dat breekt het hele punt van een soevereine kluis, dus KennisBank doet dit standaard niet. In plaats daarvan blijf **jij** de poort:

```bash
python3 .claude/scripts/kb-ask.py "how did I fix the ESP32 BLE crash"
python3 .claude/scripts/kb-ask.py "my topic" --k 8 --clip   # also copy to clipboard
```

`kb-ask` haalt lokaal op en print een kant-en-klaar te plakken contextblok (een korte instructie voor het model, dan de treffers, dan je vraag). Plak het bovenaan je ChatGPT-bericht. Niets verlaat de machine automatisch - jij kiest wat je deelt.

### ChatGPT-data-export - krijg de controle over je eigen chats terug

Je kunt je ChatGPT-geschiedenis *in* de soevereine kluis trekken, zodat lessen uit die gesprekken je eigen ophaalbare kennis worden in plaats van alleen in OpenAI's cloud te leven:

1. Open in ChatGPT **Settings → Data controls → Export data** en bevestig. (Vereist dat je bent ingelogd op de webapp.)
2. OpenAI mailt je binnen enkele minuten tot een dag een downloadlink; de link is tijdgebonden. Download de ZIP - die bevat `conversations.json` (plus `chat.html`, media).
3. Importeer het in de kluis:
   ```bash
   python3 .claude/scripts/import-chatgpt-export.py --input ~/Downloads/chatgpt-export.zip
   # preview first if you like:
   python3 .claude/scripts/import-chatgpt-export.py --input ~/Downloads/chatgpt-export.zip --dry-run --verbose
   ```
   Elk gesprek wordt een ruwe sessie-log onder `01-raw/sessies/`. Draai daarna `/wiki` om ze tot artikelen te compileren en `/kennisbank:rebuild-memory` om de geheugenlaag te extraheren. Herimports worden standaard overgeslagen (idempotent); geef `--force` mee om te overschrijven.

De importer loopt door ChatGPT's bericht-*boom* (`mapping`), ordent beurten op tijdstempel, en houdt alleen jouw en de assistent-beurten - systeem- en tool-nodes worden weggelaten. Het draait volledig lokaal; er wordt niets ergens naartoe gestuurd.

## Documentatie

| Bestand | Voor |
|------|-----|
| [docs/guiding-principles-and-values.nl.md](docs/guiding-principles-and-values.nl.md) | De guiding principles en values, uitgewerkt als één document |
| [PRINCIPLES.nl.md](PRINCIPLES.nl.md) | De ontwerp-wetten die elke beslissing sturen (beknopte referentie) |
| [VALUES.nl.md](VALUES.nl.md) | Waar het project om geeft - het karakter (beknopte referentie) |
| [AGENTS.md](AGENTS.md) | AI-codeer-agents (Claude Code, Codex, GitHub Copilot CLI en OpenCode) die dit namens een gebruiker installeren |
| [POST-INSTALL.md](POST-INSTALL.md) | Eerste-sessie-walkthrough nadat `setup.sh` klaar is |
| [CONFIGURATION.md](CONFIGURATION.md) | Elke configureerbare knop: paden, drempels, modellen, toggles |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Symptoom / oorzaak / oplossing voor veelvoorkomende problemen |
| [OBSIDIAN.md](OBSIDIAN.md) | Open de kluis in Obsidian, aanbevolen gratis plugins |
| [CHANGELOG.md](CHANGELOG.md) | Release-geschiedenis, Keep a Changelog-formaat |
| [vault-structure/README.md](vault-structure/README.md) | Map-voor-map-referentie |

## Aanpassen

1. Bewerk `<vault>/CLAUDE.md` na setup. Vervang `[YOUR NAME]` en `[YOUR PROJECTS]` door je eigen. Voor een niet-standaard installatie is `<vault>` het exacte `KENNISBANK_VAULT`-pad dat je gebruikte.
2. **Kluispad.** Alle Python-scripts, `doctor.sh`, en gegenereerde agent-integraties respecteren de omgevingsvariabele `KENNISBANK_VAULT` (standaard `~/KennisBank`). Zie [CONFIGURATION.md](CONFIGURATION.md) sectie 9 voor het niet-standaard-kluiscontract.
3. **Embedding-backend.** Verwisselbaar via `<vault>/.claude/kennisbank-embed.json` of `KB_EMBED_*`-env-vars: standaard lokale Ollama, OpenAI-compatibele endpoints wanneer geconfigureerd. Van model wisselen invalideert de cache by design; draai daarna `kb-calibrate.py` om de drempels tegen het nieuwe model te controleren (het stelt waarden voor, jij stelt ze in).
4. **LLM-backend** (beoordeling/extractie): `<vault>/.claude/kennisbank-llm.json` of `KB_LLM_*`-env-vars. Standaard Ollama `gemma4:latest`; optioneel OpenRouter gebruikt `https://openrouter.ai/api/v1/chat/completions` via het OpenAI-compatibele chat-schema.
5. **Wiki-categorieën.** `build-karpathy-index.py` groepeert artikelen met een ingebouwde taxonomie; overschrijf met een `categories.json` (kopieer [`categories.example.json`](categories.example.json)).
6. De commando's zijn standaard in het Nederlands (ze volgen de prompt-taal). Wijzig de sectiekoppen als je Engels prefereert.
7. Stale-drempel (standaard 60 dagen): geef `--days N` mee of bewerk `stale-check.py`.
8. `auto-crosslink.py`-instelbare waarden: `MIN_CONFIDENCE` (standaard `0.75`) en `MAX_NEW_LINKS` (standaard `5`).
9. Research-uitvoerpad: het wijzigen raakt meerdere plekken (`setup.sh`, de autoresearch-skill, en de commando-tekst) - zie [CONFIGURATION.md](CONFIGURATION.md) sectie 5.
10. Om de `/autoresearch`-trigger in te schakelen, voeg dit snippet toe aan je globale `~/.claude/CLAUDE.md`:
    ```
    # autoresearch
    - **autoresearch** (`~/.claude/skills/autoresearch/SKILL.md`) - multi-round research with lazy hierarchy check. Output to `~/Claude/research/`. Trigger: `/autoresearch`
    When the user types `/autoresearch`, invoke the Skill tool with `skill: "autoresearch"` before doing anything else.
    ```

## Optioneel: graphify-integratie

`auto-crosslink.py` leest uit `<vault>/graphify-out/graph.json`, geproduceerd door de graphify-skill wanneer die op de kluis wordt gedraaid. Zonder dit wordt de crosslink-stap stilletjes overgeslagen. Retrieval profiteert indirect: de graaf-buur-uitbreiding volgt de wikilinks die crosslinking onderhoudt.

## Optioneel: kennisgraaf-dashboard

[Understand-Anything](https://github.com/Lum1104/Understand-Anything) is een aparte Claude Code-plugin (MIT) die een wiki volgens het Karpathy-patroon omzet in een interactief kennisgraaf-dashboard. Bouw de vereiste index met `python3 scripts/build-karpathy-index.py`, en draai dan `/understand-knowledge` binnen `<vault>/02-wiki`. Zie `--help` voor vlaggen; categorieën zijn aanpasbaar via `categories.json`.

## Dankbetuigingen

- Patroon: [Andrej Karpathy's LLM Wiki-gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- Kluis-/CMS-inspiratie: [claude-obsidian door AgriciDaniel](https://github.com/AgriciDaniel/claude-obsidian)
- Geheugenarchitectuur-lessen: het publieke werk rond Mem0, Zep/Graphiti, Letta, en Cognee, hier local-first herbouwd

## Licentie

MIT. Zie [LICENSE](LICENSE).
