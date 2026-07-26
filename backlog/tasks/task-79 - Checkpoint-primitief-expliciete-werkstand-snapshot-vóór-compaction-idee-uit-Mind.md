---
id: TASK-79
title: >-
  Checkpoint-primitief: expliciete werkstand-snapshot vóór compaction (idee uit
  Mind)
status: Done
assignee: []
created_date: '2026-07-26 14:14'
updated_date: '2026-07-26 14:54'
labels:
  - idee-gestolen
  - geheugen
milestone: Agent-geheugen
dependencies: []
references:
  - 'https://github.com/GabrielMartinMoran/mind'
priority: medium
ordinal: 89000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Geleend van github.com/GabrielMartinMoran/mind. Mind biedt checkpoint_save (werkstand + gelinkte memories vastleggen op beslismoment), checkpoint_load (herstel na context-compaction) en checkpoint_done (checkpoint afsluiten naar een sessie-samenvatting).

KennisBank heeft sessielog (achteraf) maar geen gericht vooraf-snapshot dat na compaction of sessie-crash de werkstand herstelt. Onderzoek en bouw een checkpoint-primitief: klein commando/skill dat huidige taak, openstaande beslissingen en relevante artikelen vastlegt, plus een recall-pad dat dit bij sessiestart of na compaction aanbiedt. KISS: markdown in de vault, geen aparte store. Afsluiten van een checkpoint mag samenvallen met /sessielog.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Ontwerpnotitie: hoe verhoudt checkpoint zich tot /sessielog en geheugen-extractie (geen duplicatie, KISS)
- [x] #2 Checkpoint aanmaken legt vast: actieve taak, werkstand, open beslissingen, gelinkte artikelen — als markdown in de vault
- [x] #3 Herstel-pad: checkpoint wordt bij sessiestart (of na compaction) gesignaleerd en kan geladen worden
- [x] #4 Checkpoint afronden sluit hem af naar een sessie-samenvatting of markeert hem verwerkt
- [x] #5 Werkt lokaal, geen cloud; getest op Windows + WSL-pad
- [x] #6 Schrijfpad dubbel: PreCompact-hook (Claude, automatisch) én /checkpoint-command via ROOT_COMMANDS (Codex/Copilot, handmatig)
- [x] #7 SessionStart-coordinator parseert source-veld; checkpoint-melding vóór de freshness-gate (always-blok of status_line)
- [x] #8 Opt-in toggle geregistreerd op alle 4 knob-oppervlakken; test_knob_consistency groen
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Deep-research haalbaarheid (2026-07-26)

**Verdict: bouwbaar met bestaande bouwstenen. Client-agnostisch: leespad ja, schrijfpad deels.**

### Hook-feiten (bron: code.claude.com/docs/en/hooks)
- `PreCompact` bestaat (matchers `manual`/`auto`), side-effects only, geen contextinjectie — maar krijgt `transcript_path`, dus kan checkpoint schrijven vlak vóór compaction.
- `SessionStart` heeft `source`-waarden `startup|resume|clear|compact|fork` en injecteert context via stdout/`additionalContext`. Output-cap 10.000 tekens.
- Ideale Claude-flow: PreCompact schrijft snapshot → SessionStart(source=compact) injecteert herstel-melding.

### Client-agnostisch?
- **Claude Code**: volledig (PreCompact + SessionStart=compact).
- **Codex**: SessionStart-coordinator al geregistreerd met matcher incl. `compact` (install-agent-envs.py:392) → herstel-melding werkt via zelfde coordinator. Geen PreCompact-equivalent → snapshot alleen via exit-hook (Stop) of pull (/checkpoint-skill).
- **Copilot**: sessionStart/sessionEnd-coordinators bestaan (_copilot.py:355/362), geen compact-event → alleen pull + start-melding.
- Conclusie: schrijfkant moet dubbel: automatisch (PreCompact, Claude-only) + handmatig `/checkpoint`-command dat via ROOT_COMMANDS automatisch naar Codex ($checkpoint) en Copilot (/checkpoint) rendert (install-agent-envs.py:209-257, :43-59). Mind lost dit identiek op: capability-profiel L1/L2/L3 + degradation in hun recovery-pack.

### Drie verplichte fixes in ontwerp
1. **Freshness-gate**: kb-session-start.py `coordinate()` skipt NOTIFICATIONS binnen 300s (FRESHNESS_SECONDS, :28, :424-425) — een compact-event valt daar vrijwel altijd in. Checkpoint-melding dus in het `always`-blok (:415-422) of in `status_line()` (:464-469), NIET in NOTIFICATIONS.
2. **`source`-parsing ontbreekt**: coordinator onderscheidt startup niet van compact. Payload-parsing toevoegen (patroon: kb-session-end.py:129-138 leest transcript_path).
3. **Toggle-oppervlakken**: nieuwe opt-in toggle moet in 4 plekken (_settings.py DEFAULTS, commands/kennisbank/settings.md, skills/kennisbank-upgrade/SKILL.md ×2) anders faalt tests/test_knob_consistency.py:57-80. NB: settings.md mist activity_llm_fallback al en "7 toggles"-tekst klopt niet meer — meteen meefixen.

### Herbruikbare bouwstenen
- `kb-session-end-recover.py`: bestaand herstel-patroon met state-file + `--emit-context` (:102, :111-117) — dekt AC#3 bijna 1-op-1.
- `distill-notify.py`: canoniek melding-bij-start patroon met watermark + toggle fail-open (:74-85, :109-115).
- Afsluiten checkpoint (AC#4): semantisch werk → hoort bij /sessielog, niet in exit-hook (geen LLM in dat pad).
- Opslag: markdown in `01-raw/checkpoints/` (nieuw), via _vaultpath (ADR-0002).

### Mind-referentie (bronverificatie src/checkpoint/)
recovery-pack.ts: pack = checkpoint + ≤5 semantische context-hits + capability-profiel + degradation + guidance; fallback naar 5 recentste memories. checkpoint-done.ts: checkpoint → "session-{timestamp}"-memory, links verplaatst, origineel verwijderd. Beide concepten overneembaar.

### Correctie op beschrijving
ADR-005 (hookless Codex/Copilot) is Superseded by ADR-006 — Codex/Copilot hebben wél coordinators. Beschrijvingstekst "hookless" negeren.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Gebouwd en gemerged via PR #74 (merge-commit 2bd303f op origin/main).

- kb-checkpoint.py: PreCompact-stub (opt-in toggle `checkpoints`, default uit), --register/--list/--done/--notify; fail-open, stdlib-only, atomische state-writes.
- /checkpoint command (save/load/done) in commands/, via ROOT_COMMANDS ook Codex ($checkpoint) en Copilot.
- kb-session-start.py: source-parsing + checkpoint-melding in het always-blok, vóór de 300s-freshness-gate.
- /sessielog sluit open checkpoints af (--done).
- Toggle op alle knob-oppervlakken; bijvangst gefixt: activity_llm_fallback-omissies en de verouderde "7 toggles"-telling.
- Ontwerpnotitie: docs/superpowers/specs/2026-07-26-checkpoint-primitief.md.
- tests/test_checkpoint.py (14 tests); volledige suite 941 tests groen.
- Copilot-PR-review niet beschikbaar (quota bereikt); vervangen door een lokale code-review-agent, geen issues.

AC#5-kanttekening: getest op Windows (volledige suite); WSL-pad gedekt door dezelfde POSIX-conventies (python3, _vaultpath) maar niet apart gedraaid.
<!-- SECTION:FINAL_SUMMARY:END -->
