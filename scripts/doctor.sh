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

# 5b. Vault-onderhoud layer scripts (explicit named check).
ONDERHOUD_SCRIPTS="safe-edit.py find-similar.py kb-search.py conflict-scan.py context-budget.py"
for s in $ONDERHOUD_SCRIPTS; do
  check_file "vault-onderhoud script $s" "$SCRIPTS_DIR/$s"
done

# 6. Research dir.
if [ -d "$RESEARCH" ]; then
  report_pass "research dir" "$RESEARCH"
else
  report_warn "research dir" "missing $RESEARCH (autoresearch output target)"
fi

# 7. Slash commands installed.
COMMAND_FILES="sessielog wiki intake stale sessiestart import reconcile uitdaag brug weeklog timeline watdeedik"
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

# 11a. LiteParse is optional but powers document intake. Match setup.sh's
# interpreter choice so Windows installs via py -3 are checked correctly.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) LITEPARSE_PY=(py -3) ;;
  *) LITEPARSE_PY=(python3) ;;
esac
if command -v "${LITEPARSE_PY[0]}" >/dev/null 2>&1; then
  if "${LITEPARSE_PY[@]}" -c 'import liteparse' >/dev/null 2>&1; then
    LP_VER="$("${LITEPARSE_PY[@]}" -c 'import importlib.metadata; print(importlib.metadata.version("liteparse"))' 2>/dev/null)"
    report_pass "liteparse" "${LITEPARSE_PY[*]} version ${LP_VER:-unknown}"
  else
    report_warn "liteparse" "niet gevonden; document-intake mist PDF/Office/image parsing. Fix: ${LITEPARSE_PY[*]} -m pip install \"liteparse>=2.0,<3\""
  fi
fi

# 11a-bis. dateparser powers the optional global-language temporal fallback
# (Layer 2 of activity recall). Without it, /watdeedik still supports the
# deterministic locale layer (nl/en/de/fr/es/it); other languages fall through.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) DATEPARSER_PY=(py -3) ;;
  *) DATEPARSER_PY=(python3) ;;
esac
if command -v "${DATEPARSER_PY[0]}" >/dev/null 2>&1; then
  if "${DATEPARSER_PY[@]}" -c 'import dateparser' >/dev/null 2>&1; then
    DP_VER="$("${DATEPARSER_PY[@]}" -c 'import dateparser; print(dateparser.__version__)' 2>/dev/null)"
    report_pass "dateparser" "${DATEPARSER_PY[*]} version ${DP_VER:-unknown}"
  else
    report_warn "dateparser" "niet gevonden; temporele recall dekt alleen nl/en/de/fr/es/it. Fix: ${DATEPARSER_PY[*]} -m pip install \"dateparser>=1.2,<2\" \"babel>=2.12\""
  fi
fi

# 11b. MCP runtime, required when Codex/OpenCode/Copilot KennisBank MCP is configured.
MCP_CONFIGURED=0
CODEX_CONFIG="$HOME/.codex/config.toml"
OPENCODE_CONFIG="$HOME/.config/opencode/opencode.json"
COPILOT_HOME_DIR="${COPILOT_HOME:-$HOME/.copilot}"
COPILOT_MCP_CONFIG="$COPILOT_HOME_DIR/mcp-config.json"
if [ -f "$CODEX_CONFIG" ] && grep -q "\[mcp_servers\.kennisbank\]" "$CODEX_CONFIG" 2>/dev/null; then
  MCP_CONFIGURED=1
fi
if [ -f "$OPENCODE_CONFIG" ] && grep -q '"kennisbank"' "$OPENCODE_CONFIG" 2>/dev/null && grep -q '"mcp"' "$OPENCODE_CONFIG" 2>/dev/null; then
  MCP_CONFIGURED=1
fi
if [ -f "$COPILOT_MCP_CONFIG" ] && grep -q '"kennisbank"' "$COPILOT_MCP_CONFIG" 2>/dev/null; then
  MCP_CONFIGURED=1
fi
if [ "$MCP_CONFIGURED" = "0" ]; then
  report_info "kennisbank MCP runtime" "not configured for Codex/OpenCode"
