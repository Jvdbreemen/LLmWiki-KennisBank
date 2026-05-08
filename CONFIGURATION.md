# CONFIGURATION

Reference of every configurable knob in LLmWiki-KennisBank. For each entry: name, default, where to change it, what it affects.

All paths use `$HOME`. Defaults reflect what the source files actually contain. Discrepancies with `README.md` are flagged inline.

---

## 1. Path configuration

The four root paths are declared at the top of `setup.sh`. Scripts and commands hardcode these paths separately, so changing `setup.sh` alone is not enough.

### VAULT

- **Default**: `$HOME/KennisBank`
- **Where set**: `setup.sh` line 8
- **Read by**:
  - `scripts/auto-crosslink.py` (line 19, `VAULT_ROOT = Path.home() / "KennisBank"`)
  - `scripts/intake-scan.py` (line 12, `INBOX = Path.home() / "KennisBank" / "00-inbox"`)
  - `scripts/semantic-tiling.py` (lines 20-21, `WIKI_DIR` and `CACHE_FILE`)
  - `scripts/stale-check.py` (lines 14-15, `WIKI_DIR` and `SESSIES_DIR`)
  - `commands/intake.md` (every path reference)
  - `commands/sessielog.md` (every path reference)
  - `commands/stale.md`
  - `commands/wiki.md`
  - `skills/autoresearch/SKILL.md` (lazy hierarchy reads `$HOME/KennisBank/02-wiki/`)
  - `CLAUDE.md.template` (lazy hierarchy and graphify sections)
- **Effect**: root of the knowledge vault. Everything below this path.
- **To change**: edit `setup.sh` line 8 AND every reference listed above. There is no central env var; each file hardcodes the path.

### RESEARCH

- **Default**: `$HOME/Claude/research`
- **Where set**: `setup.sh` line 9
- **Read by**:
  - `skills/autoresearch/SKILL.md` (output directory, `mkdir -p ~/Claude/research`)
  - `commands/sessielog.md` (Step 2 scans for new research files)
  - `CLAUDE.md.template` (lazy hierarchy Layer 3)
- **Effect**: where `/autoresearch` writes output documents.
- **To change**: edit `setup.sh` line 9, `skills/autoresearch/SKILL.md` (Output section, two references), `commands/sessielog.md` (Step 2), and `CLAUDE.md.template`.

### CLAUDE_COMMANDS

- **Default**: `$HOME/.claude/commands`
- **Where set**: `setup.sh` line 10
- **Read by**: `setup.sh` only (copy destination). Claude Code itself reads from `$HOME/.claude/commands/` to expose slash commands. This path is not user-configurable in Claude Code.
- **Effect**: where slash command definitions are installed.
- **To change**: only meaningful if Claude Code's command directory ever moves. Not a real knob.

### CLAUDE_SKILLS

- **Default**: `$HOME/.claude/skills`
- **Where set**: `setup.sh` line 11
- **Read by**: `setup.sh` only (copy destination). Claude Code reads from `$HOME/.claude/skills/` to expose skills.
- **Effect**: where the autoresearch skill is installed.
- **To change**: same caveat as `CLAUDE_COMMANDS`. Not a real knob.

---

## 2. CLAUDE.md vault context variables

`$HOME/KennisBank/CLAUDE.md` is generated from `CLAUDE.md.template` and read by the model at session start. Variables are textual conventions, not parsed config. The model reads them and acts accordingly.

### LEARNINGS_FILE

- **Default**: not set. Template suggests `$HOME/Claude/learnings.md` as an example.
- **Where set**: `$HOME/KennisBank/CLAUDE.md`, "Key learnings file" section.
- **Read by**: `commands/sessielog.md` Step 5 (the model checks the file for this variable and uses it if present).
- **Effect**: when set, `/sessielog` appends Do-Not-Repeat entries and technical patterns to that file.
- **To change**: edit the line `LEARNINGS_FILE=...` in your local `CLAUDE.md`. If unset, Step 5 of `/sessielog` is skipped.

### `[YOUR NAME]` placeholder

- **Default**: literal `[YOUR NAME]` (must be replaced after setup).
- **Where set**: `CLAUDE.md.template` line 4, copied to `$HOME/KennisBank/CLAUDE.md`.
- **Read by**: model at session start.
- **Effect**: identifies the vault owner in session context.

### `[YOUR PROJECTS]` placeholder

- **Default**: literal `[YOUR PROJECTS ...]`.
- **Where set**: `CLAUDE.md.template` line 24.
- **Read by**: model at session start.
- **Effect**: lists active projects so the model can route session logs to the right context.

