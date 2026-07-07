# Agent Integrations

KennisBank is local-only. Every client below points at the same stdio MCP server:
`python3 /absolute/path/to/vault/.claude/scripts/kb-mcp.py`

## Codex CLI

```toml
[mcp_servers.kennisbank]
command = "python3"
args = ["/absolute/path/to/vault/.claude/scripts/kb-mcp.py"]
```

## Cursor

```json
{
  "servers": {
    "kennisbank": {
      "command": "python3",
      "args": ["/absolute/path/to/vault/.claude/scripts/kb-mcp.py"]
    }
  }
}
```

## Cline

```json
{
  "servers": {
    "kennisbank": {
      "command": "python3",
      "args": ["/absolute/path/to/vault/.claude/scripts/kb-mcp.py"]
    }
  }
}
```

## Windsurf

```json
{
  "servers": {
    "kennisbank": {
      "command": "python3",
      "args": ["/absolute/path/to/vault/.claude/scripts/kb-mcp.py"]
    }
  }
}
```

## Gemini CLI

```json
{
  "servers": {
    "kennisbank": {
      "command": "python3",
      "args": ["/absolute/path/to/vault/.claude/scripts/kb-mcp.py"]
    }
  }
}
```

## Claude Code

```json
{
  "servers": {
    "kennisbank": {
      "command": "python3",
      "args": ["/absolute/path/to/vault/.claude/scripts/kb-mcp.py"]
    }
  }
}
```

## Native push adapter

`.github/copilot-instructions.md` is the first native push-inject adapter in the
repo: Copilot agent mode reads instructions from that file, so the KennisBank
nudge can be pushed without a bespoke installer.

## Installer

`kennisbank install --client X` is intentionally deferred for now. The current
setup path already registers the MCP server explicitly, and the adapter needs
are small enough to keep manual until a real multi-client installer is worth
the extra surface.
