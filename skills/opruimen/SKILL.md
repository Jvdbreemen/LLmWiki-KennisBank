---
name: opruimen
description: >-
  Session hygiene for agent clients: find idle sessions in a Hermes session
  store and in Claude Code transcripts, log them to the KennisBank through
  OpenRouter with a local fallback for sensitive material, then close out
  archived sessions and leftover guard processes. Triggers: /opruimen,
  "ruim op", "clean up sessions".
---

# Opruimen (sessie-hygiëne)

Deze skill ruimt sessies op van een agentclient: stille sessies opzoeken, er een
sessielog van maken, en daarna de dode rest opgeruimen. De body is Nederlands,
omdat hij een prompt is voor Nederlandstalige sessies.

**Locaties.** `setup.sh` rolt deze skill uit naar `~/.claude/skills/opruimen/`
(Claude Code), `~/.agents/skills/opruimen/` (Codex, OpenCode, Copilot) en
`$HERMES_HOME/skills/kennisbank/opruimen/` (Hermes, namespaced). De scripts staan
in `scripts/` naast deze SKILL.md; de voorbeelden hieronder draaien vanuit die map.

## Wanneer gebruiken

- De gebruiker zegt "ruim op" of "/opruimen".
- Er staan veel sessies open en die gebruiker wil weten wat dood is of weg kan.

## Er zijn twee oppervlakken, en ze zijn niet hetzelfde

| | Hermes-store (`$HERMES_HOME/state.db`) | Claude Code (transcripten + CCD-sidebar) |
|---|---|---|
| wat de gebruiker ziet | de sessielijst in de desktop-app | de kaarten in de CC-sidebar |
| stille sessies vinden | `hermes sessions list`, `state.db` | `CC_PROJECTS` (default `~/.claude/projects`) |
| opruimen | Hermes archiveert (soft-hide) | alleen CC archiveert, via `archive_session` |
| sessielog | ja | ja |
| proces/guard sluiten | ja, met bevestiging | **nooit het proces van een CCD-kaart** |

Begin bij de Hermes-store. Dat is wat de gebruiker in zijn UI ziet en waar de echte
rommel ontstaat. De Claude Code-kant is optioneel: die oppervlakken bestaan alleen
als er een levende Claude Code-installatie is. Is die er niet, dan sla stap 2 over en
is `scan_transcripten.py` een no-op.

## Stap 1: de Hermes-store

```bash
python3 scripts/scan_hermes_sessies.py
```

Geeft per open sessie de bron, het aantal berichten, de laatste activiteit en of er
een beurt loopt. Romeinse verdachten zijn `source = a2a` en `acp`: dat zijn door een
ander proces gespawnde sessies, geen gesprekken van de gebruiker. Een statuscheck van
3 berichten is rommel; een a2a-sessie met 100+ berichten kan de nachtklus zijn.

Archiveer, verwijder nooit:

```bash
python3 scripts/archiveer_hermes_sessies.py --a2a-klein
python3 scripts/archiveer_hermes_sessies.py --ouder-dan-vandaag
python3 scripts/archiveer_hermes_sessies.py --ids <id> <id> --yes
```

Na een Hermes-update kan de script-herstart misgaan: het script herstart zichzelf
alleen als de systeempython ouder is dan 3.10, maar een nieuwere systeempython
zonder `yaml` strooit ook. Roept het script dan direct aan met
`$HERMES_HOME/hermes-agent/venv/bin/python3`.

Zonder `--yes` is het een proefrun. De archiveerstap is dezelfde functie als de
archiveerknop in de app: `SessionDB.set_session_archived` (soft-hide, berichten
blijven staan). Terugzetten kan met dezelfde aanroep en `False`. Het script start zich
zo nodig zelf opnieuw met de venv-python van de installatie; een systeempython van
3.9 is te oud voor `hermes_state`.

Wat je moet weten voordat je filters intikt:

