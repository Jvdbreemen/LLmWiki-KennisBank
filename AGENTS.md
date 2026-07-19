# AGENTS.md

Operational instructions for AI coding agents installing or upgrading this repo.
The human-facing guide is `README.md`; this file is the deployment contract.

## Purpose

LLmWiki-KennisBank deploys a local personal knowledge vault plus agent
integrations. It is not Claude-Code-only. Supported install targets are:

- `claude` - Claude Code commands, skills, and hooks.
- `codex` - Codex skills, prompt aliases, MCP config, and `AGENTS.md`.
- `opencode` - OpenCode commands, skills, MCP config, `AGENTS.md`, and plugin.
- `copilot` - standalone GitHub Copilot CLI: MCP config, personal
  instructions, and a custom agent profile under `~/.copilot/`. Opt-in and
  cloud-backed; not in the default target set.

`setup.sh` is the single supported entrypoint for both initial install and
upgrade. Do not hand-copy files unless `setup.sh` itself is broken and you are
repairing it.

The current feature set includes Temporal Activity Recall and local LiteParse
document intake. Setup must deploy `build-activity-index.py`, `kb-activity.py`,
`kb-activity-eval.py`, `parse-document.py`, `_liteparse.py`, the commands
`/weeklog`, `/timeline`, `/watdeedik`, `/intake`, `/import`, and MCP tools
`what_did_i_do`, `timeline`, `weeklog`, and `topic_timeline`.

## Vault Path Rule

Never assume the active vault is `~/KennisBank` or
`C:\Users\rvdbr\KennisBank`.

Resolve the active vault in this order:

1. `KENNISBANK_VAULT`, if set.
2. A user-provided path.
3. Only then the product default `~/KennisBank`.

When the user names a non-default vault, run setup with that exact path:

```bash
KENNISBANK_VAULT="/absolute/path/to/vault" bash setup.sh --yes --agents claude,codex
```

On Windows PowerShell with Git Bash:

```powershell
$env:KENNISBANK_VAULT = "D:/Users/Robert/Documents/Claude/Projects/Kluis"
& "C:\Program Files\Git\bin\bash.exe" setup.sh --yes --agents claude,codex,opencode
```

All generated Claude hooks and all MCP configs must contain this explicit vault
path.

## Pre-Flight

Run these before installation or upgrade:

```bash
test -f ./setup.sh && test -d ./commands && test -d ./scripts && echo OK || echo "WRONG DIR"
git status --short --branch
python3 --version
```

On Windows, prefer Git Bash from `C:\Program Files\Git\bin\bash.exe`; the
System32 `bash.exe` is WSL and may write Linux-shaped paths into Windows agent
configs.

Check local model availability when model validation is expected:

```bash
ollama list
```

The default embedding model is `qwen3-embedding:8b`. The local judge/extraction
model should match `<vault>/.claude/kennisbank-llm.json`; on Robert's machine it
is normally pinned to `gemma4:12b`.

If the user chooses OpenRouter for judge/extraction, keep it explicit:

- The default setup answer is still `ollama`.
- OpenRouter is a cloud API; warn that memory-sweep content leaves the machine.
- Store only `providers`, `model`, `endpoint`, and `api_key_env` in
  `<vault>/.claude/kennisbank-llm.json`.
- Never write API keys into the repo or vault. Use the named env var or the
  user-local `~/.config/kennisbank/secrets.json` written by setup.

## Install Or Upgrade

Use `setup.sh` for both first install and upgrades:

```bash
KENNISBANK_VAULT="/absolute/path/to/vault" bash setup.sh --yes --agents claude,codex
```

Agent target options:

- `--agents claude`
- `--agents codex`
- `--agents opencode`
- `--agents copilot`
- `--agents claude,codex`
- `--agents all`

Interactive setup asks which agent environments to install unless `--yes` or
`--agents` is supplied.

`setup.sh` must complete only after:

- vault files and scripts are deployed,
- selected agent configs are installed or repaired,
- migrations have run,
- the temporal activity index has been built/refreshed,
- `doctor.sh` has passed,
- selected agent skills/MCP config and any selected Claude hooks validate,
- local Ollama and/or OpenRouter backend smoke checks pass, unless
  `--skip-model-check` is explicit.
- LiteParse document parsing is installed or reported accurately by doctor.

Use `--skip-model-check` only for CI/offline tests or when the user explicitly
accepts that model validation is skipped.

### Copilot integration (opt-in, hookless by construction)

`--agents copilot` targets the standalone `@github/copilot` CLI (invoked
`copilot`, v1.0.70+), not the `gh copilot` extension or VS Code agent mode. It is
idempotent for both install and upgrade and never overwrites unmanaged Copilot
config:

- Structured MCP config (`~/.copilot/mcp-config.json`) gets a key-scoped
  read-modify-write of the `mcpServers.kennisbank` key — never a whole-file
  overwrite.
- Freeform files (`~/.copilot/copilot-instructions.md`, the agent profile) get a
  marker-delimited managed block, with a backup before any edit.
- KennisBank installs no Copilot lifecycle hooks. During install or upgrade it
  removes only known legacy KennisBank entries and preserves unrelated user
  hooks. Session work is explicit through `/sessiestart` and `/sessielog`.
