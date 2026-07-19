# Agent Integrations

KennisBank is local-only. Every supported local client points at the same vault
and the same stdio MCP server:

```text
<vault>/.claude/scripts/kb-mcp.py
```

Do not rely on the default `~/KennisBank` path when the user has a different
vault. Run setup with the active vault path:

```bash
KENNISBANK_VAULT="/absolute/path/to/vault" bash setup.sh --yes --agents claude,codex,copilot
```

Add `opencode` to that list when the additional OpenCode integration is also
wanted.

`setup.sh` is the only supported install and upgrade entrypoint. It refreshes the
deployed tooling, repairs agent configuration, runs migrations, validates hooks
and skills, validates MCP runtime startup for MCP-enabled agents, and runs local
Ollama model smoke tests unless `--skip-model-check` is explicitly used.

## Claude Code

Installed by `--agents claude`.

- Commands: `~/.claude/commands/*.md`
- Skills: `~/.claude/skills/<name>/SKILL.md`
- Hooks: `~/.claude/settings.json`
- Vault env: `KENNISBANK_VAULT`

Claude Code receives one coordinated `SessionStart`, one coordinated
`SessionEnd`, plus `UserPromptSubmit` and `PreToolUse`. Startup runs independent
index work concurrently and dependent notices afterward. Exit archives the
transcript first, then attributes recall usage. All scripts are time-bounded,
fail-open, and preserve user settings. Claude may still show one client-owned
row per lifecycle event; retaining automation means those generic rows cannot
be hidden portably.

## Codex

Installed by `--agents codex`.

- Skills: `~/.agents/skills/<name>/SKILL.md`
- Prompt aliases: `~/.codex/prompts/*.md`
- Global instructions: `~/.codex/AGENTS.md`
- Hooks: `~/.codex/hooks.json`
- MCP: `~/.codex/config.toml`, server name `kennisbank`

Use native skills for the common session workflows:

```text
$sessiestart
$sessielog
```

Codex custom prompt compatibility files are invoked as `/prompts:<name>`, not
as bare custom slash commands. For example:

```text
/prompts:sessielog
/prompts:sessiestart
/prompts:kennisbank-upgrade
/prompts:weeklog
/prompts:timeline
/prompts:watdeedik
```

Codex uses the installed skills for reusable workflows and the MCP tools
`recall` and `capture` for live vault access. For temporal questions, use
`what_did_i_do`, `timeline`, `weeklog`, or `topic_timeline` before generic
recall. Codex registers exactly one KennisBank SessionStart coordinator and one
Stop/exit coordinator. No-change work emits no KennisBank detail; changed
startup indexes and warnings become one agent-context payload. Exit capture is
silent. Codex may still render one generic row per lifecycle event because the
client owns that UI. Setup migrates old start/exit entries while preserving
unrelated hooks and KennisBank prompt/presearch behavior.
Setup installs the Python MCP SDK and validates Codex MCP with a real
initialize/list-tools handshake before it reports success.

Manual MCP shape:

```bash
py -3 -m pip install mcp==1.28.1
```

```toml
[mcp_servers.kennisbank]
command = "py"
args = ["-3", "/absolute/path/to/vault/.claude/scripts/kb-mcp.py"]

[mcp_servers.kennisbank.env]
KENNISBANK_VAULT = "/absolute/path/to/vault"
KB_LLM_PROVIDERS = "ollama"
KB_LLM_MODEL = "gemma4:12b"
KB_LLM_ENDPOINT = "http://localhost:11434"
```

## OpenCode

Installed by `--agents opencode`.

- Commands: `~/.config/opencode/commands/*.md`
- Skills: `~/.agents/skills/<name>/SKILL.md`
- Global rules: `~/.config/opencode/AGENTS.md`
- Local plugin: `~/.config/opencode/plugins/kennisbank.js`
- MCP: `~/.config/opencode/opencode.json`, server name `kennisbank`

