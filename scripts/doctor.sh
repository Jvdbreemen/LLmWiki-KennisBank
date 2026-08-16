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
  # Hardcoded vaultpad (ADR-0002). setup.sh overschrijft CLAUDE.md bewust nooit,
  # dus een vault die met een oud sjabloon is opgezet houdt de fout paden. Toets
  # op het letterlijke pad, niet op "VAULT != default": in elke deploytest zijn
  # die identiek en zou de check nooit vuren.
  if grep -q '~/KennisBank/' "$VAULT_CLAUDE_MD" 2>/dev/null; then
    report_warn "vault CLAUDE.md" \
      "bevat hardcoded ~/KennisBank/-paden; vervang door \"\${KENNISBANK_VAULT:-\$HOME/KennisBank}\" (ADR-0002)"
  fi
fi

# 3b. Skill-backups van eerdere upgrades. Een <naam>.pre-<tag>.bak in de map die
# de client scant, laadt als een tweede skill met dezelfde description -- de
# agent kan dan de verouderde versie kiezen.
if [ -d "$SKILLS_DIR" ]; then
  STALE_SKILL_BAKS="$(find "$SKILLS_DIR" -maxdepth 1 -name '*.bak' 2>/dev/null | wc -l | tr -d ' \r')"
  if [ "${STALE_SKILL_BAKS:-0}" -gt 0 ] 2>/dev/null; then
    report_warn "skill backups" \
      "$STALE_SKILL_BAKS .bak-item(s) in $SKILLS_DIR zijn triggerbaar; verplaats ze naar \$VAULT/.claude/skills.pre-legacy.bak/"
  else
    report_pass "skill backups" "geen .bak-skills in $SKILLS_DIR"
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
# Honoreer de agent-home-variabelen, net als COPILOT_HOME hieronder. Zonder dit
# keek doctor altijd in $HOME en gaf een groene uitslag over een MCP-runtime die
# ergens anders staat en dus nergens gevalideerd is.
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
OPENCODE_DIR="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"
CODEX_CONFIG="$CODEX_HOME_DIR/config.toml"
OPENCODE_CONFIG="$OPENCODE_DIR/opencode.json"
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

# 11c-bis. Graphify-graaf. De map wordt door setup.sh aangemaakt en hierboven al
# gecontroleerd; het gaat om het BESTAND. De producent is een externe skill, dus
# afwezigheid is geen fout -- maar wel het verschil tussen drie werkende en drie
# lege Atlas-lenzen, plus /brug en auto-crosslink.
GRAPH_JSON="$VAULT/graphify-out/graph.json"
REBUILD_FLAG="$VAULT/graphify-out/.needs-rebuild"
if [ -f "$GRAPH_JSON" ]; then
  if [ -s "$REBUILD_FLAG" ]; then
    report_info "graphify graph" "aanwezig, maar .needs-rebuild is niet leeg; draai /graphify en verwijder daarna de vlag met rm"
  else
    report_pass "graphify graph" "$GRAPH_JSON"
  fi
else
  report_info "graphify graph" "geen graph.json; /brug, auto-crosslink en de graaf-lenzen vallen stil terug (externe graphify-skill vereist)"
fi

# 11c-ter. Graafretrieval (TASK-87). De stil-leeg-guard uit TASK-15: een
# toggle die aan staat terwijl de graaf stale is levert maandenlang stil
# GEEN buur — dat hoort een WARN te zijn, geen onzichtbaarheid. De teller
# (buren geinjecteerd, 30d) toont of de expansie daadwerkelijk iets doet.
if command -v python3 >/dev/null 2>&1 && [ -f "$SCRIPTS_DIR/_settings.py" ]; then
  GRAPH_RETR="$(python3 -c 'import sys
sys.path.insert(0, sys.argv[1])
import _settings, _kbindex, _usage
import sqlite3
on = _settings.get("graph_retrieval", False)
fresh = "n/a"
try:
    p = _kbindex.graph_index_path()
    if p.exists():
        conn = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
        from _vaultpath import vault_root
        fresh = "fresh" if _kbindex.graph_is_current(conn, vault_root() / "graphify-out" / "graph.json") else "stale"
        conn.close()
    else:
        fresh = "no-db"
except Exception:
    fresh = "error"
