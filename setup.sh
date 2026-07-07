#!/usr/bin/env bash
# Setup script voor LLmWiki-KennisBank
# Maakt de vault-directorystructuur aan en kopieert scripts/templates
# Vereist bash (niet sh): bash setup.sh
#
# Gebruik:
#   bash setup.sh                       # interactief (vraagt bij commands en skill)
#   bash setup.sh --yes                 # niet-interactief, installeert alles
#   bash setup.sh --yes --no-skill      # niet-interactief, slaat skill over
#   bash setup.sh --no-commands         # interactief, maar slaat commands over
#   bash setup.sh -h                    # toon usage
#
# Flags:
#   -y, --yes          beantwoord alle prompts met ja
#   --no-commands      sla het kopiëren van commands over (heeft voorrang op --yes)
#   --no-skill         sla het kopiëren van de autoresearch skill over (heeft voorrang op --yes)
#   --no-hooks         sla het registreren van de retrieval-hooks over (heeft voorrang op --yes)
#   --agents LIST      agentdoelen: claude,codex,opencode,all (default: claude,codex)
#   --no-codex         alias voor --agents claude
#   --skip-model-check sla Ollama model-smoke-tests over in de post-install validatie
#   -f, --force        overschrijf bestaande bestanden
#   -h, --help         toon usage en stop

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Maak lege globs veilig: een patroon zonder matches expandeert nu naar niets
# in plaats van naar de letterlijke string. Voorkomt cp-fouten onder set -e.
shopt -s nullglob

# CLI argumenten parsen
ASSUME_YES=0
NO_COMMANDS=0
NO_SKILL=0
NO_HOOKS=0
FORCE=0
AGENTS="claude,codex"
AGENTS_SET=0
SKIP_MODEL_CHECK=0

usage() {
  cat <<'USAGE'
Usage: bash setup.sh [opties]

Opties:
  -y, --yes          beantwoord alle prompts met ja (niet-interactief)
  --no-commands      sla het kopiëren van commands over
  --no-skill         sla het kopiëren van de skills (autoresearch, kennisbank-upgrade, kennisbank-contribute) over
  --no-hooks         sla het registreren van de retrieval-hooks in ~/.claude/settings.json over
  --agents LIST      installeer agent-integraties voor LIST: claude,codex,opencode,all
  --no-codex         installeer alleen Claude Code-integratie (compatibiliteitsalias)
  --skip-model-check sla lokale Ollama model-smoke-tests over tijdens post-install validatie
  -f, --force        overschrijf bestaande bestanden (scripts, templates, commands, skill, CLAUDE.md)
  -h, --help         toon deze hulp en stop

Voorbeelden:
  bash setup.sh
  bash setup.sh --yes
  bash setup.sh --yes --no-skill
  bash setup.sh --yes --force
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    -y|--yes)
      ASSUME_YES=1
      ;;
    --no-commands)
      NO_COMMANDS=1
      ;;
    --no-skill)
      NO_SKILL=1
      ;;
    --no-hooks)
      NO_HOOKS=1
      ;;
    --agents)
      shift
      if [ $# -eq 0 ]; then
        echo "--agents verwacht een waarde (claude,codex,opencode,all)" >&2
        exit 1
      fi
      AGENTS="$1"
      AGENTS_SET=1
      ;;
    --no-codex)
      AGENTS="claude"
      AGENTS_SET=1
      ;;
    --skip-model-check)
      SKIP_MODEL_CHECK=1
      ;;
    -f|--force)
      FORCE=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Onbekende optie: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

AGENTS="$(printf "%s" "$AGENTS" | tr '[:upper:]' '[:lower:]' | tr -d ' ')"
if [ "$ASSUME_YES" != "1" ] && [ "$AGENTS_SET" != "1" ]; then
  printf "Agent-integraties installeren voor welke omgevingen? [claude,codex] (opties: claude,codex,opencode,all) "
  read REPLY
  if [ -n "$REPLY" ]; then
    AGENTS="$(printf "%s" "$REPLY" | tr '[:upper:]' '[:lower:]' | tr -d ' ')"
  fi
