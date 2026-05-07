#!/bin/bash
# Setup script voor LLmWiki-KennisBank
# Maakt de vault-directorystructuur aan en kopieert scripts/templates

set -e

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

# Commands and skill (with confirmation)
read -p "Commands kopiëren naar $CLAUDE_COMMANDS/? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  mkdir -p "$CLAUDE_COMMANDS"
  cp commands/*.md "$CLAUDE_COMMANDS/"
fi

read -p "autoresearch skill kopiëren naar $CLAUDE_SKILLS/autoresearch/? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  mkdir -p "$CLAUDE_SKILLS/autoresearch"
  cp skills/autoresearch/SKILL.md "$CLAUDE_SKILLS/autoresearch/"
fi

echo ""
echo "Klaar. Volgende stappen:"
echo "1. Bewerk ~/KennisBank/CLAUDE.md — vul je naam en projecten in"
echo "2. Voeg /autoresearch toe aan je globale ~/.claude/CLAUDE.md (zie README.md)"
echo "3. Optioneel: ollama pull nomic-embed-text (voor semantic tiling)"