---

## 3. Stale-check threshold

### THRESHOLD_DAYS / `--days`

- **Default**: `60`
- **Where set**: `scripts/stale-check.py` line 75 (`parser.add_argument("--days", type=int, default=60, ...)`).
- **CLI override**: `python3 stale-check.py --days N`
- **Read by**: `commands/stale.md` (which calls the script without `--days`, so always uses default).
- **Effect**: any wiki article whose `updated:` (or `date:`) frontmatter is older than this many days is reported as stale.
- **To change**: edit the `default=60` argument in `stale-check.py`, or pass `--days` on the command line, or edit `commands/stale.md` to pass `--days` explicitly.
- **Discrepancy with README**: `README.md` and the user task description refer to a constant named `THRESHOLD_DAYS` in `stale-check.py`. No such constant exists. The default lives only as the `default=60` argparse parameter. The CLI flag `--days` does work as documented.

---

## 4. Semantic tiling (`scripts/semantic-tiling.py`)

### OLLAMA_MODEL

- **Default**: `nomic-embed-text`
- **Where set**: `scripts/semantic-tiling.py` line 22.
- **Read by**: `scripts/semantic-tiling.py` only.
- **Effect**: the Ollama model used to compute embeddings via `ollama embed --model <OLLAMA_MODEL>`.
- **To change**: edit the constant. Any model that returns an `embedding` (or `embeddings[0]`) JSON field works. Run `ollama pull <model>` first.

### THRESHOLD_ERROR (duplicate threshold)

- **Default**: `0.90`
- **Where set**: `scripts/semantic-tiling.py` line 24.
- **Effect**: cosine similarity at or above this is reported as `ERROR -- mogelijke duplicaten`.

### THRESHOLD_REVIEW (related threshold)

- **Default**: `0.80`
- **Where set**: `scripts/semantic-tiling.py` line 25.
- **Effect**: cosine similarity in `[0.80, 0.90)` is reported as `REVIEW -- verwante artikelen`.

### Embedding character cap

- **Default**: `4000` characters.
- **Where set**: `scripts/semantic-tiling.py` line 36 (`return content[:4000]`).
- **Effect**: input text is truncated before embedding. Larger articles compare on their first 4000 characters only.

### CACHE_FILE

- **Default**: `$HOME/KennisBank/.claude/embeddings-cache.json`
- **Where set**: `scripts/semantic-tiling.py` line 21.
- **Effect**: stores embeddings keyed by file path and content hash. Stale entries (files no longer in `02-wiki/`) are pruned on every run.

### WIKI_DIR

- **Default**: `$HOME/KennisBank/02-wiki`
- **Where set**: `scripts/semantic-tiling.py` line 20.
- **Effect**: the directory scanned recursively (`**/*.md`) for comparison candidates. `index.md` is excluded.

---

## 5. autoresearch skill

### Output path

- **Default**: `$HOME/Claude/research/YYYY-MM-DD-[slug].md`
- **Where set**: `skills/autoresearch/SKILL.md`, "Output aanmaken" section (two references: the `mkdir` line and the "Outputpad" line). Also referenced in the "Rapport aan gebruiker" section.
- **To change**: edit `skills/autoresearch/SKILL.md` in all three places, plus `setup.sh` `RESEARCH`, plus `commands/sessielog.md` Step 2, plus `CLAUDE.md.template` Layer 3.

### Round count

- **Default**: maximum `3` rounds.
- **Where set**: `skills/autoresearch/SKILL.md`, "Research-loop" section (`Maximaal 3 rounds`) and "Constraints" section.
- **Effect**: Round 1 is broad, Round 2 is gap-filling, Round 3 is optional synthesis. The model stops earlier if confidence is high.
- **To change**: edit both the loop description and the constraint line in `SKILL.md`.

### Source cap

- **Default**: maximum `15` sources.
- **Where set**: `skills/autoresearch/SKILL.md`, "Constraints" section.
- **Effect**: model halts web fetching at this count.

### Confidence labels

- **Default**: `hoog | matig | laag` (Dutch).
- **Where set**: `skills/autoresearch/SKILL.md`, frontmatter section.
- **To change**: edit the frontmatter template and the explanatory paragraph that follows.

### Trigger phrases

- **Default**: `/autoresearch [topic]`, `"research [topic]"`, `"deep dive [topic]"`, `"onderzoek [topic]"`.
- **Where set**: `skills/autoresearch/SKILL.md` frontmatter `description` field.
- **Effect**: Claude Code matches user input against these to decide when to load the skill.

---

## 6. Slash command language

