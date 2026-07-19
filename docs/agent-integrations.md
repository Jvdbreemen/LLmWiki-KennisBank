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

Claude Code receives the complete hookset: `SessionStart`, `UserPromptSubmit`,
`PreToolUse`, and `SessionEnd`. The hook scripts are fail-open and keep user
settings intact. Routine maintenance runs through `quiet-hook.py`; successful
no-change index, sweep, archive, and telemetry hooks emit no user-facing
output. Changed indexes and warnings become concise session reports. Retrieval,
reports, and actionable notices use structured `additionalContext` with
`suppressOutput`, so the agent receives useful context without raw hook chatter.

## Codex

Installed by `--agents codex`.

- Skills: `~/.agents/skills/<name>/SKILL.md`
- Prompt aliases: `~/.codex/prompts/*.md`
- Global instructions: `~/.codex/AGENTS.md`
- MCP: `~/.codex/config.toml`, server name `kennisbank`

Use `$sessiestart` and `$sessielog` as native Codex skills. Compatibility
prompts are invoked as `/prompts:<name>`:

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
recall. KennisBank installs no Codex lifecycle hooks because the client renders
rows for registered hooks and `suppressOutput` is not implemented. Setup removes
only legacy KennisBank entries and preserves unrelated hooks.
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
`gh copilot` gh-extension and not Copilot's VS Code agent mode. The original
design is [ADR-0003](adr/0003-copilot-cli-integration.md); its hook
decision is superseded by
[ADR-005](adr/ADR-005-hookless-codex-copilot-integration.md). The wrapper's
"trivial exec, not a proxy" stance is derived in
[docs/copilot-headroom-evaluation.md](copilot-headroom-evaluation.md).

- Skills: `~/.agents/skills/<name>/SKILL.md` (shared with Codex/OpenCode; no
  separate install — list with `copilot skill list`)
- MCP: `~/.copilot/mcp-config.json`, server name `kennisbank`
- Personal instructions: `~/.copilot/copilot-instructions.md` (KennisBank managed block)
- Custom agent profile: `~/.copilot/agents/kennisbank.agent.md`, selected with
  `copilot --agent kennisbank` (the `.agent.md` extension is required)
- Wrapper/launcher: `<vault>/.claude/scripts/kennisbank-copilot.py`
- Config home: `~/.copilot` (Windows `%USERPROFILE%\.copilot`); `COPILOT_HOME` overrides it

All user-level paths honor `COPILOT_HOME`. KennisBank writes **only** its own
namespaced keys and marker-delimited blocks: `mcpServers.kennisbank` in the MCP
file and a managed block in the freeform instruction files. Upgrade removes
only known KennisBank hook commands. It never rewrites unmanaged Copilot config,
and it backs up
any freeform file before editing.

`setup.sh --agents copilot` registers the MCP server by a key-scoped JSON merge
(login-free and idempotent, not `copilot mcp add`) and validates it with the same
real initialize/list-tools handshake used for Codex/OpenCode. `copilot mcp list`
(login-free) then shows the server. MCP, skill, and instruction installation
work **without** a GitHub login; only a live model turn
needs `copilot` `/login`.

Use `/sessiestart` for explicit maintenance and `/sessielog` to capture the
session. No KennisBank lifecycle hooks means no KennisBank hook rows.

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

Use `/sessielog` to capture the current session. Existing event data remains
importable: `import-copilot.py` normalizes it into
  `01-raw/transcripts/copilot-<sid>.jsonl` (idempotent dedupe, active-session
  skip). `import-copilot.py --include-history` additionally does a best-effort
  import of Copilot's own session-state.

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