- **`hermes sessions archive` raakt open gateway-sessies niet.** Die selector is
  vastgezet op `ended_at IS NOT NULL`, en a2a/acp-sessies sluiten nooit. `--source a2a`
  meldt dus "No sessions match" terwijl er 30 rijen staan. Gebruik het script.
- **Nooit een sessie met een lopende beurt.** Die staat in `session_turn_leases`
  (`expires_at > nu`). Het script slaat ze automatisch over en zegt welke.
- **Nooit een sessie met activiteit van vandaag**, tenzij de gebruiker letterlijk
  zegt dat die ook weg mag.
- **De lange sessie blijft staan.** Bepaal hem op de spanne `started_at` tot
  `last_activity_at` plus het aantal berichten, niet op bestandsgrootte. Twijfel je
  welke sessie bedoeld wordt, vraag het met de kandidaten in de vraag.
- **De verborgen "Bot Chat" blijft altijd staan.** Dat is de canonieke bot-rij van de
  desktop; archiveren breekt Bot Mode. Het script slaat hem over, net als gepinde
  sessies.

## Stap 2: Claude Code (optioneel)

Deze stap geldt alleen als er een levende Claude Code-installatie is, dus als
`$CC_PROJECTS` (default `~/.claude/projects`) bestaat. Anders is er niets te meten.

```bash
python3 scripts/scan_transcripten.py
```

### Wat "stil" betekent

Een sessie is stil als er in de laatste **6 uur geen prompt van de gebruiker** in
staat. Meet dat uit het transcript, nooit uit procesleeftijd of bestandstijden.

Transcripten staan in `$CC_PROJECTS/<encoded-cwd>/<cliSessionId>.jsonl`. Pak de
laatste regel met `type: "user"` die echte tekst bevat. Sla over: `isMeta`, beurten
die alleen `tool_result` bevatten, en tekst die begint met `<` of `system-reminder` /
`Caveat:` bevat.

**Filter per tekstblok, niet op het samengevoegde bericht.** De `content` van een
user-record is een lijst blokken, en Claude Code zet een system-reminder als eigen
`text`-blok vóór de woorden van de gebruiker in datzelfde bericht. Plak je de blokken
eerst aan elkaar en test je daarna op "begint met `<`" of "bevat system-reminder",
dan gooi je de echte prompt mee weg en lijkt de sessie leeg. Loop de blokken dus los
af, strip per blok de `<system-reminder>`- en `<local-command-*>`-secties, en houd
over wat dan nog tekst is.

Controle: vindt je scan geen enkele prompt terwijl het transcript tientallen regels
telt, dan is je filter stuk, niet de sessie leeg.

**Reken in één tijdzone.** De `timestamp`-velden in het transcript zijn UTC, de
bestands-mtime is lokaal (CEST = UTC+2). Meng je die, dan lijkt elk transcript precies
twee uur jonger dan het is. Het script print alleen UTC en zegt dat erbij.

### Welke sessies een CC-kaart hebben

De CCD-sidebar (`~/Library/Application Support/Claude/claude-code-sessions/` op
macOS) legt per kaart een `local_<uuid>.json` met veld `cliSessionId` vast. Staat de
id daar en is `isArchived` false: het is een CCD-sessie, dus Hermes sluit hem niet af.
De CCD-id (`local_<uuid>`) is NIET de CLI-id.

Gebruik altijd de **volledige uuid**. Zoeken op de eerste 8 tekens lijkt te werken
maar mist stil elke treffer, want het veld bevat de hele uuid.

Draait er nog iets voor een sessie:

```bash
ps -eo command | grep -F "<cliSessionId>" | grep -v grep | grep -vc cozempic
```