OpenCode supports real custom command names, so `/sessielog`,
`/sessiestart`, `/kennisbank-upgrade`, and the other KennisBank commands are
available directly after restart. Setup validates OpenCode's generated MCP
server command with the same local Python MCP runtime used by Codex.
Temporal commands `/weeklog`, `/timeline`, and `/watdeedik` are installed as
regular OpenCode commands; temporal agent recall should use the MCP temporal
tools when a structured API is available.

Manual MCP shape:

```bash
py -3 -m pip install mcp==1.28.1
```

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "kennisbank": {
      "type": "local",
      "enabled": true,
      "command": ["py", "-3", "/absolute/path/to/vault/.claude/scripts/kb-mcp.py"],
      "environment": {
        "KENNISBANK_VAULT": "/absolute/path/to/vault",
        "KB_LLM_PROVIDERS": "ollama",
        "KB_LLM_MODEL": "gemma4:12b",
        "KB_LLM_ENDPOINT": "http://localhost:11434"
      }
    }
  }
}
```

OpenCode local plugins are loaded automatically from
`~/.config/opencode/plugins/`. The generated plugin is fail-open and only runs
local KennisBank maintenance scripts.

## GitHub Copilot CLI

Installed by `--agents copilot`. Targets the **standalone** GitHub Copilot CLI
(`npm install -g @github/copilot`, invoked as `copilot`, v1.0.70+), not the older
`gh copilot` gh-extension and not Copilot's VS Code agent mode. The authoritative
original design is [ADR-0003](adr/0003-copilot-cli-integration.md). Its
SessionStart fan-out is refined by
[ADR-006](adr/ADR-006-coordinate-sessionstart-work-behind-one-client-hook.md); the wrapper's
"trivial exec, not a proxy" stance is derived in
[docs/copilot-headroom-evaluation.md](copilot-headroom-evaluation.md).

- Skills: `~/.agents/skills/<name>/SKILL.md` (shared with Codex/OpenCode; no
  separate install — list with `copilot skill list`)
- MCP: `~/.copilot/mcp-config.json`, server name `kennisbank`
- Hooks: `~/.copilot/hooks/kennisbank.json`
- Personal instructions: `~/.copilot/copilot-instructions.md` (KennisBank managed block)
- Custom agent profile: `~/.copilot/agents/kennisbank.agent.md`, selected with
  `copilot --agent kennisbank` (the `.agent.md` extension is required)
- Wrapper/launcher: `<vault>/.claude/scripts/kennisbank-copilot.py`
- Config home: `~/.copilot` (Windows `%USERPROFILE%\.copilot`); `COPILOT_HOME` overrides it

All user-level paths honor `COPILOT_HOME`. KennisBank writes **only** its own
namespaced keys and marker-delimited blocks: `mcpServers.kennisbank` in the MCP
file, KennisBank hook entries, and a managed block in freeform instruction
files. During upgrade it replaces only known legacy start/exit commands. It
never rewrites unmanaged Copilot config, and it backs up
any freeform file before editing.

`setup.sh --agents copilot` registers the MCP server by a key-scoped JSON merge
(login-free and idempotent, not `copilot mcp add`) and validates it with the same
real initialize/list-tools handshake used for Codex/OpenCode. `copilot mcp list`
(login-free) then shows the server. MCP, skill, and instruction installation
work **without** a GitHub login; only a live model turn
needs `copilot` `/login`.

Copilot exposes the generated personal skills as slash commands. Use
`/sessiestart` for explicit maintenance and `/sessielog` to capture the session.
KennisBank registers one start and one exit coordinator. At startup, Copilot
import precedes the concurrent index phase and notices follow it. At exit, the
sessionEnd event is captured first; immediate import and usage attribution then
run concurrently. Copilot may still display one generic row per lifecycle
event.

Manual MCP shape (`~/.copilot/mcp-config.json`, top-level `mcpServers`,
Claude-Desktop style; `type: "local"` for the stdio server; literal env values,
no `${VAR}` interpolation):

```json
{
  "mcpServers": {
    "kennisbank": {
      "type": "local",
      "command": "py",
      "args": ["-3", "/absolute/path/to/vault/.claude/scripts/kb-mcp.py"],
      "env": {
        "KENNISBANK_VAULT": "/absolute/path/to/vault",
        "KB_LLM_PROVIDERS": "ollama",
        "KB_LLM_MODEL": "gemma4:12b",
        "KB_LLM_ENDPOINT": "http://localhost:11434"
      },
      "tools": ["*"]
    }
  }
}
```

On macOS/Linux the command is `python3` with `args`
`["/absolute/path/to/vault/.claude/scripts/kb-mcp.py"]` (no `-3`).

Run Copilot through the wrapper to pin the vault and local-LLM env:

```bash
python3 <vault>/.claude/scripts/kennisbank-copilot.py            # execs the real copilot
python3 <vault>/.claude/scripts/kennisbank-copilot.py --kb-doctor   # JSON probe, works offline
python3 <vault>/.claude/scripts/kennisbank-copilot.py --no-capture  # do not record this session
```

The wrapper is a trivial exec: it sets `KENNISBANK_VAULT` + the local-LLM env,
runs a fast fail-open validation, then hands off to the real `copilot` preserving
argv and exit code. `--kb-doctor`, `--kb-dry-run`, and `--kb-print-env` work
without a GitHub login. Point `KENNISBANK_COPILOT_BIN` at the binary when it is
not on `PATH`.

### How Copilot activity becomes recall

The start and exit coordinators capture their lifecycle events; dedicated
fail-open hooks capture prompts and tools. `/sessielog` provides explicit
on-demand semantic capture and invokes `kb-session-log.py` once for mechanical
post-save work. At exit, `import-copilot.py --include-active` immediately
normalizes the completed staging stream into
`01-raw/transcripts/copilot-<sid>.jsonl`. Normal startup import retains
idempotent dedupe and active-session skip. `import-copilot.py --include-history`
additionally imports Copilot's own session-state on a best-effort basis.

`build-activity-index.py` then indexes them (reported as `copilot_events`), so
`/watdeedik`, `/timeline`, and the MCP temporal tools `what_did_i_do`,
`timeline`, `weeklog`, and `topic_timeline` surface Copilot activity alongside the
other agents'.

## Other MCP Clients

Other compatible local MCP clients can point to the same stdio server. Use the
client's native MCP config format and include
`KENNISBANK_VAULT` in the server environment when the vault is not at the
default path. Manual clients must install the MCP SDK into the same Python
interpreter used by the configured command.

```json
{
  "servers": {
    "kennisbank": {
      "command": "py",
      "args": ["-3", "/absolute/path/to/vault/.claude/scripts/kb-mcp.py"],
      "env": {
        "KENNISBANK_VAULT": "/absolute/path/to/vault"
      }
    }
  }
}
```

The server exposes:

- `recall(query, k)` for wiki/memory retrieval.
- `capture(title, body, memory_type, importance)` for unverified memory capture.
- `what_did_i_do(date_or_period, topic, project, max_events)` for compact date
  or period recall.
- `timeline(period, topic, project, max_events)` for chronological activity.
- `weeklog(period, topic, project, max_events)` for weekly rollups.
- `topic_timeline(topic, period, project, max_events)` for following an
  entity/topic through time.

All temporal tools read `<vault>/.claude/kb-activity.db`. If the index is
missing or stale, run:

```bash
python3 <vault>/.claude/scripts/build-activity-index.py --vault <vault> --full
```

## Hosted Agents

Hosted agents cannot reach a local stdio MCP server without tunnelling. Do not
tunnel a personal vault by default. Use manual export/import or a deliberate
bridge only when the user explicitly accepts that data boundary.