- Registration and validation are login-free; only a live model turn needs
  `copilot` `/login`. On Windows/nvm4w, if `copilot --version` reports "no
  platform package found", also install `@github/copilot-<platform>-<arch>` at
  the same version.
- All user-level paths honor `COPILOT_HOME`. Repair is a re-run of the same
  command; `doctor.sh` is read-only. Never store or log the user's auth tokens
  (`COPILOT_GITHUB_TOKEN` / `GH_TOKEN` / `GITHUB_TOKEN`).

## Client Expectations

Claude Code:

- Commands go to `~/.claude/commands/`.
- Skills go to `~/.claude/skills/`.
- Hooks go to `~/.claude/settings.json`.
- Temporal commands `/weeklog`, `/timeline`, and `/watdeedik` are installed
  alongside the existing KennisBank commands.

Codex:

- Skills go to `~/.agents/skills/`.
- Prompt aliases go to `~/.codex/prompts/` and are invoked as
  `/prompts:<name>`.
- MCP server `kennisbank` goes in `~/.codex/config.toml`.
- KennisBank installs no Codex lifecycle hooks. Upgrades remove only known
  legacy KennisBank entries and preserve unrelated user hooks.
- Global KennisBank instructions go in `~/.codex/AGENTS.md`.
- Temporal prompt aliases go to `~/.codex/prompts/weeklog.md`,
  `timeline.md`, and `watdeedik.md`.

OpenCode:

- Commands go to `~/.config/opencode/commands/` and are invoked directly as
  `/sessielog`, `/sessiestart`, `/kennisbank-upgrade`, etc.
- Skills go to `~/.agents/skills/`.
- MCP server `kennisbank` goes in `~/.config/opencode/opencode.json`.
- The local plugin goes to `~/.config/opencode/plugins/kennisbank.js`.
- Global rules go in `~/.config/opencode/AGENTS.md`.
- Temporal commands go to `~/.config/opencode/commands/`.

Copilot (standalone GitHub Copilot CLI, opt-in):

- MCP server `kennisbank` goes in `~/.copilot/mcp-config.json` (key
  `mcpServers.kennisbank`, key-scoped JSON merge, login-free).
- No KennisBank lifecycle hooks are installed. Use `/sessiestart` and
  `/sessielog`; upgrades selectively clean up legacy KennisBank hook entries.
- Personal instructions go in `~/.copilot/copilot-instructions.md` (managed
  marker block).
- Custom agent profile goes in `~/.copilot/agents/kennisbank.agent.md` (the
  `.agent.md` extension is required), selected with `copilot --agent kennisbank`.
- Skills are the shared `~/.agents/skills/` set — no separate install.
- Capture/import: `kb-copilot-capture.py` writes redacted events to
  `<vault>/.claude/copilot-events/`; `import-copilot.py` normalizes them into
  `01-raw/transcripts/` with `agent=github-copilot-cli` provenance.

## Validation

After setup, verify:

```bash
KENNISBANK_VAULT="/absolute/path/to/vault" bash "<vault>/.claude/scripts/doctor.sh"
python3 scripts/install-agent-envs.py --vault "/absolute/path/to/vault" --agents claude,codex --validate
python3 "<vault>/.claude/scripts/kb-activity.py" --vault "/absolute/path/to/vault" status
```

Expected: no `[FAIL]` from doctor and `validation: PASS` from the agent
validator. WARN messages are not always blockers, but report them accurately.

For Codex specifically:

```bash
codex mcp list
```

Expected: a `kennisbank` server pointing to
`<vault>/.claude/scripts/kb-mcp.py`.
The MCP validator must list `recall`, `capture`, `what_did_i_do`, `timeline`,
`weeklog`, and `topic_timeline`.

For OpenCode, inspect:

```bash
ls ~/.config/opencode/commands
cat ~/.config/opencode/opencode.json
```

Expected: KennisBank commands present and an MCP server named `kennisbank`.

For Copilot specifically:

```bash
copilot mcp list
python3 "<vault>/.claude/scripts/_copilot.py" validate --vault "<vault>" --json
python3 "<vault>/.claude/scripts/agent-status.py" --vault "<vault>"
```

Expected: a `kennisbank` server visible to Copilot (login-free), and
`_copilot.py validate` reporting `OK`. `agent-status.py` is the multi-agent
rollup. Validation also expects no KennisBank lifecycle hooks. When Copilot is
not selected, `doctor.sh` reports
`copilot integration: not configured` as INFO (0 FAIL) — that is expected, not a
blocker.

## Safety Rules

- Never overwrite vault `CLAUDE.md` or global agent instruction files wholesale.
  Use append/managed blocks.
- Never overwrite user agent settings with a full template. Merge only the
  KennisBank entries.
- Keep Claude hook scripts fail-open.
- Long backfills or sweeps must emit meaningful progress at least every five
  minutes; do not replace progress with dot-only output.
- Do not force-close setup as complete when model validation failed, unless
  the user explicitly requested `--skip-model-check`.
- Do not tunnel the local vault to hosted/cloud agents unless the user
  explicitly accepts that data boundary.