Maar weet wat die uitkomst wel en niet zegt. De desktop-app start zijn `claude` met de
sessie op stdin, niet in de commandline (geen `--session-id`). Bij een CCD-sessie is de
uitkomst daarom onbetrouwbaar in beide richtingen: nul terwijl de app hem open heeft,
of een paar treffers van hulp-processen die de id in hun MCP-argumenten dragen. Alleen
bij een sessie die als CLI is gestart (terminal, OpenCode, door Hermes gespawnd)
bewijst de check iets, want daar staat `--session-id` in de argv. Voor CCD-sessies is
de harde bron of de kaart gearchiveerd is, en anders vraag je het.

## Stap 3: sessielogs

Gebruik de skill `sessielog` voor de opzet en de frontmatter-eisen. Voor een sessie
waar je zelf niet in zit, comprimeer je het transcript en laat je een model het log
schrijven:

1. Digest bouwen uit het transcript: gebruikersprompts, slotfragmenten van de
   assistent, gebruikte tools en aangeraakte bestanden, samen maximaal ~60k tekens.
2. Digest plus het template uit `<vault>/04-templates/tpl-sessie-log.md` in één
   request naar `https://openrouter.ai/api/v1/chat/completions`, met reasoning aan.
   CCR (`SESSIELOG_ROUTE=ccr`, model `openrouter,z-ai/glm-5.3-flash`) is de reserve,
   geen hoofdroute.
3. Schrijf naar `<vault>/01-raw/sessies/raw-sessie-<sessiedatum>-<slug>.md`. Gebruik de
   datum van de sessie zelf, niet vandaag.
4. Bij HTTP 500 (`ETIMEDOUT` op de upstream): opnieuw proberen, drie pogingen.

### Vault, store en route via de omgeving

Geen enkel pad staat hard in deze skill; alles loopt via de omgeving, met de
productdefault als laatste.

| variabele | standaard | waarvoor |
|---|---|---|
| `KENNISBANK_VAULT` | `~/KennisBank` | vault voor logs, template en nasleep |
| `HERMES_HOME` | `~/.hermes` | Hermes-store (`$HERMES_HOME/state.db`), scratch-state en venv |
| `CC_PROJECTS` | `~/.claude/projects` | Claude Code-transcripten; bestaat alleen bij een levende Claude Code |
| `SESSIELOG_ROUTE` | `openrouter` | `openrouter` of `ccr` |
| `SESSIELOG_MODEL` | `stealth/space-bunny-alpha` | cloudmodel op de hoofdroute |
| `SESSIELOG_MAX_TOKENS` | `16000` | zie denkbudget hieronder |
| `SESSIELOG_LOKAAL_MODEL` | `qwen3.8:27b-mlx` | lokaal model in de gevoeligheidsroute |
| `SESSIELOG_LOKAAL_CTX` | `16384` | contextvenster van de lokale route |
| `SESSIELOG_LOKAAL_DIGEST` | `24000` | maximale digestlengte (tekens) op de lokale route |

Het standaardmodel van de lokale route is een voorbeeld: zet `SESSIELOG_LOKAAL_MODEL`
op het model dat op jouw machine lokaal draait (`ollama list`).

`sessielog-batch.py` heeft daarnaast `--vault <pad>` voor een enkele run. Het template
wordt per vault gelezen; ontbreekt `04-templates/tpl-sessie-log.md`, dan zegt het
script welk pad het miste.

**Ook de lokale route kapt af.** Ollama kapt stil af op `num_ctx`; daarom kapt het
script de digest zelf op `SESSIELOG_LOKAAL_DIGEST` tekens en zet er een zichtbare
markering `[... digest afgekapt ...]` in het prompt. Zonder die markering zie je niet
dat het einde van de sessie in het log ontbreekt.

**Het denkbudget is de valkuil.** Reasoning-tokens tellen mee in `max_tokens`, dus
een te krappe waarde laat het log halverwege afbreken zonder dat `finish_reason` dat
zegt. De controle is daarom niet de lengte maar de laatste templatekop
(`## AI-verantwoording`). Ontbreekt die, opnieuw proberen; niet "het is wel lang
genoeg". Standaard 16000, en hoger mag altijd.

### Gevoeligheidshek

