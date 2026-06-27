# Vault Structure

This documents the directory layout of `~/KennisBank/` after running `setup.sh`.

```
~/KennisBank/
  00-inbox/
  01-raw/
    sessies/
    transcripts/
  02-wiki/
  03-projecten/
  04-templates/
  05-bronnen/
  06-claude/
  07-media/
  08-archive/
  09-memory/
    archive/
  .claude/
    scripts/
  graphify-out/
  CLAUDE.md
```

## Directory reference

### `00-inbox/`
Drop zone for unprocessed files. Run `/intake` to process them.

Accepted: `.md`, `.txt`, `.pdf`, images (jpg/png/webp/gif), URL files (plain text file containing a single URL).

Processing routes:
- Markdown without frontmatter → `add_frontmatter` → `01-raw/`
- Markdown with frontmatter → `move_to_raw` → `01-raw/`
- Plain text → `convert_to_markdown` → `01-raw/`
- URL file → `fetch_and_convert` → `01-raw/raw-YYYY-MM-DD-slug.md`
- PDF → manual extraction required
- Image → description written to `07-media/`

### `01-raw/`
Raw, unprocessed notes and session logs. No editing for quality; just capture.

#### `01-raw/sessies/`
Session logs written by `/sessielog`. Naming convention: `raw-sessie-YYYY-MM-DD-topic.md`.

These are the source material for wiki compilation. Do not delete them -- stale-check.py cross-references session dates against wiki article update dates.

#### `01-raw/transcripts/`
Archived CC transcripts (`.jsonl`) written by the `SessionEnd` hook (`archive-transcript.py`). Naming convention: `YYYY-MM-DD-<project>-<sid8>.jsonl`. Created by `setup.sh`.

### `02-wiki/`
Compiled wiki articles. Each article covers one concept, tool, method, or pattern.

Naming convention: `slug-in-kebab-case.md`. Every article has YAML frontmatter with `title`, `type: wiki`, `tags`, `status`, `created`, `updated`.

Status values:
- `actief` — current and maintained
- `concept` — draft, not yet verified
- `stabiel` — no recent changes expected, archived conceptually but kept accessible
- `archief` — moved to `08-archive/` and removed from active wiki

### `03-projecten/`
Project-specific notes that don't belong in the general wiki. One subdirectory per project.

### `04-templates/`
Templates used by commands and scripts. Do not delete:
- `tpl-sessie-log.md` — used by `/sessielog`
- `tpl-wiki-artikel.md` — used by `/wiki` and `/sessielog`

### `05-bronnen/`
Source materials: articles, papers, clippings. These are reference documents, not wiki articles.

### `06-claude/`
Claude-internal context files. `CLAUDE.md` can live here or in the vault root. If both exist, the root takes precedence.

### `07-media/`
Descriptions and metadata for media files. Images themselves are not stored here (too large for a markdown vault); their descriptions and tags are.

### `08-archive/`
Articles removed from active wiki. Kept for historical reference.

### `09-memory/`
Ruwe agent-geheugenlaag. Atomaire memories (`YYYY-MM-DD-slug.md`) met
truth-maintenance-frontmatter (`status`, `evidence_basis`, `superseded_by`).
Gevuld door het geheugen-subsysteem (toggle `memory_capture`); niet handmatig
gecureerd. Maand-archief van oude, niet-gepromote memories in `09-memory/archive/`.
Gepromote kennis verhuist via `/wiki` naar `02-wiki/`.

### `.claude/scripts/`
Python utility scripts. Installed by `setup.sh`. Do not move; commands reference these paths directly.

#### Derived files in `.claude/`:
- `kb-index.db` — SQLite index of extracted memories, built by `build-kb-index.py` (SessionStart).
- `memory-sweep-status.json` — Heartbeat file written by `memory-sweep.py` after each run, tracks pending/errors/model-reachability.
- `.sweep.lock` — Single-flight lockfile used by `sweep-launch.py` to prevent concurrent sweep runs.

### `graphify-out/`
Output directory for the graphify skill. `graph.json` is written here when graphify runs over the vault. `auto-crosslink.py` reads it.

The file `.needs-rebuild` is a flag written by `/sessielog` when wiki articles change. You can use it to trigger a graphify rebuild.

### `CLAUDE.md`
Context file read by Claude Code at the start of each session. Customize this file after running `setup.sh`.