### Command prose language

- **Default**: Dutch (all four commands and the autoresearch skill are written in Dutch).
- **Where set**:
  - `commands/intake.md`
  - `commands/sessielog.md`
  - `commands/stale.md`
  - `commands/wiki.md`
  - `skills/autoresearch/SKILL.md`
- **Effect**: section headings, instructions to the model, and report templates are Dutch. The CLAUDE.md template comments that "commands follow prompt language" -- meaning the model adapts user-facing output, but the instruction text itself stays Dutch unless edited.
- **To change**: rewrite the four `commands/*.md` files and `skills/autoresearch/SKILL.md` in the target language. Filenames (`raw-sessie-...`) and slug conventions referenced in code do not need translating.

### Session log filename pattern

- **Default**: `raw-sessie-YYYY-MM-DD-[onderwerp-slug].md`
- **Where set**: `commands/sessielog.md` Step 1.
- **Read by**: `scripts/stale-check.py` line 16 (`SESSIE_DATE_RE = re.compile(r"raw-sessie-(\d{4}-\d{2}-\d{2})")`).
- **Effect**: stale-check parses dates from this prefix to find session logs newer than a wiki article. If you change the prefix in `sessielog.md`, also update `SESSIE_DATE_RE`.

---

## 7. Memory path detection

### Pattern

- **Default**: `$HOME/.claude/projects/*/memory/MEMORY.md` (first match wins).
- **Where set**:
  - `CLAUDE.md.template` lines 33-34 and 44-47 (Layer 1 lazy hierarchy)
  - `skills/autoresearch/SKILL.md` Step 0, Layer 1
  - `README.md` "Memory path" section
- **Read by**: model at session start, and at the start of `/autoresearch`.
- **Effect**: locates Claude Code's per-project memory file. The path segment between `projects/` and `/memory/` is a slug of the working directory at the time the memory was first written.
- **Why session-dependent**: Claude Code creates one `MEMORY.md` per project working directory. If a session has never run from this project's directory, no memory file exists and the lazy check returns nothing. The glob picks the first match alphabetically, so multiple project memories produce nondeterministic selection.
- **To change**: not configurable in this repo. Replace the bash one-liner in `CLAUDE.md.template` and `SKILL.md` if you maintain memory differently.

---

## 8. graphify integration

### Graph input path

- **Default**: `$HOME/KennisBank/graphify-out/graph.json`
- **Where set**: `scripts/auto-crosslink.py` line 20 (`GRAPH_PATH = VAULT_ROOT / "graphify-out" / "graph.json"`).
- **Read by**: `scripts/auto-crosslink.py` only.
- **Effect**: source of edges for backlink suggestions. If the file is absent, `auto-crosslink.py` exits 0 silently with `graph.json niet gevonden ... crosslink overgeslagen`.
- **To change**: edit the constant in `auto-crosslink.py`. Also adjust where the graphify skill writes output if you point it elsewhere.

### Rebuild flag path

- **Default**: `$HOME/KennisBank/graphify-out/.needs-rebuild`
- **Where set**: `commands/sessielog.md` Step 3.
- **Read by**: external graphify skill (when run, it should consume and clear this flag).
- **Effect**: signals that wiki content changed and the graph is out of date. The flag is written as plain text containing changed file paths.
- **To change**: edit Step 3 of `commands/sessielog.md`.

### MIN_CONFIDENCE

- **Default**: `0.75`
- **Where set**: `scripts/auto-crosslink.py` line 22.
- **Effect**: graph edges below this `confidence_score` are ignored when proposing backlinks.
- **To change**: edit the constant.

### MAX_NEW_LINKS

- **Default**: `5`
- **Where set**: `scripts/auto-crosslink.py` line 23.
- **Effect**: per article, at most this many new `Zie ook` bullets are appended in one run.

### WIKI_DIR_PREFIX

- **Default**: `02-wiki/`
- **Where set**: `scripts/auto-crosslink.py` line 21.
- **Effect**: only nodes whose `source_file` starts with this prefix are considered crosslink targets. Change if you rename the wiki directory.

---

## 9. Customizing for non-default vault paths

If you change `VAULT` from `$HOME/KennisBank` to something else, edit every file below. There is no single source of truth.

### Files that hardcode the vault root

