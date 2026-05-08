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
#   -h, --help         toon usage en stop

set -e

# CLI argumenten parsen
ASSUME_YES=0
NO_COMMANDS=0
NO_SKILL=0

usage() {
  cat <<'USAGE'
Usage: bash setup.sh [opties]

Opties:
  -y, --yes          beantwoord alle prompts met ja (niet-interactief)
  --no-commands      sla het kopiëren van commands over
  --no-skill         sla het kopiëren van de autoresearch skill over
  -h, --help         toon deze hulp en stop

Voorbeelden:
  bash setup.sh
  bash setup.sh --yes
  bash setup.sh --yes --no-skill
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

VAULT="$HOME/KennisBank"
RESEARCH="$HOME/Claude/research"
CLAUDE_COMMANDS="$HOME/.claude/commands"
CLAUDE_SKILLS="$HOME/.claude/skills"

echo "LLmWiki-KennisBank setup"
echo "========================"

# Vault directories
mkdir -p "$VAULT"/{00-inbox,01-raw/sessies,02-wiki,03-projecten,04-templates,05-bronnen,06-claude,07-media,08-archive}
mkdir -p "$VAULT/.claude/scripts"
mkdir -p "$VAULT/graphify-out"

# Research output dir
mkdir -p "$RESEARCH"

# Scripts
cp scripts/*.py "$VAULT/.claude/scripts/"
chmod +x "$VAULT/.claude/scripts/"*.py

# Templates
cp templates/*.md "$VAULT/04-templates/"

# CLAUDE.md (only if not already present)
if [ ! -f "$VAULT/CLAUDE.md" ]; then
  cp CLAUDE.md.template "$VAULT/CLAUDE.md"
  echo "CLAUDE.md aangemaakt in $VAULT — vul [YOUR NAME] en [YOUR PROJECTS] in."
fi

# Commands and skill (with confirmation, of via flags)
if [ "$NO_COMMANDS" = "1" ]; then
  echo "Commands overgeslagen (--no-commands)."
elif [ "$ASSUME_YES" = "1" ]; then
  mkdir -p "$CLAUDE_COMMANDS"
  cp commands/*.md "$CLAUDE_COMMANDS/"
  echo "Commands gekopieerd naar $CLAUDE_COMMANDS/."
else
  printf "Commands kopiëren naar %s/? (y/n) " "$CLAUDE_COMMANDS"
  read REPLY
  if [ "$REPLY" = "y" ] || [ "$REPLY" = "Y" ]; then
    mkdir -p "$CLAUDE_COMMANDS"
    cp commands/*.md "$CLAUDE_COMMANDS/"
  fi
fi

if [ "$NO_SKILL" = "1" ]; then
  echo "autoresearch skill overgeslagen (--no-skill)."
elif [ "$ASSUME_YES" = "1" ]; then
  mkdir -p "$CLAUDE_SKILLS/autoresearch"
  cp skills/autoresearch/SKILL.md "$CLAUDE_SKILLS/autoresearch/"
  echo "autoresearch skill gekopieerd naar $CLAUDE_SKILLS/autoresearch/."
else
  printf "autoresearch skill kopiëren naar %s/autoresearch/? (y/n) " "$CLAUDE_SKILLS"
  read REPLY
  if [ "$REPLY" = "y" ] || [ "$REPLY" = "Y" ]; then
    mkdir -p "$CLAUDE_SKILLS/autoresearch"
    cp skills/autoresearch/SKILL.md "$CLAUDE_SKILLS/autoresearch/"
  fi
fi

echo ""
echo "Klaar. Volgende stappen:"
echo "0. Verifieer de installatie: bash scripts/doctor.sh"
echo "1. Bewerk ~/KennisBank/CLAUDE.md — vul je naam en projecten in"
echo "2. Voeg /autoresearch toe aan je globale ~/.claude/CLAUDE.md (zie README.md)"
echo "3. Optioneel: ollama pull nomic-embed-text (voor semantic tiling)"
