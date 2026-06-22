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

usage() {
  cat <<'USAGE'
Usage: bash setup.sh [opties]

Opties:
  -y, --yes          beantwoord alle prompts met ja (niet-interactief)
  --no-commands      sla het kopiëren van commands over
  --no-skill         sla het kopiëren van de skills (autoresearch, kennisbank-upgrade, kennisbank-contribute) over
  --no-hooks         sla het registreren van de retrieval-hooks in ~/.claude/settings.json over
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

VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"
RESEARCH="$HOME/Claude/research"
CLAUDE_COMMANDS="$HOME/.claude/commands"
CLAUDE_SKILLS="$HOME/.claude/skills"
CLAUDE_SETTINGS="$HOME/.claude/settings.json"

echo "LLmWiki-KennisBank setup"
echo "========================"

# Vault directories
mkdir -p "$VAULT"/{00-inbox,01-raw/sessies,02-wiki,03-projecten,04-templates,05-bronnen,06-claude,07-media,08-archive}
mkdir -p "$VAULT/.claude/scripts"
mkdir -p "$VAULT/graphify-out"

# Research output dir
mkdir -p "$RESEARCH"

# Scripts (Python helpers + shell tools like doctor.sh)
for f in scripts/*.py scripts/*.sh; do
  copy_file "$f" "$VAULT/.claude/scripts/$(basename "$f")"
done
chmod +x "$VAULT/.claude/scripts/"*.py "$VAULT/.claude/scripts/"*.sh

# Embedding backend config (example -> live). copy_file skips if it already
# exists (unless --force), so a user's edited backend config is never clobbered.
copy_file kennisbank-embed.example.json "$VAULT/.claude/kennisbank-embed.json"

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
if [ "$NO_COMMANDS" = "1" ]; then
  echo "Commands overgeslagen (--no-commands)."
elif [ "$ASSUME_YES" = "1" ]; then
  mkdir -p "$CLAUDE_COMMANDS"
  for f in commands/*.md; do
    copy_file "$f" "$CLAUDE_COMMANDS/$(basename "$f")"
  done
else
  printf "Commands kopiëren naar %s/? (y/n) " "$CLAUDE_COMMANDS"
  read REPLY
  if [ "$REPLY" = "y" ] || [ "$REPLY" = "Y" ]; then
    mkdir -p "$CLAUDE_COMMANDS"
    for f in commands/*.md; do
      copy_file "$f" "$CLAUDE_COMMANDS/$(basename "$f")"
    done
  fi
fi

if [ "$NO_SKILL" = "1" ]; then
  echo "Skills overgeslagen (--no-skill)."
elif [ "$ASSUME_YES" = "1" ]; then
  for sdir in skills/*/; do
    sname="$(basename "$sdir")"
    mkdir -p "$CLAUDE_SKILLS/$sname"
    copy_file "${sdir}SKILL.md" "$CLAUDE_SKILLS/$sname/SKILL.md"
  done
else
  printf "Skills kopiëren naar %s/? (y/n) " "$CLAUDE_SKILLS"
  read REPLY
  if [ "$REPLY" = "y" ] || [ "$REPLY" = "Y" ]; then
    for sdir in skills/*/; do
      sname="$(basename "$sdir")"
      mkdir -p "$CLAUDE_SKILLS/$sname"
      copy_file "${sdir}SKILL.md" "$CLAUDE_SKILLS/$sname/SKILL.md"
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
    echo "  WAARSCHUWING: python3 niet gevonden; hooks niet geregistreerd."
    echo "  Registreer later handmatig (zie CONFIGURATION.md, sectie 4)."
    return 0
  fi
  mkdir -p "$HOME/.claude"
  python3 "$VAULT/.claude/scripts/register-hooks.py" "$CLAUDE_SETTINGS" \
    SessionStart "$VAULT/.claude/scripts/build-embed-index.py" \
    UserPromptSubmit "$VAULT/.claude/scripts/kb-retrieve.py" \
    || echo "  hooks niet geregistreerd (zie melding hierboven); registreer handmatig (CONFIGURATION.md)." >&2
}

if [ "$NO_HOOKS" = "1" ]; then
  echo "Hooks overgeslagen (--no-hooks)."
elif [ "$ASSUME_YES" = "1" ]; then
  register_hooks
else
  printf "Retrieval-hooks registreren in %s? (y/n) " "$CLAUDE_SETTINGS"
  read REPLY
  if [ "$REPLY" = "y" ] || [ "$REPLY" = "Y" ]; then
    register_hooks
  fi
fi

echo ""
echo "Klaar. Volgende stappen:"
echo "0. Verifieer de installatie: bash scripts/doctor.sh"
echo "1. Bewerk ~/KennisBank/CLAUDE.md  -  vul je naam en projecten in"
echo "2. Voeg /autoresearch toe aan je globale ~/.claude/CLAUDE.md (zie README.md)"
echo "3. Optioneel: ollama pull qwen3-embedding:8b (meertalig, voor semantic tiling; Engels-only? ollama pull nomic-embed-text)"
echo "4. De retrieval-hooks zijn geregistreerd in ~/.claude/settings.json; ze warmen de embed-cache bij elke nieuwe sessie. Sla over met --no-hooks."
