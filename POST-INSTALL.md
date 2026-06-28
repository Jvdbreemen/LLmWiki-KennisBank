# Post-install walkthrough

This is your first session after `bash setup.sh`. Follow it top to bottom and you will end up with a working LLM wiki layer over Claude Code: a customised vault, a session log, a compiled wiki article, and a processed inbox file. Each step is self-contained and tells you what to expect on screen and on disk.

If you are an AI agent following this for a human user, do not skip the verification step. The doctor script is the source of truth for whether the install is healthy.

---

## What just happened

`setup.sh` created `$HOME/KennisBank/` with the full vault layout (`00-inbox`, `01-raw/sessies`, `02-wiki`, `03-projecten`, `04-templates`, `05-bronnen`, `06-claude`, `07-media`, `08-archive`, plus `.claude/scripts` and `graphify-out`). It copied the Python utility scripts into `$HOME/KennisBank/.claude/scripts/`, dropped the session-log and wiki-article templates into `$HOME/KennisBank/04-templates/`, and wrote a starter `CLAUDE.md` into the vault root from `CLAUDE.md.template`. If you accepted the prompt during setup, it also installed the slash commands (`/sessielog`, `/wiki`, `/intake`, `/stale`, `/sessiestart`, `/import`, `/destilleer`, plus the namespaced `/kennisbank:settings` under `$HOME/.claude/commands/kennisbank/`) into `$HOME/.claude/commands/` and the `/autoresearch` skill into `$HOME/.claude/skills/autoresearch/`. It also created the research output directory at `$HOME/Claude/research/`.

`setup.sh` schreef ook `kennisbank-settings.json` met de default-toggles
(`auto_archive` uit, de rest aan). Pas ze aan met `/kennisbank:settings`.

Nothing is wired into a running Claude Code session yet. The next steps do that.

---

## Step 1: Customize CLAUDE.md

The vault `CLAUDE.md` is the file Claude Code reads when you open a session inside `$HOME/KennisBank/`. It still has placeholder text.

```bash
$EDITOR $HOME/KennisBank/CLAUDE.md
```

Do this:

1. Replace `[YOUR NAME]` on the "Vault owner" line with your name.
2. Replace `[YOUR PROJECTS]` (under "Active projects") with one line per active project. Format: `- **Name**: short description`. Three to six projects is plenty.
3. Save and close.

Optional: enable a central learnings file. Near the bottom of `CLAUDE.md` there is a
commented line:

```
# LEARNINGS_FILE=~/Claude/learnings.md
```

Remove the leading `# ` (and edit the path if you like) to enable it. `/sessielog`
reads the first uncommented `LEARNINGS_FILE=` line, creates the file if it does not
exist, and appends Do-Not-Repeat entries and reusable patterns per session. Leave the
line commented to skip the learnings step. This complements the automatic `09-memory/`
layer with a human-curated record.

---

## Step 2: Wire up the autoresearch trigger (optional)

The six core commands work as soon as they are in `$HOME/.claude/commands/`. The `/autoresearch` skill needs one extra hint in your global Claude config so the skill is triggered correctly when you type `/autoresearch [topic]`.

Append this block to `$HOME/.claude/CLAUDE.md` (create the file if it does not exist):

```markdown
# autoresearch
- **autoresearch** (`~/.claude/skills/autoresearch/SKILL.md`) - multi-round research with lazy hierarchy check. Output to `~/Claude/research/`. Trigger: `/autoresearch`
When the user types `/autoresearch`, invoke the Skill tool with `skill: "autoresearch"` before doing anything else.
```

If you would rather have an agent do this safely (back up first, idempotent insert, no duplicate blocks), see `AGENTS.md` in this repo for the agent-safe edit recipe.

You can skip this step entirely if you do not plan to use `/autoresearch`.

---

## Step 3: Verify the install

Run the doctor script from inside the cloned repo. It checks every directory, every script, every template, and every command location.

```bash
bash scripts/doctor.sh
```

Expected output (abbreviated):

```
[ok] vault root: $HOME/KennisBank
[ok] vault layout: 00-inbox 01-raw/sessies 02-wiki 03-projecten 04-templates 05-bronnen 06-claude 07-media 08-archive
[ok] scripts: auto-crosslink.py intake-scan.py semantic-tiling.py stale-check.py
[ok] templates: tpl-sessie-log.md tpl-wiki-artikel.md
[ok] CLAUDE.md present
[ok] commands installed: sessielog wiki intake stale sessiestart import
[ok] autoresearch skill installed
[warn] ollama qwen3-embedding:8b not found (semantic tiling will be skipped)
[warn] graphify-out/graph.json not present (auto-crosslink will be skipped)
Done. 0 errors, 2 warnings.
```

