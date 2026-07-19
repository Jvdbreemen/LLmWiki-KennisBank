---
name: kennisbank-upgrade
description: >-
  Upgrade a deployed LLmWiki-KennisBank vault to the latest official release
  tag. Checks the upstream tag, shows the changelog, backs up the current
  deploy, copies the new tooling into the vault, stamps the version, and
  verifies with doctor.sh. Triggers: /kennisbank-upgrade, "upgrade
  kennisbank", "update kennisbank tooling".
---

# Kennisbank Upgrade

Upgrade a deployed vault to the latest **release tag** (never bare main).

## Resolve paths
- `VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`
- `REPO="${KENNISBANK_REPO}"` — if empty, ask the user for the path to their
  LLmWiki-KennisBank git checkout. Confirm it is a git repo (`git -C "$REPO" rev-parse`).

## Deploy map (referentie — stap 9 voert dit uit via `setup.sh`)
| Repo source | Deploy destination |
|---|---|
| `scripts/*.py`, `scripts/*.sh` | `$VAULT/.claude/scripts/` |
| `templates/*.md` | `$VAULT/04-templates/` |
| `commands/*.md`, `commands/*/*.md` | `$HOME/.claude/commands/` |
| `skills/*/SKILL.md` (each skill dir) | `$HOME/.claude/skills/<name>/` |

De feitelijke deploy in stap 9 gebeurt via `bash setup.sh --yes` (sinds v0.9.0 de
idempotent-veilige installer); deze tabel is alleen referentie voor wat waar landt.
`CLAUDE.md` is personalized and is NEVER overwritten (setup.sh respecteert dat).

## Procedure
1. `git -C "$REPO" fetch --tags --quiet`.
2. `LATEST=$(git -C "$REPO" tag --sort=-v:refname | grep '^v[0-9]' | head -1)`.
3. Read `$VAULT/.claude/.kennisbank-version` -> `INSTALLED` (the `tag` field).
   If the file is absent, treat as unknown/legacy and tell the user.
4. If `INSTALLED == LATEST`: report "up to date ($LATEST)" and stop.
5. Show what is NEW between versions: first run
   `git -C "$REPO" log --oneline "$INSTALLED..$LATEST"` to display the commit
   delta, then, if useful, also show the relevant CHANGELOG.md section at
   `$LATEST` (`git -C "$REPO" show "$LATEST:CHANGELOG.md"`). Keep it concise —
   the commit delta is usually enough.
6. Drift guard: iterate over ALL FOUR deploy-map categories — scripts
   (`$VAULT/.claude/scripts/`), templates (`$VAULT/04-templates/`), commands
   (`$HOME/.claude/commands/`), and skills. For skills, iterate over BOTH:
   (a) every installed skill dir under `$HOME/.claude/skills/*/SKILL.md`, AND
   (b) every skill dir in LATEST that step 9 will write (i.e. every
   `skills/*/` present in the checked-out LATEST tag).
   For each skill found in either set, perform a CRLF-agnostic diff of the
   deployed `~/.claude/skills/<name>/SKILL.md` against the INSTALLED tag's
   version (`git -C "$REPO" show "$INSTALLED:skills/<name>/SKILL.md"`).
   If `git show "$INSTALLED:skills/<name>/SKILL.md"` exits non-zero (the skill
   is absent at INSTALLED — i.e. it is newly added in LATEST) AND a deployed
   `~/.claude/skills/<name>/SKILL.md` already exists, treat it as drifted/at-
   risk so it gets backed up before step 9 overwrites it. Example for a script:
   `diff --strip-trailing-cr <(git -C "$REPO" show "$INSTALLED:scripts/<f>") "$VAULT/.claude/scripts/<f>"`.
   Apply the same CRLF-agnostic pattern for templates, commands, and each skill.
   Do not limit the check to scripts only. If any file in any category differs,
   warn the user that local edits exist, point them to the `kennisbank-contribute`
   skill, and ask whether to proceed (local edits will survive only in the backup).
7. On confirmation, back up every deploy-map category that step 6 found to have
   local drift, using the `.pre-$INSTALLED.bak` naming convention:
   - `$VAULT/.claude/scripts` -> `$VAULT/.claude/scripts.pre-$INSTALLED.bak`
   - `$VAULT/04-templates` -> `$VAULT/04-templates.pre-$INSTALLED.bak`
   - `$HOME/.claude/commands` -> `$HOME/.claude/commands.pre-$INSTALLED.bak`
   - For skills: for each skill dir that step 9 will overwrite (every
     `skills/*/` present in LATEST) where a deployed
     `~/.claude/skills/<name>/SKILL.md` exists and its content differs from
     the file step 9 will write, back it up:
     `$HOME/.claude/skills/<name>` -> `$HOME/.claude/skills/<name>.pre-$INSTALLED.bak`.
     This explicitly covers skills that are new in LATEST (absent at INSTALLED)
     but have a pre-existing local file — those are at-risk and must be backed
     up. Only back up a skill dir if the deployed file differs from what step 9
     will write; skip identical ones.
   Only back up a non-skill category if it actually has drift; skip clean ones.
   The backup set provably covers every skill that step 9 will overwrite — no false safety promise.