Niet alle sessies mogen naar een cloudmodel. `AGENTS.md` (de KennisBank-regels)
deelt de sporen in categorieën, en categorie 1-4 horen niet naar buiten de machine.
Daarom staat er een hard hek vóór elke generatie, geen advies:

- `gevoelig-paden.txt` (naast het script) bevat één patroon per regel, `#` als
  commentaar. **De ingebakken defaultlijst geldt altijd**: het bestand voegt
  patronen toe, het kan er niets weghalen. Een leeg of verwijderd bestand opent het
  hek dus niet.
- `is_gevoelig(digest + titel)` toetst case-insensitive op substring, over digest én
  sessietitel. De titel is vaak het enige spoor als de prompts zelf geen pad noemen.
  Staat de route op cloud en is er een treffer, dan gaat de sessie naar het lokale
  ollama-model (`http://127.0.0.1:11434/api/chat`, `options.num_ctx` 8192, timeout
  1800 s).
- **Geen stille terugval naar de cloud.** Is ollama onbereikbaar of geeft het een
  fout, dan wordt de sessie `geblokkeerd-gevoelig`. Dat is een melding, geen fout:
  rapporteer hem en laat de sessie staan tot de lokale route weer werkt.
- `--force-cloud` is de enige uitweg en print per sessie een waarschuwing. Gebruik
  hem alleen als de gebruiker dat expliciet vraagt.
- Het eindrapport telt hoeveel sessies lokal liepen en hoeveel geblokkeerd waren, en
  noemt per sessie de gebruikte route.

`--zelftest` bewijst de routekeuze zonder netwerk: gevoelig zonder `--force-cloud`
wordt `lokaal`, mét `--force-cloud` `cloud`, ongevoelig altijd `cloud`. Draai dat na
elke route- of hekwijziging, en ook als je een foutmelding over routes ziet.

**Zoek eerst, en zoek op onderwerp, niet op sessie-id.** De bestaande logs bevatten
geen sessie-ids, dus `grep -r <cliSessionId> 01-raw/sessies/` geeft nul treffers
terwijl het log er allang is. Zoek op de datum plus een kernwoord uit de kaarttitel of
de eerste prompt (`ls 01-raw/sessies | grep -i <onderwerp>`). Schrijf je een tweede log
over dezelfde sessie, dan vervuil je de vault en telt de index dubbel.

Voor Hermes-store-sessies in bulk staat er `scripts/sessielog-batch.py`: bouwt digests
uit `state.db`, matcht tegen bestaande logs (voorkomt dubbelen), schrijft via
OpenRouter met de CCR-route als reserve en houdt een statefile bij zodat een afgebroken
run hervat. Twee stappen: `sessielog-batch.py manifest` (overzicht, geen writes) en
`genereer`. `STILTE_UREN` (standaard 6) bepaalt de doelset. Zet de genereerstap in een
`screen` met log in `/tmp`; elke request duurt 10-60 s en de hele batch duurt te lang
voor een beurt. Natrokken na afloop: de laatste kop (`## AI-verantwoording`) per log,
en of het bestand niet leeg is. De rest doet het script zelf: `natek()` zet
`source: claude-sessie`/`tags: [claude-sessie]` om naar `hermes-sessie` en schrijft
losse kandidaat-zinnen om naar `- wiki-kandidaat: <onderwerp>`, want alleen dat
formaat herkent `wiki-scan.py`. Een los natek-script is dus niet meer nodig.

Het eindrapport van `genereer` staat altijd op stdout en noemt: het aantal gelogde
logs, het volledige pad per log, het aantal regels `- wiki-kandidaat:` per log, de
gebruikte route en het model per sessie, en de vervolgstap als losse regel
(`<vault>/.claude/scripts/wiki-scan.py --days 8`). Dat is het rapport dat stap 3b
voedingt; lees het voordat je zelf gaat zoeken.