fi

has_agent() {
  case ",$AGENTS," in
    *",all,"*) return 0 ;;
    *",$1,"*) return 0 ;;
    *) return 1 ;;
  esac
}

# copy_file SRC DST
# Kopieert SRC naar DST. Als FORCE=1, overschrijft. Anders, slaat over als DST bestaat.
copy_file() {
  local src="$1"
  local dst="$2"
  if [ -f "$dst" ] && [ "$FORCE" != "1" ]; then
    echo "  behouden: $dst (bestaat al; gebruik --force om te overschrijven)"
    return 0
  fi
  cp "$src" "$dst"
  echo "  gekopieerd: $dst"
}

# copy_force SRC DST -- altijd (over)kopieren. Voor TOOLING (scripts/commands/
# skills): geen user-data, dus altijd de repo-versie. User-data blijft copy_file.
copy_force() {
  cp "$1" "$2"
  echo "  ververst: $2"
}

VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"
RESEARCH="$HOME/Claude/research"
CLAUDE_COMMANDS="$HOME/.claude/commands"
CLAUDE_SKILLS="$HOME/.claude/skills"
CLAUDE_SETTINGS="$HOME/.claude/settings.json"

echo "LLmWiki-KennisBank setup"
echo "========================"

# Vault directories
mkdir -p "$VAULT"/{00-inbox,01-raw/sessies,01-raw/transcripts,02-wiki,03-projecten,04-templates,05-bronnen,06-claude,07-media,08-archive,09-memory,09-memory/archive}
mkdir -p "$VAULT/.claude/scripts"
mkdir -p "$VAULT/graphify-out"

# Research output dir
mkdir -p "$RESEARCH"