print(f"{int(on)} {fresh} {_usage.neighbor_injected(30)}")' "$SCRIPTS_DIR" 2>/dev/null | tr -d '
')"
  GR_ON="$(printf '%s' "$GRAPH_RETR" | cut -d' ' -f1)"
  GR_FRESH="$(printf '%s' "$GRAPH_RETR" | cut -d' ' -f2)"
  GR_NB="$(printf '%s' "$GRAPH_RETR" | cut -d' ' -f3)"
  case "$GR_ON" in
    1)
      if [ "$GR_FRESH" = "fresh" ]; then
        report_pass "graph retrieval" "toggle aan, graaf vers, buren geinjecteerd (30d): ${GR_NB:-0}"
      else
        report_warn "graph retrieval" "toggle AAN maar graafindex ${GR_FRESH:-onbekend} — expansie levert stil niets; draai /graphify + build-graph-index.py"
      fi
      ;;
    0)
      report_info "graph retrieval" "toggle uit (legacy wikilink-expansie actief); buren geinjecteerd (30d): ${GR_NB:-0}"
      ;;
    *)
      report_warn "graph retrieval" "status niet leesbaar (python3/_settings-fout)"
      ;;
  esac
fi

# 11c-ter-bis. Verdwaalde KB_USAGE_DISABLE in de omgeving (TASK-97).
# kb-eval.py zet deze var alleen in zijn eigen proces; staat hij hier (shell-
# profiel, systeem-env), dan leert de KennisBank stil niets meer van gebruik —
# precies de stil-leeg-faalvorm (TASK-15) die zichtbaar hoort te zijn.
if [ -n "${KB_USAGE_DISABLE:-}" ]; then
  report_warn "usage telemetry" \
    "KB_USAGE_DISABLE staat in de omgeving — de KennisBank leert nu NIET van gebruik. Bedoeld voor eval-runs; verwijder de export uit je shell-profiel/systeem-env."
else
  report_pass "usage telemetry" "geen verdwaalde KB_USAGE_DISABLE in de omgeving"
fi

# 11c-quater. Provenance-dekking in de index (TASK-88). Het coupling-signaal
# kan alleen wegen wat geindexeerd is; dekking 0 terwijl de knop aan staat is
# de stil-leeg-faalvorm (TASK-15) en verdient een WARN.
if command -v python3 >/dev/null 2>&1 && [ -f "$VAULT/.claude/kb-index.db" ]; then
  PROV_COV="$(python3 -c 'import sqlite3, sys
db = sys.argv[1]
try:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT d.layer, count(DISTINCT d.doc_id), "
        "count(DISTINCT CASE WHEN s.doc_id IS NOT NULL THEN d.doc_id END) "
        "FROM docs d LEFT JOIN doc_sources s ON s.doc_id = d.doc_id "
        "GROUP BY d.layer").fetchall()
    conn.close()
    stats = {layer: (int(cov), int(tot)) for layer, tot, cov in rows}
    w = stats.get("wiki", (0, 0)); m = stats.get("memory", (0, 0))
    print(f"{w[0]} {w[1]} {m[0]} {m[1]}")
except Exception:
    print("ERR")' "$VAULT/.claude/kb-index.db" 2>/dev/null | tr -d '
')"
  if [ "$PROV_COV" = "ERR" ] || [ -z "$PROV_COV" ]; then
    report_info "provenance coverage" "index nog zonder doc_sources-tabel; draai build-kb-index.py --rebuild voor de backfill"
  else
    PC_WC="$(printf '%s' "$PROV_COV" | cut -d' ' -f1)"
    PC_WT="$(printf '%s' "$PROV_COV" | cut -d' ' -f2)"
    PC_MC="$(printf '%s' "$PROV_COV" | cut -d' ' -f3)"
    PC_MT="$(printf '%s' "$PROV_COV" | cut -d' ' -f4)"
    COUPLING_ON="$(python3 -c 'import json, sys, os
try:
    cfg = json.loads(open(os.path.join(sys.argv[1], ".claude", "kennisbank-embed.json"), encoding="utf-8").read())
    print(int(bool(cfg.get("rank_coupling", 0))))
except Exception:
    print(0)' "$VAULT" 2>/dev/null | tr -d '
')"
    if [ "$COUPLING_ON" = "1" ] && [ "${PC_WC:-0}" = "0" ] && [ "${PC_MC:-0}" = "0" ]; then
      report_warn "provenance coverage" "rank_coupling staat AAN maar geen enkel doc heeft een bron in de index — het signaal weegt stil niets; draai build-kb-index.py --rebuild"
    else
      report_pass "provenance coverage" "wiki ${PC_WC:-0}/${PC_WT:-0}, memory ${PC_MC:-0}/${PC_MT:-0} docs met >=1 bron"
    fi
  fi
fi

# 11d. Temporele locale-vocabulaire. Toetst de GELADEN tabel, niet de
# aanwezigheid van het bestand: een aanwezig-maar-onleesbaar activity-locales.json
# faalt stil open en laat de datumparser met een lege Laag 1 achter.
if command -v python3 >/dev/null 2>&1 && [ -f "$SCRIPTS_DIR/_activity.py" ]; then
  LOCALE_N="$(python3 -c 'import sys
