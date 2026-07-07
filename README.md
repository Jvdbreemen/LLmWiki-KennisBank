# LLmWiki-KennisBank

**A memory that learns, for people who work with AI.**

Every Claude session ends the same way: the model forgets everything, and the knowledge you built together evaporates. KennisBank fixes that. It is a local-first knowledge and memory layer for [Claude Code](https://claude.ai/code) that captures what you learn, compiles it into a durable wiki, remembers facts with a validity window, retrieves the right knowledge automatically into every new session, and then measures whether that knowledge actually helped.

Plain markdown. Local models. Your own machine. You stay the editor-in-chief: the system proposes, quarantines, and flags, but a human merges, supersedes, and decides. No cloud dependency, no vendor lock-in, no data leaving your house. Open the vault in Obsidian and it is just... notes. Very well-organized notes that happen to power an AI memory.

Based on [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): raw sessions go in, structured knowledge comes out. KennisBank extends the pattern into a closed loop:

```
capture ──> consolidate ──> retrieve ──> measure
   ^                                        │
   └────────────── learn <─────────────────┘
```

- **Capture**: session logs, transcript archiving, and an autonomous memory sweep that extracts, types, and judges candidate memories after each session.
- **Consolidate**: `/wiki` compiles sessions into wiki articles with per-claim provenance; new facts reconcile against old ones at write time (add, supersede, or drop) with a bi-temporal validity model.
- **Retrieve**: hooks inject relevant wiki articles and memories into every prompt, in any project: hybrid semantic + keyword search, ranked by relevance x recency x importance, expanded with the best-connected graph neighbour.
- **Measure**: a recall@k eval harness and a threshold calibration harness make every retrieval change testable instead of vibes-based.
- **Learn**: usage telemetry tracks which injected knowledge was actually used, boosting warm documents and keeping recently-used articles out of the stale list.

## Why this exists

Vendor memory systems (Mem0, Zep, Letta, Cognee) are powerful but cloud-shaped: your knowledge lives in their store, behind their API, on their pricing tier. KennisBank takes the two mechanisms that actually matter from that literature, temporal validity of facts and invalidation-at-write, and rebuilds them in plain markdown frontmatter plus SQLite. What you own stays portable; what the agent needs stays fast.

The design bias throughout: **deterministic where possible, LLM only where it adds judgment, fail-open everywhere**. A dead model never blocks a session, never loses a transcript, and never deletes verified knowledge.

## Feature highlights (v0.9.0)

### Knowledge (the wiki layer)
- `/wiki` compiles raw session logs into interlinked wiki articles, updating existing ones via a guarded rewrite engine (`safe-edit.py`) instead of clobbering them.
- **Provenance-lint** (`kb-lint.py`): every article must trace back to its sources with resolving wikilinks to a raw session or an imported source; `/wiki` writes that provenance per key point at distillation time. A hallucination during distillation can no longer become a permanent "fact" that nobody can check.
- `/stale` finds outdated articles, and usage telemetry keeps warm articles out of the list: an article you used last week is not stale, however old its `updated` date.
- Thinking tools: `/reconcile` surfaces contradictions between articles, `/uitdaag` adversarially challenges a claim, `/brug` finds conceptual bridges between two topics.

### Memory (the agent layer)
- An autonomous **capture sweep** runs detached in the background (launched at session start, over transcripts archived at session end): extract candidates, type them (`feit`, `voorkeur`, `procedure`, `beslissing`), deduplicate, and let an independent judge decide `current` versus quarantine (`unverified`) with an importance score (1-5).
- **Bi-temporal validity**: every memory carries `valid_from` (event time, from the session date) separate from `created` (capture time); superseding or expiring a fact stamps `valid_until`. The system knows not just what is true, but since when and until when.
- **Write-time invalidation** (Mem0 pattern, local): a new fact reconciles against the most similar existing memories at write time: ADD, SUPERSEDE (the old fact is closed and linked), or NOOP. A deterministic temporal guard ensures an older fact can never invalidate a newer one, so bulk re-imports are safe.
- Cross-memory maintenance: supersede pass, noise recheck, and cluster promotion (recurring themes get flagged as wiki candidates).

### Retrieval (the hooks layer)
- **Every prompt, every project**: a UserPromptSubmit hook embeds your prompt and injects the top-matching wiki articles and memories as context. A PreToolUse hook checks the vault before Claude searches the web.
- Hybrid index (`kb-index.db`): semantic vectors (sqlite-vec) fused with FTS5 keyword search, so exact terms are found even when embeddings miss them.
- Ranking: relevance x recency (half-life per memory type) x importance, plus a usage boost for documents that recently proved useful.
- **Graph-neighbour expansion**: the most-referenced wikilink neighbour of your hits rides along as one extra entry, turning loose hits into a coherent knowledge neighbourhood.

### Measurement (the trust layer)
- `kb-eval.py`: recall@1/3/5 and MRR against your personal eval set of questions. Run it before and after any retrieval change; a drop is a regression, not an opinion.
- `kb-calibrate.py`: checks all cosine thresholds (dedup, rewrite, reconcile, conflict, retrieve) against the active embedding model using a hand-labelled pair set, and proposes boundaries with separation margins. It writes nothing: you decide. Switch embedding models without silently degrading.
- `doctor.sh`: one command verifies the whole install, from vault layout and hook registration to provenance coverage.

### Sovereignty (the whole point)
- Local Ollama models for both embeddings and judgment, swappable via config (`kennisbank-embed.json`, `kennisbank-llm.json`); OpenAI-compatible endpoints supported when you choose to.
- Everything is markdown + SQLite in a folder you own. Obsidian-compatible. MIT-licensed.
- Human update authority: agents never silently delete; superseded knowledge is closed and linked, quarantined knowledge cannot displace verified knowledge, and large rewrites require your confirmation.

## Prerequisites

- [Claude Code](https://claude.ai/code) (CLI)
- Python 3.10+
- [Ollama](https://ollama.com) with:
  - `qwen3-embedding:8b` (embeddings; multilingual default. English-only vaults can use the lighter `nomic-embed-text`)
  - a chat model for the memory judge/extraction (default `gemma4:latest`; pin another via `<vault>/.claude/kennisbank-llm.json`)

Ollama is optional in the sense that everything fails open without it, but the memory sweep, semantic retrieval, and deduplication are the heart of the system: install it.

The setup creates two root directories:
- `~/KennisBank/` — the vault (wiki, logs, memory, templates, scripts)
- `~/Claude/research/` — output directory for `/autoresearch`

Both paths are configurable — see [Customization](#customization).

## Installation

```bash
git clone https://github.com/Jvdbreemen/LLmWiki-KennisBank.git
cd LLmWiki-KennisBank
bash setup.sh           # interactive
bash setup.sh --yes     # non-interactive (recommended for AI agents)
bash scripts/doctor.sh  # verify install
```

In one idempotent run, the setup script:
- creates the vault directory structure under `~/KennisBank/`
- copies scripts and templates into place
- bootstraps the settings toggles and runs version-gated migrations
- asks whether to install commands and skills into `~/.claude/` (auto-yes with `--yes`)
- registers the full hookset in `~/.claude/settings.json` (skip with `--no-hooks`)

**Re-running `setup.sh` is safe and is the upgrade mechanism**: it refreshes tooling without clobbering user data, customizations, or vault contents. The `/kennisbank-upgrade` skill wraps it with release-tag checkout, drift detection, and backups.

After install, read [POST-INSTALL.md](POST-INSTALL.md) for the first-session walkthrough.

### The hookset

| Hook | Script | What it does |
|------|--------|--------------|
| SessionStart | `build-embed-index.py` | Warm the wiki embedding cache (incremental) |
| SessionStart | `build-kb-index.py` | Refresh the hybrid vector+FTS index |
| SessionStart | `sweep-launch.py` | Launch the detached memory capture sweep |
| SessionStart | `memory-notify.py` | Report memory-quarantine health |
| SessionStart | `distill-notify.py` | Report transcripts waiting for distillation |
| UserPromptSubmit | `kb-retrieve.py` | Inject matching wiki + memory context into the prompt |
| SessionEnd | `archive-transcript.py` | Archive the session transcript into the vault |
| SessionEnd | `kb-usage-scan.py` | Mark which injected knowledge was actually used |
| PreToolUse (WebSearch\|WebFetch) | `kb-presearch.py` | Consult the vault before searching the web |

The hooks are fail-open by design: an error means no injected context or a skipped background step, never a blocked session.

## Commands reference

| Command | Arguments | What it does |
|---------|-----------|--------------|
| `/sessielog` | none | Writes session log, compiles wiki candidates, runs semantic tiling |
| `/sessiestart` | none | Read vault context, memory, wiki status, suggest next actions |
| `/wiki` | optional topic | Compiles raw logs (last 7 days) into wiki articles with per-key-point provenance, validated by kb-lint |
| `/intake` | none | Processes files in `~/KennisBank/00-inbox/` |
| `/stale` | none | Detects articles older than 60 days, skipping recently-used ones |
| `/import` | `cc` \| `claudeai <path>` \| `folder <path> [prefix]` \| `cowork` \| `all` | Bulk-import old sessions from Claude Code history, a claude.ai export bundle, any markdown folder, or Mac desktop Claude data; `all` runs every detected source, no argument asks interactively |
| `/destilleer` | none | Imports archived CC transcripts and compiles them into the wiki |
| `/autoresearch` | topic | Multi-round web research via the autoresearch skill (not a command file), saves to `~/Claude/research/` |
| `/reconcile` | optional topic | Surface contradictions across wiki articles and produce a reconciliation log |
| `/uitdaag` | claim or decision | Adversarially challenge a claim for weak reasoning or missing evidence |
| `/brug` | two topics | Find conceptual bridges and shared principles between two topics |
| `/kennisbank:settings` | none | Show and flip the background-automation toggles |
| `/kennisbank:rebuild-index` | none | Rebuild the hybrid search index from the vault markdown |
| `/kennisbank:rebuild-memory` | none | Re-extract ALL memory from archived transcripts (heavy; semantic dedup makes it near-idempotent) |
| `/kennisbank-upgrade` | optional `--dry-run` | Upgrade the deployed vault to the latest release tag |
| `/kennisbank-contribute` | optional `--dry-run` | PR local tooling edits back upstream |

## Skills

Three skills ship with the system and are installed into `~/.claude/skills/` by `setup.sh`. Commands are single prompts; skills are multi-step procedures with their own guardrails.

| Skill | Invoked via | What it does |
|-------|-------------|--------------|
| `autoresearch` | `/autoresearch <topic>` or "research/deep dive/onderzoek [topic]" | Autonomous iterative research loop: multi-round web searches, synthesis, and one structured, cited document in `~/Claude/research/`. Checks your own vault first (lazy hierarchy) so research fills gaps instead of repeating what you already know. Built on Karpathy's autoresearch pattern. |
| `kennisbank-upgrade` | `/kennisbank-upgrade [--dry-run]` | Upgrades a deployed vault to the latest official release tag (never bare main): fetches tags, shows the changelog delta, detects local drift with a CRLF-agnostic diff, backs up drifted categories, deploys via `setup.sh`, stamps the installed version, and verifies with `doctor.sh`. |
| `kennisbank-contribute` | `/kennisbank-contribute [--dry-run]` | The reverse direction: isolates local tooling edits in a deployed vault (scripts, templates, commands, skills), filters out personal vault content, then branches, commits, pushes, and opens an upstream PR. Ownership equals durability: improvements survive the next upgrade because they land upstream. |

Upgrade and contribute are two halves of one loop: `contribute` sends your local improvements upstream, `upgrade` brings released improvements back down. A vault that follows both never drifts permanently from the project.

## Vault structure

```
~/KennisBank/
  00-inbox/        Drop files here for processing
  01-raw/
    sessies/       Session logs (raw-sessie-YYYY-MM-DD-topic.md)
    transcripts/   Archived Claude Code transcripts (SessionEnd hook)
  02-wiki/         Compiled wiki articles
  03-projecten/    Project-specific notes
  04-templates/    Article and log templates
  05-bronnen/      Source materials and references
  06-claude/       Claude-internal context files, eval + calibration sets
  07-media/        Media descriptions and asset metadata (not the binaries)
  08-archive/      Archived articles
  09-memory/       Agent memory (typed, judged, bi-temporal; archive/ for retired items)
  .claude/
    scripts/       Python + shell tooling (incl. doctor.sh)
    kb-index.db    Hybrid vector + FTS index (refreshed incrementally each session)
    kb-usage.db    Usage telemetry (survives rebuilds and model switches)
  graphify-out/    Knowledge graph output (optional)
```

## Background automation toggles

Seven background behaviours are individual toggles in `kennisbank-settings.json`, managed with `/kennisbank:settings`:

| Toggle | Default | Controls |
|--------|---------|----------|
| `auto_archive` | off | Archive the transcript at session end |
| `distill_notify` | on | Notify at start that transcripts are pending |
| `embed_index` | on | Refresh the wiki embedding cache at start |
| `daily_graphify` | on | Update the knowledge graph once a day |
| `memory_capture` | on | Extract and judge memories into `09-memory/` |
| `memory_recall` | on | Inject memories into context via hooks |
| `usage_telemetry` | on | Track which injected knowledge gets used |

## Measuring your retrieval

Two harnesses keep the system honest:

```bash
# recall@k against your personal eval set (06-claude/kb-eval-set.json)
python3 ~/KennisBank/.claude/scripts/kb-eval.py

# threshold calibration against the active embedding model
python3 ~/KennisBank/.claude/scripts/kb-calibrate.py
```

Maintain the eval set as your vault grows (questions you know the answer to, with the expected article), and run both harnesses after any change to thresholds, models, or ranking. Example sets ship in the repo root.

## Migrating from older Claude tooling

The `/import` command backfills the vault from existing Claude history. It handles Claude Code session JSONL files under `~/.claude/projects/`, claude.ai export bundles, Mac desktop Claude (Cowork) conversation data, and any generic markdown or text folder. Each importer writes raw session files that `/wiki` can compile afterwards. For the memory layer, `/kennisbank:rebuild-memory` re-extracts all archived transcripts through the full sweep (semantic dedup makes re-runs near-idempotent).

## Using KennisBank from other agents (Codex, Copilot, ChatGPT)

The vault is not Claude-Code-only. `scripts/kb-mcp.py` is a local **MCP server** exposing three primitives — `recall` (search memory + wiki), `capture` (save a new memory), and an `instructions` resource (a nudge to pull before searching externally). MCP is the one protocol every modern agent already speaks, so any client running **on this machine** can use the vault.

**The hard boundary: local only.** The MCP server binds nothing to the network (stdio transport); the vault never leaves your machine. Agents that run *on your machine* (Codex CLI, GitHub Copilot in VS Code, Claude Code, Cursor, Cline, Windsurf) reach it directly. Agents that run *in the cloud* (hosted ChatGPT) cannot reach a local stdio server, and the answer is **not** to tunnel your sovereign vault to the internet — it is the manual bridge below.

### Codex CLI — clean fit

Codex supports MCP over stdio. Register the server once:

```bash
codex mcp add kennisbank -- python3 /absolute/path/to/vault/.claude/scripts/kb-mcp.py
```

Or add it by hand to `~/.codex/config.toml` (or project-scoped `.codex/config.toml`):

```toml
[mcp_servers.kennisbank]
command = "python3"
args = ["/absolute/path/to/vault/.claude/scripts/kb-mcp.py"]
```

`recall` and `capture` are now available in Codex.

### GitHub Copilot (VS Code agent mode) — works, with one caveat

Copilot's agent mode supports MCP **tools** over stdio, but **not** MCP resources or prompts. So `recall` and `capture` work, but the `instructions` nudge (a resource) will not surface. Put the nudge in `.github/copilot-instructions.md` instead:

```markdown
You have a local KennisBank via MCP tools `recall` and `capture`.
Call `recall` before searching externally; call `capture` to save a reusable fact.
```

Register the server in VS Code settings (`mcp.json` / `"servers"`):

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

The wider adapter registry and the rest of the client snippets live in
[docs/agent-integrations.md](docs/agent-integrations.md).

### ChatGPT — the manual bridge (sovereignty first)

Hosted ChatGPT can only connect to **remote** MCP servers on the public internet; exposing a local server means tunnelling (Secure Tunnel / ngrok / Cloudflare), which routes your queries **and** the returned knowledge through OpenAI's infrastructure. That breaks the whole point of a sovereign vault, so KennisBank does not do it by default. Instead, **you** stay the gate:

```bash
python3 .claude/scripts/kb-ask.py "how did I fix the ESP32 BLE crash"
python3 .claude/scripts/kb-ask.py "my topic" --k 8 --clip   # also copy to clipboard
```

`kb-ask` retrieves locally and prints a ready-to-paste context block (a short instruction for the model, then the hits, then your question). Paste it at the top of your ChatGPT message. Nothing leaves the machine automatically — you choose what to share.

### ChatGPT data export — get control of your own chats back

You can pull your ChatGPT history *into* the sovereign vault, so lessons from those conversations become your own retrievable knowledge instead of living only in OpenAI's cloud:

1. In ChatGPT, open **Settings → Data controls → Export data** and confirm. (Requires being signed in on the web app.)
2. OpenAI emails you a download link within minutes to a day; the link is time-limited. Download the ZIP — it contains `conversations.json` (plus `chat.html`, media).
3. Import it into the vault:
   ```bash
   python3 .claude/scripts/import-chatgpt-export.py --input ~/Downloads/chatgpt-export.zip
   # preview first if you like:
   python3 .claude/scripts/import-chatgpt-export.py --input ~/Downloads/chatgpt-export.zip --dry-run --verbose
   ```
   Each conversation becomes a raw session log under `01-raw/sessies/`. Then run `/wiki` to compile them into articles and `/kennisbank:rebuild-memory` to extract the memory layer. Re-imports are skip-by-default (idempotent); pass `--force` to overwrite.

The importer walks ChatGPT's message *tree* (`mapping`), orders turns by timestamp, and keeps only your and the assistant's turns — system and tool nodes are dropped. It runs fully locally; nothing is sent anywhere.

## Documentation

| File | For |
|------|-----|
| [AGENTS.md](AGENTS.md) | AI coding agents (Claude Code, Cursor, Aider) installing this on a user's behalf |
| [POST-INSTALL.md](POST-INSTALL.md) | First-session walkthrough after `setup.sh` finishes |
| [CONFIGURATION.md](CONFIGURATION.md) | Every configurable knob: paths, thresholds, models, toggles |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Symptom / cause / fix for common problems |
| [OBSIDIAN.md](OBSIDIAN.md) | Open the vault in Obsidian, recommended free plugins |
| [CHANGELOG.md](CHANGELOG.md) | Release history, Keep a Changelog format |
| [vault-structure/README.md](vault-structure/README.md) | Directory-by-directory reference |

## Customization

1. Edit `~/KennisBank/CLAUDE.md` after setup. Replace `[YOUR NAME]` and `[YOUR PROJECTS]` with your own.
2. **Vault path.** All Python scripts and `doctor.sh` honor the `KENNISBANK_VAULT` environment variable (default `~/KennisBank`). See [CONFIGURATION.md](CONFIGURATION.md) section 9 for what the slash-command prompt files still hardcode.
3. **Embedding backend.** Swappable via `<vault>/.claude/kennisbank-embed.json` or `KB_EMBED_*` env vars: local Ollama by default, OpenAI-compatible endpoints when configured. Switching models invalidates the cache by design; run `kb-calibrate.py` afterwards to check the thresholds against the new model (it proposes values, you set them).
4. **LLM backend** (judge/extraction): `<vault>/.claude/kennisbank-llm.json` or `KB_LLM_*` env vars. Default Ollama `gemma4:latest`.
5. **Wiki categories.** `build-karpathy-index.py` groups articles using a built-in taxonomy; override with a `categories.json` (copy [`categories.example.json`](categories.example.json)).
6. The commands are in Dutch by default (they follow prompt language). Change section headings if you prefer English.
7. Stale threshold (default 60 days): pass `--days N` or edit `stale-check.py`.
8. `auto-crosslink.py` tunables: `MIN_CONFIDENCE` (default `0.75`) and `MAX_NEW_LINKS` (default `5`).
9. Research output path: changing it touches several places (`setup.sh`, the autoresearch skill, and the command prose) — see [CONFIGURATION.md](CONFIGURATION.md) section 5.
10. To enable the `/autoresearch` trigger, add this snippet to your global `~/.claude/CLAUDE.md`:
    ```
    # autoresearch
    - **autoresearch** (`~/.claude/skills/autoresearch/SKILL.md`) - multi-round research with lazy hierarchy check. Output to `~/Claude/research/`. Trigger: `/autoresearch`
    When the user types `/autoresearch`, invoke the Skill tool with `skill: "autoresearch"` before doing anything else.
    ```

## Optional: graphify integration

`auto-crosslink.py` reads from `~/KennisBank/graphify-out/graph.json`, produced by the graphify skill when run on the vault. Without it, the crosslink step is silently skipped. Retrieval benefits indirectly: the graph-neighbour expansion follows the wikilinks that crosslinking maintains.

## Optional: knowledge graph dashboard

[Understand-Anything](https://github.com/Lum1104/Understand-Anything) is a separate Claude Code plugin (MIT) that turns a Karpathy-pattern wiki into an interactive knowledge graph dashboard. Build the required index with `python3 scripts/build-karpathy-index.py`, then run `/understand-knowledge` inside `~/KennisBank/02-wiki`. See `--help` for flags; categories are customizable via `categories.json`.

## Credits

- Pattern: [Andrej Karpathy's LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- Vault/CMS inspiration: [claude-obsidian by AgriciDaniel](https://github.com/AgriciDaniel/claude-obsidian)
- Memory-architecture lessons: the public work around Mem0, Zep/Graphiti, Letta, and Cognee, rebuilt here local-first

## License

MIT. See [LICENSE](LICENSE).