| File | What to edit |
|------|-----|
| `setup.sh` | line 8: `VAULT="..."` |
| `scripts/auto-crosslink.py` | line 19: `VAULT_ROOT = Path.home() / "KennisBank"` |
| `scripts/intake-scan.py` | line 12: `INBOX = Path.home() / "KennisBank" / "00-inbox"` |
| `scripts/semantic-tiling.py` | lines 20, 21: `WIKI_DIR` and `CACHE_FILE` |
| `scripts/stale-check.py` | lines 14, 15: `WIKI_DIR`, `SESSIES_DIR` |
| `commands/intake.md` | every `~/KennisBank/...` reference |
| `commands/sessielog.md` | every `~/KennisBank/...` reference (template path, scripts path, graphify-out path) |
| `commands/stale.md` | the `python3 ~/KennisBank/.claude/scripts/stale-check.py` line |
| `commands/wiki.md` | every `~/KennisBank/...` reference |
| `skills/autoresearch/SKILL.md` | Step 0 lazy hierarchy bash blocks (Layer 2) |
| `CLAUDE.md.template` | Layer 2 bash blocks; graphify section |
| `README.md` | documentation references |

### Files that hardcode the research path

| File | What to edit |
|------|-----|
| `setup.sh` | line 9: `RESEARCH="..."` |
| `skills/autoresearch/SKILL.md` | "Output aanmaken" `mkdir -p ...`, "Outputpad" line, "Rapport aan gebruiker" path |
| `commands/sessielog.md` | Step 2 `find ~/Claude/research/...` |
| `CLAUDE.md.template` | Layer 3 `ls ~/Claude/research/...` |

### Recommended approach

There is no env-var indirection in the codebase. Two options:

1. Manually edit all files listed above. Use a global find-replace for `~/KennisBank` and `KennisBank /` constructs (and `~/Claude/research` separately).
2. Symlink: leave defaults in place and create `ln -s /your/real/path $HOME/KennisBank`. This is simpler and keeps upgrades clean.

---

## 10. Multiple vaults / per-project context

### What works

- One vault per user account works. All scripts and commands target `$HOME/KennisBank` exclusively.
- Per-project subdivision inside the vault works via `03-projecten/` subdirectories. Wiki articles can tag a project in frontmatter; `commands/wiki.md` accepts an `$ARGUMENTS` topic filter, but it filters by content match, not by project boundary.

### What does not work

- **Multiple parallel vaults are not supported.** All scripts hardcode `Path.home() / "KennisBank"`. Switching active vaults requires either editing the source of every script (see section 9) or moving symlinks.
- **Per-project vault overrides** are not implemented. There is no `KENNISBANK_VAULT` env var, no CLI flag for vault path, no auto-detection from project context.
- **Concurrent vaults** would collide on the embeddings cache (`$HOME/KennisBank/.claude/embeddings-cache.json`) and on `MEMORY.md` glob ambiguity (section 7).

### Workarounds for multi-vault use

| Approach | Trade-off |
|----------|-----------|
| Symlink `$HOME/KennisBank` to the active vault, swap before each session | Manual, error-prone. No active-vault indicator. |
| Maintain separate clones of this repo with `setup.sh` pointing to different `VAULT` values, and run `setup.sh` per project | Heavy. Each setup overwrites `$HOME/.claude/commands/` for all projects. |
| Single vault, internal sectioning via `03-projecten/<project-name>/` and frontmatter tags | Recommended. The system was designed for this. |

---

## Discrepancies found

1. **`THRESHOLD_DAYS` constant does not exist.** `README.md` (line 126) and the original task description reference editing `THRESHOLD_DAYS` in `stale-check.py`. The actual code uses `argparse` with `default=60`. The `--days N` CLI flag is correct.
2. **`README.md` stale description is partial.** It says `/stale` "detects articles older than 60 days with newer session data." The script also reports stale articles WITHOUT newer session logs (in a separate `stale_without_sessies` group). Both groups are output.
3. **`auto-crosslink.py` knobs are undocumented in README.** `MIN_CONFIDENCE = 0.75` and `MAX_NEW_LINKS = 5` are real knobs not mentioned anywhere in `README.md` or `CLAUDE.md.template`.
4. **`LEARNINGS_FILE` is text-only convention, not parsed config.** The variable is read by the model from `CLAUDE.md`, not by any script. This works because the model is the executor of `commands/sessielog.md` Step 5; mentioning it as a "configuration variable" can mislead readers into expecting code parsing.
5. **`embeddings-cache.json` location not in README.** The cache lives at `$HOME/KennisBank/.claude/embeddings-cache.json` but is undocumented outside the script source.
6. **graphify rebuild flag is written by a command, not by `setup.sh`.** `setup.sh` creates `graphify-out/` but the `.needs-rebuild` flag is written by `commands/sessielog.md` Step 3. README implies graphify is fully external; the rebuild signal is actually produced inside this repo.