sys.path.insert(0, sys.argv[1])
import _activity as m
print(len(m.MONTHS), len(m.WEEKDAYS))' "$SCRIPTS_DIR" 2>/dev/null | tr -d '\r')"
  LOCALE_MONTHS="$(printf '%s' "$LOCALE_N" | cut -d' ' -f1)"
  LOCALE_DAYS="$(printf '%s' "$LOCALE_N" | cut -d' ' -f2)"
  case "$LOCALE_MONTHS" in
    ''|*[!0-9]*) report_warn "temporal locales" "kon de locale-tabel niet laden; run: bash setup.sh" ;;
    0) report_warn "temporal locales" "lege vocabulaire (activity-locales.json niet gedeployed?); run: bash setup.sh" ;;
    *) report_pass "temporal locales" "$LOCALE_MONTHS maandwoorden, $LOCALE_DAYS dagwoorden" ;;
  esac
fi

# 12. Ollama and the embedding model (optional).
# Resolve the ACTIVE model through the one config chain (env >
# kennisbank-embed.json > code default) instead of a literal: a stale :8b
# here reported the OLD model as "installed" on exactly the vaults whose
# recall had gone dark after the default flip (TASK-182).
if ! command -v ollama >/dev/null 2>&1; then
  report_info "ollama" "not installed (optional, needed for semantic tiling)"
else
  EMBED_MODEL="$(KENNISBANK_VAULT="$VAULT" python3 "$SCRIPTS_DIR/_embeddings.py" --print-model 2>/dev/null)"
  if [ -z "$EMBED_MODEL" ]; then
    report_warn "ollama embed-model" "kon het actieve embedmodel niet bepalen (python3/_embeddings.py)"
  elif ollama list 2>/dev/null | grep -qF "$EMBED_MODEL"; then
    report_info "ollama $EMBED_MODEL" "installed"
  else
    report_warn "ollama $EMBED_MODEL" "model not pulled (run: ollama pull $EMBED_MODEL)"
  fi
  # Index-vs-code mismatch: the exact condition under which recall returns []
  # silently. Warn with the remedy; only FAIL flips doctor's exit code, so
  # setup on a not-yet-pulled model does not hard-fail twice.
  if [ -f "$VAULT/.claude/kb-index.db" ]; then
    MISMATCH="$(KENNISBANK_VAULT="$VAULT" python3 - "$VAULT" <<'PYEOF' 2>/dev/null
import sys, os
sys.path.insert(0, os.path.join(sys.argv[1], ".claude", "scripts"))
try:
    import _embeddings as emb
    import _kbindex
    conn = _kbindex.connect()
    m = _kbindex.embed_mismatch(conn, emb.embed_id())
    conn.close()
    if m:
        print(f"{m[0]}|{m[1]}")
except Exception:
    pass
PYEOF
)"
    if [ -n "$MISMATCH" ]; then
      STORED="${MISMATCH%|*}"; LIVE="${MISMATCH#*|}"
      # embed_id is "provider:model[+prefix]" -> strip both for the pull cmd.
      LIVE_MODEL="${LIVE#*:}"; LIVE_MODEL="${LIVE_MODEL%%+*}"
      report_warn "kb-index embed-model" "index=$STORED code=$LIVE; recall staat uit tot: ollama pull $LIVE_MODEL && python3 \"\$VAULT/.claude/scripts/build-kb-index.py\" --rebuild"
    fi
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
  # Review-queue-teller (TASK-89): een queue die bestaat maar nooit gebruikt
  # wordt is de TASK-23-faalvorm (31 gestuwde unverified, mens zag het niet).
  REVIEW_STAT="$(python3 -c 'import sys
sys.path.insert(0, sys.argv[1])
import _memory
pending = len(_memory.pending_reviews())
c = _memory.review_counts(30)
print(f"{pending} {c[\"approve\"]} {c[\"reject\"]} {c[\"skip\"]}")' "$SCRIPTS_DIR" 2>/dev/null | tr -d '\r')"
  if [ -n "$REVIEW_STAT" ]; then
    RV_P="$(printf '%s' "$REVIEW_STAT" | cut -d' ' -f1)"
    RV_A="$(printf '%s' "$REVIEW_STAT" | cut -d' ' -f2)"
    RV_R="$(printf '%s' "$REVIEW_STAT" | cut -d' ' -f3)"
    RV_S="$(printf '%s' "$REVIEW_STAT" | cut -d' ' -f4)"
    RV_TOT=$((${RV_A:-0} + ${RV_R:-0} + ${RV_S:-0}))
    if [ "${RV_P:-0}" -ge 10 ] 2>/dev/null && [ "$RV_TOT" -eq 0 ] 2>/dev/null; then
      report_warn "review-queue" "$RV_P unverified wachten en 0 beslissingen in 30d — draai /kennisbank:review"
    else
      report_pass "review-queue" "$RV_P wachtend; beslist (30d): $RV_A approve / $RV_R reject / $RV_S skip"
    fi
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