# Scripts (Python helpers + shell tools like doctor.sh)
for f in scripts/*.py scripts/*.sh; do
  copy_force "$f" "$VAULT/.claude/scripts/$(basename "$f")"
done
chmod +x "$VAULT/.claude/scripts/"*.py "$VAULT/.claude/scripts/"*.sh

# Embedding backend config (example -> live). copy_file skips if it already
# exists (unless --force), so a user's edited backend config is never clobbered.
copy_file kennisbank-embed.example.json "$VAULT/.claude/kennisbank-embed.json"
copy_file kennisbank-llm.example.json "$VAULT/.claude/kennisbank-llm.json"

configure_llm_backend() {
  if [ "$ASSUME_YES" = "1" ] || [ ! -t 0 ]; then
    return 0
  fi
  local backend model key_env key_value store_reply
  printf "LLM-backend voor memory judge/extractie? [ollama] (opties: ollama, openrouter) "
  read backend
  backend="$(printf "%s" "${backend:-ollama}" | tr '[:upper:]' '[:lower:]' | tr -d ' ')"
  case "$backend" in
    ""|ollama)
      printf "Ollama model tag? [gemma4:latest] "
      read model
      if [ -n "$model" ]; then
        python3 "$SCRIPT_DIR/scripts/install-agent-envs.py" \
          --vault "$VAULT" --agents "$AGENTS" --configure-llm \
          --llm-provider ollama --llm-model "$model"
      else
        python3 "$SCRIPT_DIR/scripts/install-agent-envs.py" \
          --vault "$VAULT" --agents "$AGENTS" --configure-llm \
          --llm-provider ollama
      fi
      ;;
    openrouter)
      echo "  LET OP: OpenRouter is een externe cloud-API; memory-sweep content verlaat je machine."
      printf "OpenRouter model slug? [openai/gpt-5.2] "
      read model
      model="${model:-openai/gpt-5.2}"
      printf "API-key env var naam? [OPENROUTER_API_KEY] "
      read key_env
      key_env="${key_env:-OPENROUTER_API_KEY}"
      case "$key_env" in
        ""|[0-9]*|*[!A-Za-z0-9_]*)
          echo "Ongeldige env-varnaam voor API key: $key_env" >&2
          return 1
          ;;
      esac
      if [ -z "${!key_env:-}" ]; then
        printf "Geen %s in deze shell. API key nu invoeren en user-local opslaan in ~/.config/kennisbank/secrets.json? [y/N] " "$key_env"
        read store_reply
        if [ "$store_reply" = "y" ] || [ "$store_reply" = "Y" ]; then
          printf "OpenRouter API key: "
          read -r -s key_value
          printf "\n"
        fi
      fi
      if [ -n "${key_value:-}" ]; then
        KENNISBANK_OPENROUTER_API_KEY_TO_STORE="$key_value" \
          python3 "$SCRIPT_DIR/scripts/install-agent-envs.py" \
            --vault "$VAULT" --agents "$AGENTS" --configure-llm \
            --llm-provider openrouter --llm-model "$model" \
            --llm-api-key-env "$key_env"
      else
        python3 "$SCRIPT_DIR/scripts/install-agent-envs.py" \
          --vault "$VAULT" --agents "$AGENTS" --configure-llm \
          --llm-provider openrouter --llm-model "$model" \
          --llm-api-key-env "$key_env"
      fi
      ;;
    *)
      echo "Onbekende LLM-backend: $backend (gebruik ollama of openrouter)" >&2
      return 1
      ;;
  esac
}

configure_llm_backend

# Python-afhankelijkheden (sqlite-vec voor kb-index)
# F3: op Windows draait py -3 (de hooks-interpreter); gebruik diezelfde interpreter
# voor pip zodat sqlite-vec in dezelfde omgeving terechtkomt.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) PIP_PYTHON="py -3" ;;
  *) PIP_PYTHON="python3" ;;
esac
$PIP_PYTHON -m pip install --quiet "sqlite-vec==0.1.9" 2>/dev/null \
  || echo "  (let op: '$PIP_PYTHON -m pip install sqlite-vec==0.1.9' handmatig nodig voor kb-index)"

# Settings-bootstrap: zorg dat kennisbank-settings.json bestaat. De toggles
# bepalen welke achtergrond-automatiek draait (auto-archive, distill-notify,
# embed-index, daily-graphify). Interactief vragen we per toggle; niet-
# interactief (--yes of geen TTY) schrijven we de defaults.
SETTINGS_FILE="$VAULT/kennisbank-settings.json"
if [ -f "$SETTINGS_FILE" ]; then
  echo "  behouden: $SETTINGS_FILE (bestaat al)"
elif [ "$ASSUME_YES" = "1" ] || [ ! -t 0 ]; then
  python3 "$VAULT/.claude/scripts/_settings.py" init >/dev/null \
    && echo "  settings: defaults geschreven naar $SETTINGS_FILE (draai /kennisbank:settings om aan te passen)"
else
  echo "Achtergrond-automatiek instellen (Enter = default):"
  # auto_archive default uit, de rest aan. read met default-hint.
  ask_toggle() {
    local key="$1" prompt="$2" def="$3" reply
    printf "  %s [%s] (y/n) " "$prompt" "$([ "$def" = "1" ] && echo "Y/n" || echo "y/N")"
    read reply
    if [ -z "$reply" ]; then reply="$def"; fi
    case "$reply" in
      y|Y|1) python3 "$VAULT/.claude/scripts/_settings.py" set "$key" true >/dev/null ;;
      *)     python3 "$VAULT/.claude/scripts/_settings.py" set "$key" false >/dev/null ;;
    esac
  }
  ask_toggle auto_archive   "transcripts archiveren bij sessie-einde (auto_archive)" 0
  ask_toggle distill_notify "melden bij start dat transcripts wachten (distill_notify)" 1
  ask_toggle embed_index    "wiki-embeddings verversen bij start (embed_index)" 1
  ask_toggle daily_graphify "1x/dag graph automatisch bijwerken (daily_graphify)" 1
  echo "  settings: keuze opgeslagen in $SETTINGS_FILE"
fi

# Templates
for f in templates/*.md; do
  copy_file "$f" "$VAULT/04-templates/$(basename "$f")"
done

# CLAUDE.md (alleen als nog niet aanwezig, tenzij --force)
if [ -f "$VAULT/CLAUDE.md" ]; then
  claude_md_was_present=1
else
  claude_md_was_present=0
fi
copy_file CLAUDE.md.template "$VAULT/CLAUDE.md"
if [ "$claude_md_was_present" = "0" ] && [ -f "$VAULT/CLAUDE.md" ]; then
  echo "CLAUDE.md aangemaakt in $VAULT  -  vul [YOUR NAME] en [YOUR PROJECTS] in."
elif [ "$claude_md_was_present" = "1" ] && [ "$FORCE" = "1" ]; then
  echo "WAARSCHUWING: bestaande CLAUDE.md overschreven met template. Eventuele aanpassingen zijn verloren."
fi

# Commands and skill (with confirmation, of via flags)
if ! has_agent claude; then
  echo "Claude Code commands overgeslagen (--agents bevat geen claude)."
elif [ "$NO_COMMANDS" = "1" ]; then
  echo "Commands overgeslagen (--no-commands)."
elif [ "$ASSUME_YES" = "1" ]; then
  mkdir -p "$CLAUDE_COMMANDS"
  for f in commands/*.md; do
    copy_force "$f" "$CLAUDE_COMMANDS/$(basename "$f")"
  done
  # Genamespacede commands (bv. commands/kennisbank/settings.md -> /kennisbank:settings)
  for f in commands/*/*.md; do
    rel="${f#commands/}"
    mkdir -p "$CLAUDE_COMMANDS/$(dirname "$rel")"
    copy_force "$f" "$CLAUDE_COMMANDS/$rel"
  done