8. `git -C "$REPO" -c advice.detachedHead=false checkout "$LATEST"`.
9. Deploy by delegating to the installer — it is the single, idempotent-safe
   deploy mechanism (sinds v0.9.0): refresh ALL tooling (scripts/commands/skills/
   templates), register the FULL hookset in `~/.claude/settings.json`
   (interpreter-aware: `py -3` op Windows / `python3` elders; PreToolUse-matcher),
   install the runtime-deps (`sqlite-vec`) onder de juiste interpreter, en draai
   de version-gated migraties (die stempelen `$VAULT/.claude/.kennisbank-schema-version`).
   User-data (`CLAUDE.md`, `kennisbank-embed.json`, bestaande settings-WAARDEN)
   blijft behouden.
   ```bash
   ( cd "$REPO" && KENNISBANK_VAULT="$VAULT" bash setup.sh --yes )
   ```
   Dit vervangt de oude hand-gerolde kopie: zonder dit zou een upgrade de nieuwe
   scripts deployen maar de hooks NIET registreren en de deps NIET installeren —
   de feature shipt dan dood. setup.sh ververst ook de kennisbank-* skills zelf;
   als hun gedrag veranderde, her-invoke de relevante skill.
10. Write `$VAULT/.claude/.kennisbank-version` (de RELEASE-tag-stamp; los van de
    migratie-schema-stamp `.kennisbank-schema-version` die setup.sh in stap 9 zet):
    `{"tag":"$LATEST","commit":"<git rev-parse --short $LATEST>","installed_at":"<UTC ISO 8601>"}`.
11. `git -C "$REPO" checkout -` (return to the previously checked-out branch,
    regardless of its name).
12. Run `bash "$VAULT/.claude/scripts/doctor.sh"` and report the PASS count.

## Ensure settings and ask for missing toggles

Resolve `VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`.

Stap 9's `setup.sh` heeft `kennisbank-settings.json` al gebootstrapt (defaults) of
additief gemigreerd (ontbrekende toggles toegevoegd, bestaande WAARDEN behouden).
Toon daarom de huidige waarden en bied aan ze te tunen — niet "vraag-indien-afwezig".
Lees elke canonieke toggle's huidige waarde:

```bash
for key in auto_archive distill_notify embed_index daily_graphify memory_capture memory_recall; do
  echo "$key=$(python3 "$VAULT/.claude/scripts/_settings.py" get "$key")"
done
```

If the file does not exist yet (every value falls back to its default and
`$VAULT/kennisbank-settings.json` is absent), ask the user PER toggle whether to
enable it, suggesting the default:

- auto_archive (default OFF) - archive the transcript at session end
- distill_notify (default ON) - notify at start that transcripts are pending
- embed_index (default ON) - refresh the wiki embedding cache at start
- daily_graphify (default ON) - update the graph automatically once a day
- memory_capture (default ON) - extract and judge memories into 09-memory/ with maintenance
- memory_recall (default ON) - inject memories into context via hook and local MCP

Write each choice with `python3 "$VAULT/.claude/scripts/_settings.py" set <key> <true|false>`.
Do NOT re-ask keys that are already set. Mention afterwards that the user can
change this later with `/kennisbank:settings`.

BEHAVIOUR CHANGE: after this upgrade the hook only archives when `auto_archive`
is ON. Ask for it explicitly, otherwise the transcript archive stops silently.

## Geheugen-backfill (eenmalig, bij upgrade naar de geheugen-versie)

Als `memory_capture` aan staat en er al transcripts in `01-raw/transcripts/`
staan, bied aan de bestaande backlog te her-extraheren tot geheugen:

> "Er staan N gearchiveerde transcripts. Wil je die nu eenmalig tot geheugen
> verwerken (`/kennisbank:rebuild-memory`)? Dit is zwaar LLM-werk maar idempotent."

Pas na bevestiging:

```bash
python3 "$VAULT/.claude/scripts/memory-sweep.py" --all
```

Idempotent via dedup; herhaald draaien maakt geen dubbele memories. Sla over als
de gebruiker nee zegt of als Ollama/het LLM niet draait.

## Dry-run
If invoked with `--dry-run`, perform steps 1-6 and print the planned copies and
backups, but make no writes (no backup, no copy, no stamp, no checkout side
effects beyond fetch).
