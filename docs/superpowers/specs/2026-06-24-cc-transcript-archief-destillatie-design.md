# Design: Claude Code transcript-archief + piggyback-destillatie

- **Datum:** 2026-06-24
- **Status:** ontwerp, goedgekeurd voor uitwerking
- **Scope:** Fase 1 van een breder doel (zie [Bredere context](#bredere-context))

## Probleem

Claude Code-sessies bevatten kennis die nu niet betrouwbaar wordt vastgelegd. Twee gaten:

1. **Archief-gat.** Transcripts staan in `~/.claude/projects/*.jsonl` en worden door `cleanupPeriodDays` gewist. Wie niet op tijd importeert, verliest ze. Er bestaat geen automatische archivering.
2. **Extractie-gat.** `/sessielog` en `/wiki` zijn handmatig en interactief. Kennis komt alleen uit een sessie als de gebruiker er actief om vraagt.

Doel: **elke Claude Code-chat archiveren met de laagst mogelijke frictie, en de kennis eruit destilleren** — zonder dat de gebruiker per sessie commando's hoeft te typen voor het archief.

### Wat dit GEEN native feature is

De aanleiding was de observatie `claude_code_session_archive: true` op een Linux-box. Dat is **geen native Claude Code config-key**. Het is een Ansible-rol-variabele (`when: claude_code_session_archive | bool`, `archive-transcript.sh.j2`, `managed-settings.json.j2`) die een **SessionEnd-hook installeert**. De vlag doet zelf niets; de hook doet het werk. Op deze Windows-box bestaat die Ansible-rol niet — we repliceren dus het hook-mechanisme, niet een vlag.

## Architectuur

De oplossing splitst de goedkope deterministische stap van de dure LLM-stap, consistent met twee bestaande patronen in dit project (SessionStart-indexbouw vs UserPromptSubmit-match; `.needs-rebuild`-schrijf vs graphify-dagbatch).

```
CC-sessie eindigt
   │
   ▼
[1] SessionEnd-hook  ──►  $VAULT/01-raw/transcripts/<datum>-<project>-<sid8>.jsonl
   (goedkoop, deterministisch, fail-open, watermark)   (backed-up = enige bron van waarheid)
                                                                │
                          ── volgende interactieve sessie ──    │
                                                                ▼
[2] SessionStart-hook meldt "N transcripts wachten op destillatie"   (goedkoop, push, géén LLM)
                                                                │
                          ── gebruiker trekt de zware pass ──   ▼
[3] /destilleer  ──►  import (--source archief) ──► 01-raw/sessies/ ──► /wiki ──► 02-wiki/
   (LLM-pass, pull, idempotent via watermark)
```

Kernbeslissing — **trigger = piggyback (Approach A)**, niet headless cron. De hook garandeert dat niets verloren gaat; een groeiende destillatie-achterstand is daarom onschadelijk. De cron-variant (Approach B) is genoteerd als backlog `TASK-1` (bespreken met Jim).

## Componenten

### Component 1 — Archiefhook (`scripts/archive-transcript.sh`)

Eén verantwoordelijkheid: het transcript van een net-geëindigde sessie veilig naar de vault kopiëren.

- **Trigger:** geregistreerd in user-`settings.json` onder `SessionEnd` (bevestigd: vuurt 1×/sessie op Windows, default Git Bash-shell, geeft `transcript_path`/`session_id`/`cwd`/`reason` op stdin).
- **Vault-resolutie:** `VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`, exact het repo-patroon dat branch `fix/vault-env-var-everywhere` standaardiseert. Geen hardcoded pad.
- **Self-locating fallback:** als de hook-omgeving `KENNISBANK_VAULT` niet doorgeeft, vindt het script de vault via zijn eigen pad (`$VAULT/.claude/scripts/archive-transcript.sh`), net als `kb-retrieve.py`.
- **Bestemming:** `$VAULT/01-raw/transcripts/<YYYY-MM-DD>-<project-slug>-<sid8>.jsonl`. `project-slug` afgeleid van `cwd`; `sid8` = eerste 8 tekens van `session_id`.
- **Idempotentie / watermark:** bestemmingsnaam bevat `session_id`. Een herhaalde `SessionEnd` (bv. na `/clear`) voor dezelfde sessie overschrijft alleen als de bron groter/nieuwer is (transcript groeit). Geen duplicaten.
- **Skip-regels:** lege of triviaal kleine transcripts (bv. een `claude -p`-aanroep die zelf `prompt_input_exit` triggert) worden niet gearchiveerd — size-drempel.
- **Fail-open:** elke fout (vault onbereikbaar, ontbrekend veld, kopieerfout) → log naar stderr, **exit 0**. Een SessionEnd-hook draait synchroon vóór exit; hij mag het afsluiten nooit blokkeren.
- **Optioneel:** een leesbare `.md` naast de `.jsonl` (jq-strip van tool-ruis), zoals de Linux-variant. Markeren als optioneel/v1.1 om de hook simpel te houden.

### Component 2 — Destillatie-notificatie (SessionStart-hook)

Eén verantwoordelijkheid: goedkoop melden dat er werk klaarstaat. Géén LLM.

- Telt transcripts in `01-raw/transcripts/` die nog niet in de destillatie-watermark staan.
- Bij `>0`: injecteert `additionalContext` ("N transcripts wachten op destillatie — draai `/destilleer`"). Bij `0`: niets, exit 0.
- Fail-open, snel, géén embed/LLM-aanroep. Push (de harness duwt de melding), in lijn met [[hook-gedreven-kennisretrieval]].

### Component 3 — `/destilleer` (nieuw slash-command, dunne orkestratie)

Eén verantwoordelijkheid: de pull-actie die de gebruiker draait wanneer hij wil. Ketent bestaande tooling, voegt geen nieuwe destillatie-logica toe.

1. Lees de destillatie-watermark; bepaal welke transcripts in `01-raw/transcripts/` nieuw zijn.
2. `import-cc-history.py --source $VAULT/01-raw/transcripts/` → schrijft raw-sessielogs naar `01-raw/sessies/` (zelfde formaat als `/sessielog`).
3. Roep de `/wiki`-compilatie aan over de nieuwe raw-logs → `02-wiki/`.
4. Werk de watermark bij (verwerkte `session_id`'s).
5. Rapporteer: gearchiveerd / geïmporteerd / wiki nieuw+bijgewerkt / overgeslagen.

**Belangrijk:** destillatie leest uit het **archief**, niet uit `~/.claude/projects`. Het archief is daarmee de enige bron van waarheid en `cleanupPeriodDays`-timing doet er niet meer toe. Dit vereist een nieuwe `--source <dir>`-flag op `import-cc-history.py`.

## Bestandswijzigingen

| Bestand | Wijziging |
|---|---|
| `scripts/archive-transcript.sh` | **nieuw** — SessionEnd-archiefhook |
| `scripts/import-cc-history.py` | **wijzig** — `--source <dir>`-flag toevoegen (default blijft `~/.claude/projects`) |
| `commands/destilleer.md` | **nieuw** — `/destilleer`-orkestratiecommando |
| `scripts/distill-notify.sh` + user `settings.json` SessionStart | **nieuw** — pending-transcripts-melding (push-hook, niet het handmatige `/sessiestart`) |
| user `settings.json` (buiten repo) | **wijzig** — SessionEnd- + SessionStart-hookregistratie (gedocumenteerd in setup) |
| `setup.sh` | **wijzig** — kopieer nieuw script + command, registreer hooks |
| `01-raw/transcripts/` | **nieuw** — archiefmap (+ `.gitkeep`); watermark-bestand `.distilled` |
| `vault-structure/README.md`, `README.md`, `CONFIGURATION.md`, `CHANGELOG.md` | **wijzig** — documenteren |

## Watermark-ontwerp

Twee onafhankelijke watermarks, want archiveren en destilleren zijn ontkoppeld:

- **Archief-idempotentie:** impliciet via bestemmingsbestandsnaam (`session_id` in de naam). Geen apart bestand nodig.
- **Destillatie-voortgang:** `$VAULT/01-raw/transcripts/.distilled` — platte lijst van verwerkte `session_id`'s. Component 2 telt `archief \ .distilled`; Component 3 vult aan na succes.

## Foutafhandeling

- Beide hooks **fail-open** (exit 0), nooit een sessie blokkeren of vertragen.
- Archiefhook: defensieve size-check + (optioneel) één retry als het transcript nog niet volledig geschreven lijkt (timing is niet officieel gedocumenteerd, wel synchroon vóór exit → vrijwel zeker veilig).
- `/destilleer` is **idempotent**: opnieuw draaien verwerkt alleen niet-gewatermerkte transcripts; een crash halverwege laat de watermark intact voor de rest.

## Testen

- **Archiefhook (unit, bash):** voer met een fixture-stdin-JSON; assert correct bestemmingspad, watermark-idempotentie (2× zelfde sessie → 1 bestand), skip op leeg transcript, exit 0 bij fout.
- **`import-cc-history.py --source`:** wijst naar een fixture-archiefmap, assert raw-sessielogs in `01-raw/sessies/`.
- **End-to-end (handmatig, eerste sessie):** echte sessie → check `.jsonl` in archief → nieuwe sessie → check melding → `/destilleer` → check wiki-artikel + watermark.

## Bredere context

Dit is **Fase 1** van een gefaseerd doel: kennisvastlegging met minimale frictie over alle Claude-oppervlakken, in één backed-up vault.

| Fase | Oppervlak | Aanpak | Status |
|---|---|---|---|
| 1 | Claude Code | SessionEnd-archief + piggyback-destillatie | **dit ontwerp** |
| 2 | Desktop / Co-work | auto-capture indien mogelijk, anders `/sessielog` | later |
| 3 | claude.ai (web) | ~1×/week export-bundle + `/import claudeai` | later |
| — | Cloud workloads | onduidelijk of er een lokaal transcript is | onderzoeken |

Backlog: `TASK-1` — headless cron-trigger (Approach B) als opt-in upgrade, bespreken met Jim.

## Niet in scope (YAGNI)

- Headless/onbeheerde verwerking (= Approach B, backlog).
- Desktop, claude.ai, cloud (Fase 2/3).
- Cross-machine sync — de vault is hier de lokale backed-up locatie; sync is een apart vraagstuk.
- Automatische LLM-destillatie binnen een hook — bewust pull, niet push.