else
  printf "Commands kopiëren naar %s/? (y/n) " "$CLAUDE_COMMANDS"
  read REPLY
  if [ "$REPLY" = "y" ] || [ "$REPLY" = "Y" ]; then
    mkdir -p "$CLAUDE_COMMANDS"
    for f in commands/*.md; do
      copy_force "$f" "$CLAUDE_COMMANDS/$(basename "$f")"
    done
    for f in commands/*/*.md; do
      rel="${f#commands/}"
      mkdir -p "$CLAUDE_COMMANDS/$(dirname "$rel")"
      copy_force "$f" "$CLAUDE_COMMANDS/$rel"
    done
  fi
fi

if ! has_agent claude; then
  echo "Claude Code skills overgeslagen (--agents bevat geen claude)."
elif [ "$NO_SKILL" = "1" ]; then
  echo "Skills overgeslagen (--no-skill)."
elif [ "$ASSUME_YES" = "1" ]; then
  for sdir in skills/*/; do
    sname="$(basename "$sdir")"
    mkdir -p "$CLAUDE_SKILLS/$sname"
    copy_force "${sdir}SKILL.md" "$CLAUDE_SKILLS/$sname/SKILL.md"
  done
else
  printf "Skills kopiëren naar %s/? (y/n) " "$CLAUDE_SKILLS"
  read REPLY
  if [ "$REPLY" = "y" ] || [ "$REPLY" = "Y" ]; then
    for sdir in skills/*/; do
      sname="$(basename "$sdir")"
      mkdir -p "$CLAUDE_SKILLS/$sname"
      copy_force "${sdir}SKILL.md" "$CLAUDE_SKILLS/$sname/SKILL.md"
    done
  fi
fi

# Retrieval hooks: SessionStart warms the wiki embed cache (build-embed-index.py),
# UserPromptSubmit injects matching wiki snippets (kb-retrieve.py). Registered into
# ~/.claude/settings.json by register-hooks.py: idempotent and non-destructive
# (existing hooks/permissions/env are preserved). Without these a fresh install has
# a cold cache and /uitdaag, /brug and /wiki self-rewrite silently find nothing.
register_hooks() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "  WAARSCHUWING: python3 niet gevonden; hooks/migraties niet uitgevoerd."
    echo "  Registreer later handmatig (zie CONFIGURATION.md, sectie 4)."
    return 0
  fi
  mkdir -p "$HOME/.claude"
  python3 "$VAULT/.claude/scripts/register-hooks.py" "$CLAUDE_SETTINGS" --manifest "$VAULT" \
    || echo "  hooks niet geregistreerd (zie melding hierboven); registreer handmatig (CONFIGURATION.md)." >&2
}

