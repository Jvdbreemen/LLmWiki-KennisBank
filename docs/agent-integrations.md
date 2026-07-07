# Agent Integrations

KennisBank is local-only. Every supported local client points at the same vault
and the same stdio MCP server:

```text
<vault>/.claude/scripts/kb-mcp.py
```

Do not rely on the default `~/KennisBank` path when the user has a different
vault. Run setup with the active vault path:

```bash
KENNISBANK_VAULT="/absolute/path/to/vault" bash setup.sh --yes --agents claude,codex,opencode
```

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

Claude Code receives the complete hookset: `SessionStart`, `UserPromptSubmit`,
`PreToolUse`, and `SessionEnd`. The hook scripts are fail-open and keep user
settings intact.

## Codex

Installed by `--agents codex`.

- Skills: `~/.agents/skills/<name>/SKILL.md`
- Prompt aliases: `~/.codex/prompts/*.md`
- Global instructions: `~/.codex/AGENTS.md`
- Hooks: `~/.codex/hooks.json`
- MCP: `~/.codex/config.toml`, server name `kennisbank`

Codex custom prompt files are invoked as `/prompts:<name>`, not as bare custom
slash commands. For example:

```text
/prompts:sessielog
/prompts:sessiestart
/prompts:kennisbank-upgrade
/prompts:weeklog
/prompts:timeline
/prompts:watdeedik
```

Codex should use the installed skills for reusable workflows and the MCP tools
`recall` and `capture` for live vault access. For temporal questions, use
`what_did_i_do`, `timeline`, `weeklog`, or `topic_timeline` before generic
recall. Hooks are installed for lifecycle maintenance and best-effort recall,
but MCP is the durable cross-client API.
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

## Other MCP Clients

Cursor, Cline, Windsurf, Gemini CLI, and similar local MCP clients can point to
the same stdio server. Use the client's native MCP config format and include
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