else
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) MCP_PY=(py -3) ;;
    *) MCP_PY=(python3) ;;
  esac
  if ! command -v "${MCP_PY[0]}" >/dev/null 2>&1; then
    report_fail "kennisbank MCP runtime" "interpreter not found: ${MCP_PY[*]}"
  else
    MCP_IMPORT_OUT="$("${MCP_PY[@]}" -c 'import mcp; import mcp.client.stdio; import mcp.server.fastmcp' 2>&1)"
    MCP_IMPORT_RC=$?
    if [ "$MCP_IMPORT_RC" = "0" ]; then
      report_pass "kennisbank MCP runtime" "${MCP_PY[*]} imports mcp"
    else
      report_fail "kennisbank MCP runtime" "missing Python package for ${MCP_PY[*]} (run: ${MCP_PY[*]} -m pip install mcp==1.28.1) ${MCP_IMPORT_OUT}"
    fi
  fi
  if [ -f "$SCRIPTS_DIR/kb-mcp.py" ]; then
    MCP_TEMPORAL_OUT="$("${MCP_PY[@]}" -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("kb_mcp", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
missing = [n for n in ("what_did_i_do_tool", "timeline_tool", "weeklog_tool", "topic_timeline_tool") if not hasattr(m, n)]
print("OK" if not missing else "MISSING " + ",".join(missing))
' "$SCRIPTS_DIR/kb-mcp.py" 2>&1)"
    if [ "$MCP_TEMPORAL_OUT" = "OK" ]; then
      report_pass "kennisbank MCP temporal tools" "what_did_i_do timeline weeklog topic_timeline"
    else
      report_fail "kennisbank MCP temporal tools" "$MCP_TEMPORAL_OUT"
    fi
  fi
fi

# 11b-copilot. GitHub Copilot CLI integration (optional; TASK-26.9).
# Read-only diagnosis. Repair path is a setup re-run (install_copilot is
# idempotent and only touches KennisBank-managed keys/files, with backups).
COPILOT_CONFIGURED=0
if [ -f "$COPILOT_MCP_CONFIG" ] && grep -q '"kennisbank"' "$COPILOT_MCP_CONFIG" 2>/dev/null; then
  COPILOT_CONFIGURED=1
fi
if [ "$COPILOT_CONFIGURED" = "0" ]; then
  report_info "copilot integration" "not configured (optional; run setup.sh --agents copilot)"
elif command -v python3 >/dev/null 2>&1 && [ -f "$SCRIPTS_DIR/_copilot.py" ]; then
  # Managed config validation: MCP/instructions/profile, vault pinning, one
  # start/exit coordinator, and no legacy KennisBank lifecycle fan-out.
  CP_VALIDATE="$(python3 "$SCRIPTS_DIR/_copilot.py" validate --vault "$VAULT" 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    print("OK" if d.get("ok") else "FAIL " + "; ".join(d.get("errors", [])))
except Exception:
    print("ERR")
' 2>/dev/null | tr -d '\r')"
  case "$CP_VALIDATE" in
    OK) report_pass "copilot config" "mcp, instructions and agent profile present; one start and one exit coordinator" ;;
    ERR|"") report_warn "copilot config" "kon _copilot.py validate niet lezen (setup opnieuw draaien?)" ;;
    *) report_fail "copilot config" "${CP_VALIDATE#FAIL }; fix: setup.sh --agents copilot" ;;
  esac
  # Login-free CLI probe: binary/version + whether Copilot sees the MCP server.
  CP_PROBE="$(python3 "$SCRIPTS_DIR/_copilot.py" probe --vault "$VAULT" 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    print("%s|%s|%s" % (d.get("status"), d.get("version"), d.get("detail", "")))
except Exception:
    print("ERR||")
' 2>/dev/null | tr -d '\r')"
  CP_STATUS="$(printf '%s' "$CP_PROBE" | cut -d'|' -f1)"
  CP_VER="$(printf '%s' "$CP_PROBE" | cut -d'|' -f2)"
  CP_DETAIL="$(printf '%s' "$CP_PROBE" | cut -d'|' -f3)"
  case "$CP_STATUS" in
    ok) report_pass "copilot cli" "v$CP_VER; kennisbank MCP visible to copilot" ;;
    version_old|not_logged_in|mcp_not_listed) report_warn "copilot cli" "${CP_DETAIL:-$CP_STATUS}" ;;
    copilot_missing) report_warn "copilot cli" "configured but copilot not installed: ${CP_DETAIL}" ;;
    platform_binary_missing) report_warn "copilot cli" "${CP_DETAIL}" ;;
    *) report_warn "copilot cli" "kon probe-status niet lezen" ;;
  esac
  if [ -f "$HOME/.agents/skills/sessiestart/SKILL.md" ] &&
     [ -f "$HOME/.agents/skills/sessielog/SKILL.md" ]; then
    report_pass "copilot command skills" "sessiestart and sessielog installed"
  else
    report_warn "copilot command skills" "sessiestart/sessielog ontbreekt; run setup.sh --agents copilot"
  fi