if ! has_agent claude; then
  echo "Claude Code hooks overgeslagen (--agents bevat geen claude)."
  NO_HOOKS=1
elif [ "$NO_HOOKS" = "1" ]; then
  echo "Hooks overgeslagen (--no-hooks)."
elif [ "$ASSUME_YES" = "1" ]; then
  register_hooks
else
  printf "Retrieval-hooks registreren in %s? (y/n) " "$CLAUDE_SETTINGS"
  read REPLY
  if [ "$REPLY" = "y" ] || [ "$REPLY" = "Y" ]; then
    register_hooks
  else
    # F5: interactieve 'n' stelt NO_HOOKS=1 zodat ook de migratie --skip-hooks krijgt.
    NO_HOOKS=1
  fi
fi

# Migraties: breng de vault version-gated naar de huidige staat (dirs, hooks,
# toggles) en stempel de versie. Idempotent; fail-soft (breekt setup niet).
if command -v python3 >/dev/null 2>&1; then
  SKIP_HOOKS_ARG=""
  [ "$NO_HOOKS" = "1" ] && SKIP_HOOKS_ARG="--skip-hooks"
  python3 "$VAULT/.claude/scripts/_migrations.py" run "$VAULT" "$CLAUDE_SETTINGS" $SKIP_HOOKS_ARG \
    || echo "  migraties niet (volledig) uitgevoerd; her-run 'bash setup.sh'." >&2
fi

# Agent-integraties (Codex/OpenCode) en harde post-install validatie. Dit is
# idempotent en bedoeld voor zowel initiële installatie als upgrades.
if command -v python3 >/dev/null 2>&1; then
  MODEL_ARG=""
  [ "$SKIP_MODEL_CHECK" = "1" ] && MODEL_ARG="--skip-models"
  python3 "$SCRIPT_DIR/scripts/install-agent-envs.py" \
    --repo "$SCRIPT_DIR" \
    --vault "$VAULT" \
    --agents "$AGENTS" \
    --install \
    --validate \
    $MODEL_ARG
  AGENT_VALIDATE_RC=$?
else
  echo "  WAARSCHUWING: python3 niet gevonden; agent-integraties en validatie overgeslagen." >&2
  AGENT_VALIDATE_RC=1
fi

# doctor.sh blijft read-only, maar setup gebruikt hem als afsluitende gate:
# eerst repareren/configureren, dan diagnosticeren.
if [ -f "$VAULT/.claude/scripts/doctor.sh" ]; then
  KENNISBANK_VAULT="$VAULT" bash "$VAULT/.claude/scripts/doctor.sh"
  DOCTOR_RC=$?
else
  echo "  WAARSCHUWING: doctor.sh ontbreekt na setup." >&2
  DOCTOR_RC=1
fi

if [ "$AGENT_VALIDATE_RC" != "0" ] || [ "$DOCTOR_RC" != "0" ]; then
  echo "" >&2
  echo "Post-install validatie faalde. Corrigeer de meldingen hierboven en draai setup.sh opnieuw." >&2
  exit 1
fi

echo ""
echo "Klaar. Volgende stappen:"
echo "0. Installatie en upgrade-validatie zijn uitgevoerd door setup.sh (doctor + agent/model checks)."
echo "1. Vault: $VAULT"
echo "2. Bewerk $VAULT/CLAUDE.md wanneer je naam/projecten wilt bijwerken."
echo "3. Agentdoelen geconfigureerd: $AGENTS"
echo "4. LLM-backend: Ollama is de default; OpenRouter is alleen actief als je dat expliciet koos in kennisbank-llm.json."
echo "5. De retrieval-hooks zijn geregistreerd in ~/.claude/settings.json wanneer Claude Code in --agents staat; sla registratie over met --no-hooks."
