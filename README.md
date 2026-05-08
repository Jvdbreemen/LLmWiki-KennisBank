# LLmWiki-KennisBank

A personal LLM wiki layer for [Claude Code](https://claude.ai/code). Captures knowledge from Claude sessions, compiles it into a searchable wiki, and keeps it fresh over time.

Based on [Andrej Karpathy's LLM Wiki pattern](https://x.com/karpathy): raw sessions go in, structured knowledge comes out.

## The pattern

```
raw sessions → compile → wiki → query
```

Every Claude session produces a session log. The `/wiki` command compiles logs into structured articles. The `/stale` command flags articles that need updating. The `/autoresearch` skill researches any topic and feeds its output back into the same pipeline.

## What's included

| Component | Purpose |
|-----------|---------|
| `commands/sessielog.md` | `/sessielog` command: write session log + compile wiki candidates |
| `commands/wiki.md` | `/wiki` command: compile raw logs into wiki articles |
| `commands/intake.md` | `/intake` command: process files dropped in `00-inbox/` |
| `commands/stale.md` | `/stale` command: detect and update stale wiki articles |
| `skills/autoresearch/` | `/autoresearch` skill: iterative multi-round web research |
| `scripts/auto-crosslink.py` | Add backlinks based on knowledge graph (graphify integration) |
| `scripts/stale-check.py` | Detect wiki articles older than threshold with newer session logs |
| `scripts/intake-scan.py` | Scan inbox and classify files by type |
| `scripts/semantic-tiling.py` | Detect near-duplicate articles via Ollama embeddings |
| `templates/tpl-sessie-log.md` | Session log template |
| `templates/tpl-wiki-artikel.md` | Wiki article template |
| `vault-structure/README.md` | Documentation of the vault directory layout |
| `CLAUDE.md.template` | Template for `~/KennisBank/CLAUDE.md` |
| `setup.sh` | One-command setup |

## Prerequisites

- [Claude Code](https://claude.ai/code) (CLI)
- Python 3.10+
- [Ollama](https://ollama.com) with `nomic-embed-text` (optional, for semantic deduplication)

The setup creates two root directories:
- `~/KennisBank/` — the vault (wiki, logs, templates, scripts)
- `~/Claude/research/` — output directory for `/autoresearch` (separate from the vault so research files stay editable without cluttering raw logs)

Both paths are configurable — see [Customization](#customization).

## Documentation

| File | For |
|------|-----|
| [AGENTS.md](AGENTS.md) | AI coding agents (Claude Code, Cursor, Aider) installing this on a user's behalf |
| [POST-INSTALL.md](POST-INSTALL.md) | First-session walkthrough after `setup.sh` finishes |
| [CONFIGURATION.md](CONFIGURATION.md) | Every configurable knob: paths, thresholds, models |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Symptom / cause / fix for common problems |
| [OBSIDIAN.md](OBSIDIAN.md) | Open the vault in Obsidian, recommended free plugins |
| [vault-structure/README.md](vault-structure/README.md) | Directory-by-directory reference |

## Installation

```bash
git clone https://github.com/Jvdbreemen/LLmWiki-KennisBank.git
cd LLmWiki-KennisBank
bash setup.sh           # interactive
bash setup.sh --yes     # non-interactive (recommended for AI agents)
bash scripts/doctor.sh  # verify install
```

The setup script will:
1. Create the vault directory structure under `~/KennisBank/`
2. Copy scripts and templates into place
3. Ask whether to install commands and the autoresearch skill into `~/.claude/` (skipped with `--yes`)

After install, run `bash scripts/doctor.sh` to verify, then read [POST-INSTALL.md](POST-INSTALL.md) for the first-session walkthrough.

### Manual installation

```bash
# Create vault
mkdir -p ~/KennisBank/{00-inbox,01-raw/sessies,02-wiki,03-projecten,04-templates,05-bronnen,06-claude,07-media,08-archive}
mkdir -p ~/KennisBank/.claude/scripts ~/KennisBank/graphify-out

# Scripts
cp scripts/*.py ~/KennisBank/.claude/scripts/

# Templates
cp templates/*.md ~/KennisBank/04-templates/

# CLAUDE.md
cp CLAUDE.md.template ~/KennisBank/CLAUDE.md

# Commands (Claude Code reads these as slash commands)
cp commands/*.md ~/.claude/commands/

# autoresearch skill
mkdir -p ~/.claude/skills/autoresearch
cp skills/autoresearch/SKILL.md ~/.claude/skills/autoresearch/
```

## Commands reference

| Command | Arguments | What it does |
|---------|-----------|--------------|
| `/sessielog` | none | Writes session log, compiles wiki candidates, runs semantic tiling |
| `/wiki` | optional topic | Compiles raw logs (last 7 days) into wiki articles |
| `/intake` | none | Processes files in `~/KennisBank/00-inbox/` |
| `/stale` | none | Detects articles older than 60 days with newer session data |
| `/autoresearch` | topic | Multi-round web research, saves to `~/Claude/research/` |

## Vault structure

```
~/KennisBank/
  00-inbox/        Drop files here for processing
  01-raw/
    sessies/       Session logs (raw-sessie-YYYY-MM-DD-topic.md)
  02-wiki/         Compiled wiki articles
  03-projecten/    Project-specific notes
  04-templates/    Article and log templates
  05-bronnen/      Source materials and references
  06-claude/       Claude-internal context files
  07-media/        Media descriptions and assets
  08-archive/      Archived articles
  .claude/
    scripts/       Python utility scripts
  graphify-out/    Knowledge graph output (optional)
```

## Memory path

Commands in this system detect your Claude memory file automatically:

```bash
ls ~/.claude/projects/*/memory/MEMORY.md 2>/dev/null | head -1
```

Your memory files live under `~/.claude/projects/`. The path segment is a slug of your working directory.

## Customization

1. Edit `~/KennisBank/CLAUDE.md` after setup. Replace `[YOUR NAME]` and `[YOUR PROJECTS]` with your own.
2. The commands are in Dutch by default (they follow prompt language). Change section headings if you prefer English.
3. To change the stale threshold (default 60 days): edit `THRESHOLD_DAYS` in `stale-check.py` or pass `--days N` on the CLI.
4. To change the research output path from `~/Claude/research/` to something else, edit two places:
   - `setup.sh`: change the `RESEARCH` variable
   - `skills/autoresearch/SKILL.md`: change the output path in the "Output aanmaken" section and the report
5. Semantic tiling requires Ollama:
   ```bash
   ollama pull nomic-embed-text
   ```
5. To enable the `/autoresearch` trigger in Claude Code, add this to your global `~/.claude/CLAUDE.md`:
   ```
   # autoresearch
   - **autoresearch** (`~/.claude/skills/autoresearch/SKILL.md`) - multi-round research with lazy hierarchy check. Output to `~/Claude/research/`. Trigger: `/autoresearch`
   When the user types `/autoresearch`, invoke the Skill tool with `skill: "autoresearch"` before doing anything else.
   ```

## Optional: graphify integration

The `auto-crosslink.py` script reads from `~/KennisBank/graphify-out/graph.json`. This is produced by the graphify skill when run on the vault. Without it, the crosslink step is silently skipped.

## Credits

- Pattern: [Andrej Karpathy's LLM Wiki concept](https://x.com/karpathy)
- Vault/CMS inspiration: [claude-obsidian by AgriciDaniel](https://github.com/AgriciDaniel/claude-obsidian)

## License

MIT. See [LICENSE](LICENSE).
