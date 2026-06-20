#!/usr/bin/env bash
# LLmWiki-KennisBank doctor
# Verifies that the vault, scripts, templates, commands and skill
# are installed and configured correctly. Read-only: never writes
# anything. Run after `bash setup.sh`.

set -u

VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"
RESEARCH="$HOME/Claude/research"
CLAUDE_DIR="$HOME/.claude"
COMMANDS_DIR="$CLAUDE_DIR/commands"
SKILLS_DIR="$CLAUDE_DIR/skills"
GLOBAL_CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
INFO_COUNT=0

# Color setup, only if stdout is a TTY and tput supports it.
if [ -t 1 ] && command -v tput >/dev/null 2>&1 && [ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]; then
  C_GREEN="$(tput setaf 2)"
  C_YELLOW="$(tput setaf 3)"
  C_RED="$(tput setaf 1)"
  C_BLUE="$(tput setaf 4)"
  C_BOLD="$(tput bold)"
  C_RESET="$(tput sgr0)"
else
  C_GREEN=""
  C_YELLOW=""
  C_RED=""
  C_BLUE=""
  C_BOLD=""
  C_RESET=""
fi

report_pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf "%s[PASS]%s %s: %s\n" "$C_GREEN" "$C_RESET" "$1" "$2"
}

report_warn() {
  WARN_COUNT=$((WARN_COUNT + 1))
  printf "%s[WARN]%s %s: %s\n" "$C_YELLOW" "$C_RESET" "$1" "$2"
}

report_fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf "%s[FAIL]%s %s: %s\n" "$C_RED" "$C_RESET" "$1" "$2"
}

report_info() {
  INFO_COUNT=$((INFO_COUNT + 1))
  printf "%s[INFO]%s %s: %s\n" "$C_BLUE" "$C_RESET" "$1" "$2"
}

check_dir() {
  local name="$1"
  local path="$2"
  if [ -d "$path" ]; then
    report_pass "$name" "$path"
  else
    report_fail "$name" "missing directory $path"
  fi
}

check_file() {
  local name="$1"
  local path="$2"
  if [ -f "$path" ]; then
    report_pass "$name" "$path"
  else
    report_fail "$name" "missing file $path"
  fi
}

check_executable() {
  local name="$1"
  local path="$2"
  if [ ! -f "$path" ]; then
    report_fail "$name" "missing file $path"
  elif [ -x "$path" ]; then
    report_pass "$name" "$path"
  else
    # Scripts are invoked via 'python3 path' so the executable bit is cosmetic.
    # Report INFO instead of WARN to avoid alarming users with old installs.
    report_info "$name" "$path (not chmod +x, but invoked via python3 so harmless)"
  fi
}

printf "%sLLmWiki-KennisBank doctor%s\n" "$C_BOLD" "$C_RESET"
printf "==========================\n\n"

# 1. Vault root.
check_dir "vault root" "$VAULT"

# 2. Vault subdirectories.
SUBDIRS="00-inbox 01-raw/sessies 02-wiki 03-projecten 04-templates 05-bronnen 06-claude 07-media 08-archive .claude/scripts graphify-out"
for sub in $SUBDIRS; do
  check_dir "vault subdir $sub" "$VAULT/$sub"
done

# 3. Vault CLAUDE.md present and placeholders replaced.
VAULT_CLAUDE_MD="$VAULT/CLAUDE.md"
if [ ! -f "$VAULT_CLAUDE_MD" ]; then
  report_fail "vault CLAUDE.md" "missing $VAULT_CLAUDE_MD"
else
  PLACEHOLDERS=""
  if grep -q "\[YOUR NAME\]" "$VAULT_CLAUDE_MD" 2>/dev/null; then
    PLACEHOLDERS="$PLACEHOLDERS [YOUR NAME]"
  fi
  if grep -q "\[YOUR PROJECTS" "$VAULT_CLAUDE_MD" 2>/dev/null; then
    PLACEHOLDERS="$PLACEHOLDERS [YOUR PROJECTS]"
  fi
  if [ -n "$PLACEHOLDERS" ]; then
    report_warn "vault CLAUDE.md" "still contains placeholders:$PLACEHOLDERS"
  else
    report_pass "vault CLAUDE.md" "placeholders replaced"
  fi
fi

# 4. Templates present.
check_file "template tpl-sessie-log.md" "$VAULT/04-templates/tpl-sessie-log.md"
check_file "template tpl-wiki-artikel.md" "$VAULT/04-templates/tpl-wiki-artikel.md"

# 5. Scripts present and executable.
SCRIPTS_DIR="$VAULT/.claude/scripts"
if [ ! -d "$SCRIPTS_DIR" ]; then
  report_fail "scripts dir" "missing $SCRIPTS_DIR"