fi

# 11c. Temporal Activity Recall index.
if command -v python3 >/dev/null 2>&1 && [ -f "$SCRIPTS_DIR/kb-activity.py" ]; then
  ACTIVITY_STATUS="$(python3 "$SCRIPTS_DIR/kb-activity.py" --vault "$VAULT" --json status 2>/dev/null)"
  if [ -z "$ACTIVITY_STATUS" ]; then
    report_warn "activity index" "kon status niet lezen; run: python3 $SCRIPTS_DIR/build-activity-index.py --vault $VAULT --full"
  else
    ACTIVITY_SUMMARY="$(printf '%s' "$ACTIVITY_STATUS" | python3 -c '
import json, sys
try:
    r=json.load(sys.stdin)
    print("%s %s %s %s %s" % (r.get("ok"), r.get("schema_version"), r.get("events"), r.get("sources"), r.get("stale_sources")))
except Exception:
    print("ERR")
' 2>/dev/null | tr -d '\r')"
    if [ "$ACTIVITY_SUMMARY" = "ERR" ]; then
      report_warn "activity index" "ongeldige status-output"
    else
      ACTIVITY_OK="$(printf '%s' "$ACTIVITY_SUMMARY" | cut -d' ' -f1)"
      ACTIVITY_SCHEMA="$(printf '%s' "$ACTIVITY_SUMMARY" | cut -d' ' -f2)"
      ACTIVITY_EVENTS="$(printf '%s' "$ACTIVITY_SUMMARY" | cut -d' ' -f3)"
      ACTIVITY_SOURCES="$(printf '%s' "$ACTIVITY_SUMMARY" | cut -d' ' -f4)"
      ACTIVITY_STALE="$(printf '%s' "$ACTIVITY_SUMMARY" | cut -d' ' -f5)"
      if [ "$ACTIVITY_OK" = "True" ]; then
        report_pass "activity index" "schema=$ACTIVITY_SCHEMA events=$ACTIVITY_EVENTS sources=$ACTIVITY_SOURCES stale=$ACTIVITY_STALE"
      else
        report_warn "activity index" "schema=$ACTIVITY_SCHEMA events=$ACTIVITY_EVENTS sources=$ACTIVITY_SOURCES stale=$ACTIVITY_STALE; run build-activity-index.py --full"
      fi
    fi
  fi
else
  report_warn "activity index" "kb-activity.py ontbreekt of python3 niet beschikbaar"
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

# 13. Memory subsystem checks (fase 5).
if [ -f "$SCRIPTS_DIR/memory-doctor.py" ]; then
  nocloud_out="$(python3 "$SCRIPTS_DIR/memory-doctor.py" nocloud 2>/dev/null)"
  if [ -n "$nocloud_out" ]; then
    while IFS= read -r line; do report_warn "geheugen no-cloud" "$line"; done <<EOF2
$nocloud_out
EOF2
  else
    report_pass "geheugen no-cloud" "LLM-keten lokaal"
  fi
  rot="$(python3 "$SCRIPTS_DIR/memory-doctor.py" rot 2>/dev/null)"
  if [ "${rot:-0}" -gt 0 ] 2>/dev/null; then
    report_warn "geheugen quarantaine" "$rot unverified memories ouder dan 48u (sweep/judge hangt?)"
  else
    report_pass "geheugen quarantaine" "geen rot"
  fi
fi

# 13b. KennisBank-hooks geregistreerd in settings.json (manifest-gedreven).
SETTINGS="$CLAUDE_DIR/settings.json"
HOOK_HINT="re-run 'bash setup.sh' (of bij een hardnekkig ontbrekende hook: rm \"$VAULT/.claude/.kennisbank-schema-version\" && bash setup.sh)"
if ! command -v python3 >/dev/null 2>&1; then
  report_warn "retrieval hooks" "kan $SETTINGS niet lezen zonder python3; $HOOK_HINT"
else
  HOOK_LINES="$(python3 -c '
import json, os, sys, importlib.util
spec = importlib.util.spec_from_file_location("_hooks_manifest",
    os.path.join(sys.argv[2], "_hooks_manifest.py"))