Warnings are fine; they correspond to optional features. Errors mean a directory or file is missing and you should rerun `bash setup.sh`.

Manual sanity check, in case you want to see for yourself:

```bash
ls $HOME/KennisBank/
ls $HOME/KennisBank/.claude/scripts/
ls $HOME/.claude/commands/ | grep -E '^(sessielog|wiki|intake|stale|sessiestart|import)\.md$'
ls $HOME/.claude/skills/autoresearch/SKILL.md
```

If all four `ls` listings show files (the third one should list six command files), the install is wired up.

---

## Step 4: Your first session

Now you write the first session log. Open Claude Code in any directory:

```bash
cd $HOME/KennisBank
claude
```

(Working directory does not matter for the commands, but starting inside the vault means Claude will read your `CLAUDE.md` at the top of the session.)

Have a short, real conversation. Anything goes; the goal is to produce something worth logging. Examples:

- Ask Claude to outline a small refactor in a project you have nearby.
- Ask Claude to summarize an article you paste in.
- Ask Claude to plan a 30-minute task you actually want to do today.

Then run:

```
/sessielog
```

Claude will write a session log to `$HOME/KennisBank/01-raw/sessies/raw-sessie-YYYY-MM-DD-[slug].md`, where `[slug]` is a kebab-case version of your dominant topic. Verify:

```bash
ls -lt $HOME/KennisBank/01-raw/sessies/ | head
cat $HOME/KennisBank/01-raw/sessies/raw-sessie-*-*.md | head -40
```

You should see YAML frontmatter (`title`, `type: raw`, `created`, `updated`), a Doel section, a Samenvatting section, an Output section with absolute paths, a Nieuwe kennis section, Vervolgacties checkboxes, and an AI-verantwoording section.

The same command also runs steps 2 to 5 of `commands/sessielog.md`: it scans `$HOME/Claude/research/` for files modified in the last day, identifies wiki candidates, runs `auto-crosslink.py` and `semantic-tiling.py` if available, and (if you configured it) appends to `LEARNINGS_FILE`. The on-screen confirmation lists which articles were new, updated, or skipped.

---

## Step 5: Compile your first wiki article

The session log is raw input. The wiki is the compiled, searchable layer. Run:

```
/wiki
```

This scans logs from the last 7 days, picks out reusable knowledge (lines marked `wiki-kandidaat: ...`, recurring topics, technical patterns), and writes one article per concept to `$HOME/KennisBank/02-wiki/`.

After the command finishes:

```bash
ls $HOME/KennisBank/02-wiki/
cat $HOME/KennisBank/02-wiki/*.md | head -60
```

Each article has YAML frontmatter (`type: wiki`, `tags`, `status`, `created`, `updated`), a Definition section, a Context section, Kernpunten in prose, Verbanden with `[[backlinks]]`, Bronnen in APA7, and a Sessie-herkomst section linking back to the source raw log under `01-raw/sessies/`.

If your first session was not knowledge-rich enough, `/wiki` may report "no candidates". That is correct behaviour. Have one more session, then try again.

---

## Step 6: Try the inbox

The inbox is a drop zone. Anything you put there gets routed to the right place by `/intake`.

Drop a markdown file:

```bash
cat > $HOME/KennisBank/00-inbox/test-note.md <<'EOF'
A short note about why I am testing the inbox.
EOF
```

Or a URL file (plain text file containing a single URL):

```bash
echo "https://en.wikipedia.org/wiki/Andrej_Karpathy" > $HOME/KennisBank/00-inbox/karpathy.url
```

Then run:

```
/intake
```

Expected behaviour:

- The markdown file gets YAML frontmatter added and is moved to `$HOME/KennisBank/01-raw/`.
- The URL file is fetched, converted to markdown, and saved as `$HOME/KennisBank/01-raw/raw-YYYY-MM-DD-[slug].md`.
- The original files are removed from `00-inbox/` once processed.
- Claude reports per file: path, action, result.

Verify:

```bash
ls $HOME/KennisBank/00-inbox/
ls -lt $HOME/KennisBank/01-raw/ | head
```

The inbox should be empty and the new files should be in `01-raw/`.

---

## Step 7: Optional: graphify

