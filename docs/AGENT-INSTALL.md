# Agent install guide

This guide is written **for AI agents** (and the humans supervising them) that
install LLmWiki-KennisBank. It gives the shortest correct path per platform.
The full deployment contract lives in [`AGENTS.md`](../AGENTS.md); when this
guide and `AGENTS.md` disagree, `AGENTS.md` wins.

## TL;DR for an agent

```bash
git clone https://github.com/Jvdbreemen/LLmWiki-KennisBank.git
cd LLmWiki-KennisBank
KENNISBANK_VAULT="/absolute/path/to/vault" bash setup.sh --yes --agents claude,codex
```

`setup.sh` is the **single supported entrypoint** for install and upgrade. Do
not hand-copy files. It is idempotent: re-running repairs a broken install and
preserves user data (`CLAUDE.md`, settings values, existing hooks that are not
KennisBank's).

Three rules that prevent the most common breakage:

1. **Never assume the vault path.** Resolve in this order:
   `KENNISBANK_VAULT` env var → a user-provided path → only then the default
   `~/KennisBank`. Pass it explicitly on every setup call.
2. **On Windows, use Git Bash** (`C:\Program Files\Git\bin\bash.exe`), not the
   System32 `bash.exe` (that is WSL and writes Linux-shaped paths into Windows
   agent configs). Hooks run under `py -3`; POSIX systems use `python3`.
3. **Verify, then stop.** After setup, run
   `bash "$VAULT/.claude/scripts/doctor.sh"` and report the PASS/WARN/FAIL
   counts. Do not "fix" WARNs the user did not ask about.

Prerequisites: `git`, Python 3.10+, and — for local embeddings and the memory
judge — [Ollama](https://ollama.com) with `qwen3-embedding:8b`. Setup validates
models unless `--skip-model-check` is passed (CI/offline only).

## Platform matrix

| Capability | Claude Code | Codex CLI | Copilot CLI | OpenCode | Claude Cowork |
|---|---|---|---|---|---|
| Slash commands / skills | yes (`/sessielog`, …) | yes (`$sessielog` prompts + skills) | yes (personal skills) | yes | partial (skills/plugin, no hooks) |
| Session start/exit coordinators | yes (hooks) | yes (hooks) | yes (hooks) | yes | no |
| Prompt-time retrieval hook | yes | no (MCP pull) | no (MCP pull) | no (MCP pull) | no (MCP pull) |
| Local MCP server (`recall`, temporal tools) | yes | yes | yes | yes | yes, via connector/plugin |
| Install target | `--agents claude` | `--agents codex` | `--agents copilot` | `--agents opencode` | manual (see below) |

## Claude Code

```bash
KENNISBANK_VAULT="/absolute/path/to/vault" bash setup.sh --yes --agents claude
```

What lands where:

- Scripts → `$VAULT/.claude/scripts/`, templates → `$VAULT/04-templates/`
- Commands → `~/.claude/commands/`, skills → `~/.claude/skills/<name>/`
- Hooks registered in `~/.claude/settings.json` (SessionStart, SessionEnd,
  UserPromptSubmit, PreToolUse, PreCompact) with `KENNISBANK_VAULT` pinned in
  `env`. Existing non-KennisBank hooks are preserved; a hand-edited but invalid
  `settings.json` makes registration refuse rather than clobber.

Restart Claude Code after install: hooks and MCP servers load at startup.

Windows PowerShell example:

```powershell
$env:KENNISBANK_VAULT = "D:/path/to/vault"
& "C:\Program Files\Git\bin\bash.exe" setup.sh --yes --agents claude
```

## Codex CLI

```bash
KENNISBANK_VAULT="/absolute/path/to/vault" bash setup.sh --yes --agents codex
```

- Skills and prompt aliases land under `~/.agents/skills/` and Codex prompts;
  commands are invoked as `$<name>` (e.g. `$sessielog`), nested ones as
  `/prompts:<name>`.
- One KennisBank SessionStart coordinator and one Stop coordinator are
  registered in the Codex hook config; both fail open.
- The local stdio MCP server (`kb-mcp.py`) is registered with the same pinned
  vault path; setup validates it with a real initialize/list-tools handshake.

## GitHub Copilot CLI

Opt-in and not in the default target set (the standalone `@github/copilot`
CLI v1.0.70+, invoked as `copilot` — **not** the `gh copilot` extension, not
VS Code agent mode):

```bash
KENNISBANK_VAULT="/absolute/path/to/vault" bash setup.sh --yes --agents copilot
```

- MCP config: key-scoped read-modify-write of `mcpServers.kennisbank` in
  `~/.copilot/mcp-config.json` — never a whole-file overwrite.
- Freeform files (`~/.copilot/copilot-instructions.md`, agent profile) get a
  marker-delimited managed block with a backup before any edit.
- Skills are shared with Codex/OpenCode under `~/.agents/skills/` and appear
  as slash commands. One sessionStart and one sessionEnd coordinator are
  registered; Copilot hooks are wrapped fail-open (a non-zero exit would be
  fail-closed in Copilot's preToolUse model).

## OpenCode

```bash
KENNISBANK_VAULT="/absolute/path/to/vault" bash setup.sh --yes --agents opencode
```

Commands, skills, MCP config, `AGENTS.md` block, and the OpenCode plugin.

## Claude Cowork

Cowork (the Claude Desktop Cowork tab) has a different extensibility model:
**plugins, skills, and MCP connectors — no Claude Code-style hooks**. That
means the automatic layer (session coordinators, prompt-time retrieval,
transcript archiving) does not run there. What works today:

- **Knowledge retrieval via MCP**: the same local stdio server
  (`$VAULT/.claude/scripts/kb-mcp.py`) can be added as a local MCP server
  (Settings → Developer, when enabled) or shipped inside a plugin's
  `.mcp.json`. This gives Cowork the `recall` and temporal tools
  (`what_did_i_do`, `timeline`, `weeklog`, `topic_timeline`).
- **Skills**: users can add skills through the in-app Plugins/Skills UI, or an
  admin can distribute a plugin (bundling `skills/`, `commands/` and
  `.mcp.json`) through a plugin marketplace or the org-plugins directory.
- **Not available**: hook-driven capture and push-retrieval. Knowledge flows
  into the vault from your CLI agents; Cowork is a read-mostly client.

There is no `--agents cowork` target yet. If you want one, the pieces exist
(the MCP server and the skill set are client-agnostic); track it as a feature
request. Verified against the Claude Desktop 3P extensions documentation
(claude.com/docs/cowork/3p/extensions) as of 2026-07; Cowork evolves quickly,
so re-check before relying on this section.

## Verify

```bash
bash "$VAULT/.claude/scripts/doctor.sh"
```

Report the summary (PASS/WARN/FAIL). A healthy install ends with zero FAIL.
Then restart the agent client so hooks and MCP tools load.

## Upgrade

Deployed vaults upgrade with the `kennisbank-upgrade` skill
(`/kennisbank-upgrade` in Claude Code) or by re-running `setup.sh` from the
latest release tag — never from bare `main`. See `AGENTS.md` for the drift
guard and backup conventions.