man = importlib.util.module_from_spec(spec); spec.loader.exec_module(man)
p = sys.argv[1]
if not os.path.exists(p):
    print("NOFILE"); raise SystemExit
try:
    text = open(p, encoding="utf-8").read()
    data = json.loads(text) if text.strip() else {}
except (ValueError, OSError):
    print("BADJSON"); raise SystemExit
if not isinstance(data, dict):
    print("BADJSON"); raise SystemExit
hooks = data.get("hooks", {}) if isinstance(data.get("hooks"), dict) else {}
def present(event, needle):
    for g in (hooks.get(event) or []):
        if isinstance(g, dict):
            for h in (g.get("hooks") or []):
                if isinstance(h, dict) and needle in (h.get("command") or ""):
                    return True
    return False
for event, script, _m in man.hooks():
    print(("OK " if present(event, script) else "MISSING ") + event + " " + script)
' "$SETTINGS" "$SCRIPTS_DIR" 2>/dev/null | tr -d '\r')"
  if [ "$HOOK_LINES" = "NOFILE" ]; then
    report_warn "retrieval hooks" "nog geen $SETTINGS; $HOOK_HINT"
  elif [ "$HOOK_LINES" = "BADJSON" ]; then
    report_warn "retrieval hooks" "$SETTINGS is geen geldige JSON; kan hooks niet checken. $HOOK_HINT"
  elif [ -z "$HOOK_LINES" ]; then
    report_warn "retrieval hooks" "kon $SETTINGS niet lezen (python3-fout); $HOOK_HINT"
  else
    while IFS=' ' read -r status event script; do
      if [ "$status" = "OK" ]; then
        report_pass "hook $event $script" "registered in $SETTINGS"
      else
        report_warn "hook $event $script" "not registered. $HOOK_HINT"
      fi
    done <<HOOKEOF
$HOOK_LINES
HOOKEOF
  fi
fi

# 13c. Vault-migratie-schema-versie (eigen stempel; los van .kennisbank-version
# dat de upgrade/contribute-skills voor de release-tag gebruiken).
if command -v python3 >/dev/null 2>&1; then
  KB_VER="$(python3 "$SCRIPTS_DIR/_migrations.py" version "$VAULT" 2>/dev/null | tr -d '\r')"
  report_info "kennisbank-schema-versie" "${KB_VER:-onbekend}"
fi

# 13d. Provenance-lint: elk wiki-artikel moet herleidbare sessie-herkomst
# hebben (resolvende [[raw-sessie-...]]-wikilink). Read-only; details via
# `python3 kb-lint.py` los draaien. FAIL-tier op HARD findings (missing/
# dangling = niet-auditeerbaar); path-only blijft advisory (WARN).
if command -v python3 >/dev/null 2>&1 && [ -f "$SCRIPTS_DIR/kb-lint.py" ]; then
  LINT_SUMMARY="$(python3 "$SCRIPTS_DIR/kb-lint.py" --json 2>/dev/null | python3 -c '
import json, sys
try:
    r = json.load(sys.stdin)
    print("%d %d %d" % (r["articles"], r["warned"], r.get("hard", 0)))
except Exception:
    print("ERR")
' 2>/dev/null | tr -d '\r')"
  case "$LINT_SUMMARY" in
    ""|ERR)
      report_warn "provenance-lint" "kon kb-lint.py niet draaien (bestaat 02-wiki/?)"
      ;;
    *)
      LINT_ARTICLES="$(printf '%s' "$LINT_SUMMARY" | cut -d' ' -f1)"
      LINT_WARNED="$(printf '%s' "$LINT_SUMMARY" | cut -d' ' -f2)"
      LINT_HARD="$(printf '%s' "$LINT_SUMMARY" | cut -d' ' -f3)"
      if [ "$LINT_HARD" != "0" ]; then
        report_fail "provenance-lint" "$LINT_HARD artikel(en) met NIET-herleidbare herkomst (missing/dangling); niet-auditeerbaar. Fix: python3 $SCRIPTS_DIR/kb-lint.py --strict"
      elif [ "$LINT_WARNED" != "0" ]; then
        report_warn "provenance-lint" "$LINT_WARNED van $LINT_ARTICLES artikelen met pad-tekst-herkomst (advisory); draai: python3 $SCRIPTS_DIR/kb-lint.py"
      else
        report_pass "provenance-lint" "$LINT_ARTICLES artikelen, alle herkomst herleidbaar"
      fi
      ;;
  esac
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