else
  found_any_script=0
  for py in "$SCRIPTS_DIR"/*.py; do
    if [ -f "$py" ]; then
      found_any_script=1
      check_executable "script $(basename "$py")" "$py"
    fi
  done
  if [ "$found_any_script" -eq 0 ]; then
    report_fail "scripts dir" "no .py files found in $SCRIPTS_DIR"
  fi
fi

# 6. Research dir.
if [ -d "$RESEARCH" ]; then
  report_pass "research dir" "$RESEARCH"
else
  report_warn "research dir" "missing $RESEARCH (autoresearch output target)"
fi

# 7. Slash commands installed.
COMMAND_FILES="sessielog wiki intake stale sessiestart import"
if [ ! -d "$COMMANDS_DIR" ]; then
  report_warn "commands dir" "$COMMANDS_DIR not found (user may have opted out)"
else
  for cmd in $COMMAND_FILES; do
    cmd_path="$COMMANDS_DIR/$cmd.md"
    if [ -f "$cmd_path" ]; then
      report_pass "command /$cmd" "$cmd_path"
    else
      report_warn "command /$cmd" "missing $cmd_path"
    fi
  done
fi

# 8. autoresearch skill installed.
AUTORESEARCH_SKILL="$SKILLS_DIR/autoresearch/SKILL.md"
if [ -f "$AUTORESEARCH_SKILL" ]; then
  report_pass "autoresearch skill" "$AUTORESEARCH_SKILL"
else
  report_warn "autoresearch skill" "missing $AUTORESEARCH_SKILL (user may have opted out)"
fi

# 9. autoresearch trigger snippet in global CLAUDE.md.
if [ ! -f "$GLOBAL_CLAUDE_MD" ]; then
  report_info "global CLAUDE.md" "no $GLOBAL_CLAUDE_MD (optional)"
else
  if grep -q "/autoresearch" "$GLOBAL_CLAUDE_MD" 2>/dev/null; then
    report_pass "autoresearch trigger" "found in $GLOBAL_CLAUDE_MD"
  else
    report_warn "autoresearch trigger" "no /autoresearch snippet in $GLOBAL_CLAUDE_MD (see README customization step 7)"
  fi
fi

# 10. Memory directory (info-level).
MEMORY_PATH="$(ls "$CLAUDE_DIR"/projects/*/memory/MEMORY.md 2>/dev/null | head -1)"
if [ -n "$MEMORY_PATH" ]; then
  report_pass "memory index" "$MEMORY_PATH"
else
  report_info "memory index" "no MEMORY.md under $CLAUDE_DIR/projects/*/memory/ yet (created on first session)"
fi

# 11. Python 3.10+.
if ! command -v python3 >/dev/null 2>&1; then
  report_fail "python3" "not found in PATH"
else
  PY_VERSION="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)"
  PY_MAJOR="$(printf "%s" "$PY_VERSION" | cut -d. -f1)"
  PY_MINOR="$(printf "%s" "$PY_VERSION" | cut -d. -f2)"
  if [ -z "$PY_VERSION" ]; then
    report_fail "python3" "could not determine version"
  elif [ "$PY_MAJOR" -gt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 10 ]; }; then
    report_pass "python3" "version $PY_VERSION"
  else
    report_fail "python3" "version $PY_VERSION found, need 3.10+"
  fi
fi

# 12. Ollama and the embedding model (optional).
# Default is qwen3-embedding:8b (multilingual); nomic-embed-text is the
# lighter English-only fallback. Respect OLLAMA_EMBED_MODEL if the user set it.
if ! command -v ollama >/dev/null 2>&1; then
  report_info "ollama" "not installed (optional, needed for semantic tiling)"
else
  EMBED_MODEL="${OLLAMA_EMBED_MODEL:-qwen3-embedding:8b}"
  if ollama list 2>/dev/null | grep -qF "$EMBED_MODEL"; then
    report_info "ollama $EMBED_MODEL" "installed"
  else
    report_info "ollama $EMBED_MODEL" "model not pulled (run: ollama pull $EMBED_MODEL)"
  fi
fi

# Footer.
printf "\n%sSummary%s\n" "$C_BOLD" "$C_RESET"
printf "  %s[PASS]%s %d\n" "$C_GREEN" "$C_RESET" "$PASS_COUNT"
printf "  %s[WARN]%s %d\n" "$C_YELLOW" "$C_RESET" "$WARN_COUNT"
printf "  %s[FAIL]%s %d\n" "$C_RED" "$C_RESET" "$FAIL_COUNT"
printf "  %s[INFO]%s %d\n" "$C_BLUE" "$C_RESET" "$INFO_COUNT"

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi
exit 0