If you have a graphify skill installed in `$HOME/.claude/skills/graphify/` (one reference implementation lives at https://github.com/Jvdbreemen/graphify, any compatible knowledge-graph tool works), you can build a knowledge graph over the vault. Run `/graphify` in a session inside `$HOME/KennisBank/`. The output lands in `$HOME/KennisBank/graphify-out/graph.json`, and the next time `/sessielog` runs it will use that file to add `[[backlinks]]` to your wiki articles via `auto-crosslink.py`. Without graphify, that step is silently skipped; everything else still works.

---

## Step 8: Optional: knowledge graph dashboard

[Understand-Anything](https://github.com/Lum1104/Understand-Anything) generates an interactive HTML dashboard from a Karpathy-pattern wiki. Install once, build the index, run the skill:

```bash
# Install the plugin (user scope)
claude plugin marketplace add Lum1104/Understand-Anything
claude plugin install understand-anything

# Build the index.md + log.md that parse-knowledge-base.py expects
python3 scripts/build-karpathy-index.py
```

The build script scans `$HOME/KennisBank/02-wiki/` frontmatter and `$HOME/KennisBank/01-raw/sessies/` filenames, then writes:

- `02-wiki/index.md` - wiki articles grouped into 5–12 categories via `## Section` + `[[wikilink]]` lines
- `02-wiki/log.md` - chronological session log in `## [YYYY-MM-DD] OPERATION | Title` format

Re-run after major `/wiki` rounds. Without `--force` the script refuses to overwrite an existing index/log; pass `--force` to rebuild (a `.bak` is kept). Use `--dry-run` to preview.

Then, in a Claude Code session pointed at `$HOME/KennisBank/02-wiki/`, run:

```
/understand-knowledge
```

After analysis (about 5 minutes for 100+ articles, dispatches up to 3 article-analyzer subagents concurrently), the skill auto-launches `/understand-dashboard`. You will see a graph URL with a `?token=` parameter - open it to browse nodes (articles, topics, entities, claims) and edges (related, categorized_under, builds_on, cites, contradicts, ...).

This is read-only: no vault content is modified beyond the index/log helper files.

---

## Step 9: Optional: autoresearch

If you completed Step 2, you can do multi-round research on any topic and have it land where the rest of your knowledge lives.

```
/autoresearch Sveltia CMS vs Decap CMS
```

The skill runs up to three rounds of web search and fetch (max 15 sources), writes one structured document to `$HOME/Claude/research/YYYY-MM-DD-[slug].md`, and reports the outcome with confidence level (hoog, matig, laag). The next `/sessielog` you run picks up that file as a wiki candidate automatically.

---

## Step 10: Optional: backfill old sessions

If you have Claude history from before you installed this layer, `/import` can pull it into `$HOME/KennisBank/01-raw/sessies/` so `/wiki` can compile it. Four sources are supported:

1. `cc`: Claude Code session history under `$HOME/.claude/projects/*.jsonl`. Lowest-risk, already on disk; start here.
2. `claudeai <path>`: a claude.ai export bundle (`conversations.json` or the surrounding `.zip`).
3. `folder <path> [prefix]`: any folder with markdown or text files; recursive.
4. `cowork`: auto-detected Mac desktop Claude (Cowork) data.

Try `/import cc` first. The command runs a dry-run, shows you what would be imported, asks for confirmation, then runs for real:

```
/import cc
```

Expected output (abbreviated):

```
Dry-run: 42 sessions found, 42 new, 0 skipped, 0 errors.
Doorgaan met import? y
Done. imported: 42, skipped: 0, errors: 0.
Pad: $HOME/KennisBank/01-raw/sessies/
Tip: run /wiki om kennis uit deze imports te compileren.
```

After the import finishes, run `/wiki` so the new raw logs become wiki articles.

If something goes wrong (no sessions found, errors on individual files, claude.ai zip not parsing), see `TROUBLESHOOTING.md`.

---

## Maintenance rhythm

Three cadences keep the system healthy:

1. **Daily**: run `/sessielog` at the end of every Claude session that produced something worth keeping. If a session was small talk only, skip it.
2. **Weekly**: run `/wiki` once a week. It compiles the last 7 days of raw logs into wiki articles, updates existing ones, and reports what it skipped and why.
3. **Monthly**: run `/stale`. It uses `stale-check.py` to find articles older than 60 days that have newer session logs touching the same topic (priority: update) or no recent input at all (consider archiving or marking `status: stabiel`). The threshold is configurable in `stale-check.py` or via `--days N`.

Three commands, three cadences. That is the whole rhythm.

---

## What to read next

- `TROUBLESHOOTING.md`: doctor failures, missing memory paths, Ollama not found, command not triggering, intake misclassification, autoresearch returning empty.
- `CONFIGURATION.md`: change the vault path, change the research output path, change the stale threshold, switch language defaults, set `LEARNINGS_FILE`, integrate graphify.
- `AGENTS.md`: how to let an AI agent edit `$HOME/.claude/CLAUDE.md` safely (idempotent insert, backup, no duplicate blocks), and what an agent should and should not touch in `$HOME/KennisBank/`.

You are done. Run `/sessielog` after this session and you will have logged your install itself.