`--natek-index` (bewust opt-in, staat standaard uit) draait de KennisBank-nasleep na
een geslaagde generatie: `build-karpathy-index.py --force` met de venv-python van de
dev-installatie, daarna `touch <vault>/graphify-out/.needs-rebuild`. Ontbreekt een van
beide, dan meldt het script dat en maakt het niets aan. Gebruik hem als je de batch
ook meteen door de index wilt halen; anders doe je het handmatig in stap 3b.

Het script moet met de venv-python van de Hermes-installatie draaien
(`$HERMES_HOME/hermes-agent/venv/bin/python3`). Een systeempython die `ruamel.yaml`
mist, faalt met `ModuleNotFoundError`, omdat dat via `hermes_state` binnenkomt.

De OpenRouter-sleutel komt uit de omgeving, of uit `$HERMES_HOME/.env`, of uit
`~/.openrouter-env`. `sessielog-batch.py` leest die zelf en gebruikt hem alleen in de
`Authorization`-header; hij print of logt hem nooit. Ontbreekt de key, dan krijg je
een `RuntimeError` met de drie plekken waar hij gezocht is.

CCR is alleen de reserve (`SESSIELOG_ROUTE=ccr`). Draait CCR niet, of komt er een 401
terug met "Missing Authentication header", dan stuurt CCR de letterlijke string
`$OPENROUTER_API_KEY` door. Hij expandeert zijn config niet zelf; de variabele moet in
zijn omgeving staan bij het starten. CCR hoort in een eigen screen:

```bash
screen -dmS oc-ccr bash -lc 'env OPENROUTER_API_KEY="$(grep -m1 "^OPENROUTER_API_KEY=" "$HERMES_HOME/.env" | cut -d= -f2-)" ccr start'
```

Controleer de output op volledigheid, niet op lengte: het denkbudget telt mee in
`max_tokens`, dus een log kan halverwege afbreken zonder dat `stop_reason` dat
verraadt. Eis dat de laatste kop uit het template aanwezig is.

Een log dat de gebruiker met de hand heeft gecorrigeerd laat je met rust.

## Stap 3b: wiki-compilatie

De logs zijn de grondstof voor de wiki, en dat is een eigen stap (commando `wiki`).
Draai `<vault>/.claude/scripts/wiki-scan.py --days 8`, splits de kandidaten in nieuw
(deze batch), oud (nooit verwerkte oudere logs) en ruis, en werk ze in batches af. De
`- wiki-kandidaat: <onderwerp>`-regels in de logs zijn het invoerformaat van
`wiki-scan.py`; die telling staat in het eindrapport van stap 3, dus je hoeft de logs
niet nog eens te lezen om te weten wat erin zit. Tientallen kandidaten gaan sneller en
veiliger met meerdere subagents per cluster dan met één run: geef elke subagent een
eigen set kandidaten (verdeel op onderwerp, niet op log, anders schrijven twee
subagents hetzelfde artikel) plus het vaste voorschrift en het rapportformaat van de
wiki-skill. Maak vooraf een backup van `02-wiki`.

Na de compilatie: `kb-lint.py` moet schoon zijn, `build-karpathy-index.py --force`
herbouwt index en log, en `graphify-out/.needs-rebuild` zet de kennisgraaf klaar.
Blijkt een log template-koppen als wiki-kandidaat te leveren (Doel, Output,
Vervolgacties, AI-verantwoording), zet die dan in `GENERIC_HEADINGS` van
`wiki-scan.py`.

## Stap 4: processen en guards

Elk guard-proces draagt zijn sessie in de commandline (`--session <cliSessionId>` of
`--session-id`). Gebruik PPID niet als signaal: een guard daemoniseert zichzelf, dus
ze staan allemaal op 1.

**Controleer eerst of ze er nog zijn.** Een guard hangt aan een sessie die in de app
open staat; archiveert de gebruiker die kaart, dan verdwijnt de guard mee. Kijk dus met
`pgrep -fl <guardpatroon>` voordat je een kill-lijst maakt, anders kondig je werk aan
dat al klaar is.

