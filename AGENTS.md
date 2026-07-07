# AGENTS.md

Operational instructions for AI coding agents installing or upgrading this repo.
The human-facing guide is `README.md`; this file is the deployment contract.

## Purpose

LLmWiki-KennisBank deploys a local personal knowledge vault plus agent
integrations. It is not Claude-Code-only. Supported install targets are:

- `claude` - Claude Code commands, skills, and hooks.
- `codex` - Codex skills, prompt aliases, hooks, MCP config, and `AGENTS.md`.
- `opencode` - OpenCode commands, skills, MCP config, `AGENTS.md`, and plugin.

`setup.sh` is the single supported entrypoint for both initial install and
upgrade. Do not hand-copy files unless `setup.sh` itself is broken and you are
repairing it.

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

All generated hooks and MCP configs must contain this explicit vault path.

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
- `--agents claude,codex`
- `--agents all`

Interactive setup asks which agent environments to install unless `--yes` or
`--agents` is supplied.

`setup.sh` must complete only after:

- vault files and scripts are deployed,
- selected agent configs are installed or repaired,
- migrations have run,
- `doctor.sh` has passed,
- selected agent hooks/skills/MCP config validate,
- local Ollama and/or OpenRouter backend smoke checks pass, unless
  `--skip-model-check` is explicit.

Use `--skip-model-check` only for CI/offline tests or when the user explicitly
accepts that model validation is skipped.

## Client Expectations

Claude Code:

- Commands go to `~/.claude/commands/`.
- Skills go to `~/.claude/skills/`.
- Hooks go to `~/.claude/settings.json`.

Codex:

- Skills go to `~/.agents/skills/`.
- Prompt aliases go to `~/.codex/prompts/` and are invoked as
  `/prompts:<name>`.
- MCP server `kennisbank` goes in `~/.codex/config.toml`.
- Hooks go in `~/.codex/hooks.json`.
- Global KennisBank instructions go in `~/.codex/AGENTS.md`.

OpenCode:

- Commands go to `~/.config/opencode/commands/` and are invoked directly as
  `/sessielog`, `/sessiestart`, `/kennisbank-upgrade`, etc.
- Skills go to `~/.agents/skills/`.
- MCP server `kennisbank` goes in `~/.config/opencode/opencode.json`.
- The local plugin goes to `~/.config/opencode/plugins/kennisbank.js`.
- Global rules go in `~/.config/opencode/AGENTS.md`.

## Validation

After setup, verify:

```bash
KENNISBANK_VAULT="/absolute/path/to/vault" bash "<vault>/.claude/scripts/doctor.sh"
python3 scripts/install-agent-envs.py --vault "/absolute/path/to/vault" --agents claude,codex --validate
```

Expected: no `[FAIL]` from doctor and `validation: PASS` from the agent
validator. WARN messages are not always blockers, but report them accurately.

For Codex specifically:

```bash
codex mcp list
```

Expected: a `kennisbank` server pointing to
`<vault>/.claude/scripts/kb-mcp.py`.

For OpenCode, inspect:

```bash
ls ~/.config/opencode/commands
cat ~/.config/opencode/opencode.json
```

Expected: KennisBank commands present and an MCP server named `kennisbank`.

## Safety Rules

- Never overwrite vault `CLAUDE.md` or global agent instruction files wholesale.
  Use append/managed blocks.
- Never overwrite user agent settings with a full template. Merge only the
  KennisBank entries.
- Keep hook scripts fail-open.
- Do not force-close setup as complete when model validation failed, unless
  the user explicitly requested `--skip-model-check`.
- Do not tunnel the local vault to hosted/cloud agents unless the user
  explicitly accepts that data boundary.
