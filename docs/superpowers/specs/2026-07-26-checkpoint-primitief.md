# Checkpoint-primitief: werkstand-snapshot vóór compaction (TASK-79)

Idee geleend van Mind (github.com/GabrielMartinMoran/mind): `checkpoint_save` /
`checkpoint_load` / `checkpoint_done`. Deze notitie legt vast hoe het in
KennisBank landt en waarom het niet dubbelt met bestaande lagen.

## Verhouding tot /sessielog en geheugen-extractie (geen duplicatie)

Drie lagen, drie tijdshorizonnen:

| laag | richting | levensduur | inhoud |
|------|----------|------------|--------|
| checkpoint | vooruit ("dit moet nog") | uren-dagen, wegwerp | actieve taak, werkstand, open beslissingen, volgende stap |
| /sessielog | achteruit ("dit gebeurde") | permanent, raw-laag | verslag + wiki-kandidaten |
| geheugen (09-memory) | tijdloos ("dit is waar") | permanent, gecureerd | feiten, voorkeuren, lessen |

Een checkpoint is werkstand, geen kennis: het wordt NIET geïndexeerd als
wiki-artikel en niet gedestilleerd. Zodra een sessielog geschreven is, is elk
ouder checkpoint achterhaald — daarom sluit `/sessielog` ze automatisch af
(`kb-checkpoint.py --done`). Dat is de hele overlap-regel; er is geen tweede
plek waar dezelfde informatie duurzaam landt.

## Architectuur (KISS: één script, één state-bestand, markdown in de vault)

- **Semantisch checkpoint**: `/checkpoint` (command, via ROOT_COMMANDS ook in
  Codex als `$checkpoint` en Copilot als `/checkpoint`). De agent schrijft
  markdown naar `01-raw/checkpoints/` en registreert het pad via
  `kb-checkpoint.py --register`.
- **Automatische stub**: Claude's `PreCompact`-hook draait `kb-checkpoint.py`
  zonder argumenten. Die schrijft — gated op de opt-in toggle `checkpoints` —
  een mechanische stub (transcript-pad, sessie, tijdstip) naar
  `.claude/kb-checkpoint-state.json`. PreCompact kan geen context injecteren
  (side-effects only), dus meer dan een stub is daar niet mogelijk; het
  semantische werk gebeurt bij `load` op basis van het transcript.
- **Herstel-pad**: `kb-session-start.py` draait `kb-checkpoint.py --notify
  --source <source>` in het always-blok, dus VÓÓR de 300s-freshness-gate. Een
  SessionStart met `source=compact` valt vrijwel altijd binnen die gate; in
  NOTIFICATIONS zou de melding precies dan wegvallen. De coordinator parseert
  daarvoor nu het `source`-veld uit de hook-payload.
- **Afsluiten**: `/checkpoint done`, na een geslaagde `load`, of automatisch
  door `/sessielog`.

## Client-matrix (bewuste asymmetrie)

| client | auto-stub bij compaction | melding bij sessiestart | handmatig |
|--------|--------------------------|-------------------------|-----------|
| Claude Code | ja (PreCompact) | ja | /checkpoint |
| Codex | nee (geen PreCompact-event) | ja (zelfde coordinator) | $checkpoint |
| Copilot CLI | nee | ja | /checkpoint |

Mind lost dit identiek op (capability-profiel L1/L2/L3 met degradation): waar
de client geen event biedt, degradeert het schrijfpad naar handmatig; het
leespad is overal gelijk. `install-agent-envs.py` neemt het PreCompact-event
bewust niet op in de Codex/Copilot-registratie.

## Toggle

`checkpoints` (default UIT) gate-t alleen de automatische PreCompact-stub.
`--register`, `--list`, `--done` en `--notify` werken altijd: wie handmatig
/checkpoint draait, wil een checkpoint, en een bestaand checkpoint verzwijgen
omdat een toggle uit staat zou het herstel-pad saboteren.

## Begrenzingen

- State begrensd op 20 entries (`MAX_PENDING`); een hook-loop kan de state niet
  onbegrensd laten groeien.
- `--register` weigert paden buiten `01-raw/checkpoints/` (zelfde strengheid
  als `kb-session-log.py`).
- Alles fail-open, stdlib-only, vault-root via `_vaultpath` (ADR-0002).