**Bepaal wees-zijn met het juiste signaal.** Voor een CLI-gestarte sessie: geen ander
proces dan de guard met die id betekent dood, dus SIGTERM. Voor een CCD-sessie werkt
dat niet (zie stap 2, de app zet de id niet in de argv). Daar geldt: kaart
gearchiveerd of weg, dan is de guard wees; kaart nog open, dan laat je hem staan of
vraag je het. Twee valkuilen die dit ondervangt:

- **Een sessielijst is nooit compleet.** De CC-sidebar toont alleen kaarten. Een
  `claude` in de terminal en een door Hermes of OpenCode gestarte sessie hebben wel een
  guard maar geen kaart. Die als wees wegstrepen is fout zolang hun proces draait.
- **Transcript-mtime is geen levensteken.** Afsluiten schrijft zelf nog een
  `mode`-record, dus het transcript van een net gesloten sessie is seconden oud. Ook
  starten van de desktop-app raakt alle transcripten tegelijk. Gebruik mtime hooguit
  als bijvangst, nooit als doorslag.

Toon daarna een eventuele statusfile van de janitor (`~/Claude/logs/janitor-status.json`)
als die bestaat.

## Bevestigen, niet aankondigen

Sluiten en killen vraagt bevestiging per geval, maar dat hoeft geen vragenlijst te
worden: zet alle kandidaten in **één** `clarify` van het type multi-select, met de
aanbevolen optie eerst. Vraag in dezelfde call alleen wat je echt niet kunt afleiden,
zoals welke sessie "de lange" is.

Draait er een langdurige klus (screen, agent-doorloop, nachtwacht) die na jouw beurt
moet doorlopen, zet hem in `screen` met een log in `/tmp`. `screen -X quit` doodt
alleen de screen, niet het kind: `pkill -f <script>` en daarna met `ps` controleren of
er geen schrijver meer is.

## Rapport

Sluit af met: wat is gearchiveerd of gesloten en waar, wat is gelogd, wat blijft staan
en waarom, en welke CCD-sessies klaar zijn om in Claude Code te archiveren. Noem ook
waar de rommel vandaan kwam en of dat opgelost is; blijft de bron bestaan, meld dat met
de plek waar het geregeld moet worden.

## Harde regels

- Nooit een sessie sluiten of archiveren als de sessielog-stap faalde of als er nog
  geen log is voor een sessie met inhoud. Een statuscheck van drie berichten valt niet
  te loggen en hoeft dat ook niet; zeg dat expliciet. Zulke te kleine sessies mogen wel
  gewoon mee in het archief.
- Nooit een sessie sluiten met een prompt van de gebruiker binnen 6 uur.
- Nooit een sessie met een lopende beurt archiveren.
- Nooit het proces van een CCD-sidebarsessie beëindigen.
- Nooit verwijderen waar archiveren volstaat.
- Nooit `--force-cloud` zonder een expliciete vraag van de gebruiker.
- Twijfel je, laat staan en vraag.

## Referenties

- `scripts/scan_hermes_sessies.py` - open sessies in de Hermes-store, met lopende beurten
- `scripts/archiveer_hermes_sessies.py` - archiveren per criterium of per id (proefrun zonder `--yes`)
- `scripts/scan_transcripten.py` - laatste prompt per CC-transcript, met stilte-uren
- `scripts/sessielog-batch.py --zelftest` - offline proef van vault-resolutie,
  gevoeligheidshek, natek en routekeuze; exitcode 1 bij een FAIL
- `gevoelig-paden.txt` - de patronen die nooit naar een cloudmodel mogen; één per
  regel, `#` als commentaar, bij ontbreken geldt de defaultlijst in het script
- `commands/opruimen.md` - de Claude Code-variant, met de archiveerstappen; werkt
  alleen met een levende Claude Code-installatie (`CC_PROJECTS` + CCD-sidebar)
- skills `sessielog` en `wiki`
