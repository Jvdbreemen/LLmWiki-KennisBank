# Troubleshooting

Practical fixes for problems during or after installing LLmWiki-KennisBank. Each entry follows the same shape: Symptom, Cause, Fix. "Repo root" means the directory you cloned with `git clone`.

---

## 1. Install problems

### 1.1 Permission denied on setup.sh or scripts

**Symptom**: `bash: ./setup.sh: Permission denied`, or later `Permission denied` on `$HOME/KennisBank/.claude/scripts/*.py`.

**Cause**: Files lack the executable bit. Common after zip download or sync that strips Unix permissions.

**Fix**:
```bash
chmod +x setup.sh "$HOME/KennisBank/.claude/scripts/"*.py
```
Or invoke the interpreter directly: `bash setup.sh`, `python3 <script>`.

### 1.2 setup.sh fails with "No such file or directory"

**Symptom**: `cp: scripts/*.py: No such file or directory`.

**Cause**: `setup.sh` uses relative paths and must be run from the repo root.

**Fix**:
```bash
cd "$HOME/path/to/LLmWiki-KennisBank"
bash setup.sh
```

### 1.3 Re-running setup.sh overwrites edits

**Symptom**: Customized templates or scripts disappear after a second `bash setup.sh`.

**Cause**: `setup.sh` uses unconditional `cp` for templates, scripts, and commands. Only `CLAUDE.md` is guarded by an existence check.

**Fix**: Back up first, then re-run:
```bash
cp -r "$HOME/KennisBank/04-templates" "$HOME/KennisBank-backup-templates"
cp -r "$HOME/KennisBank/.claude/scripts" "$HOME/KennisBank-backup-scripts"
bash setup.sh
```
Restore individual edits afterwards. If you do not need to re-run setup, do not.

### 1.4 mkdir cannot create vault directory

**Symptom**: `mkdir: cannot create directory '$HOME/KennisBank': Permission denied`.

**Cause**: `$HOME` is read-only, or `$HOME/KennisBank` is a broken symlink to a path you do not own.

**Fix**:
```bash
ls -ld "$HOME/KennisBank" 2>/dev/null
rm "$HOME/KennisBank"   # only if it is a broken symlink
bash setup.sh
```

### 1.5 setup.sh: command not found

**Symptom**: `zsh: command not found: setup.sh`.

**Cause**: User typed `setup.sh` instead of `bash setup.sh`. The file is not on PATH and has no shebang invocation.

**Fix**: `bash setup.sh`. Do not use `sh setup.sh`; the script is bash-specific.

---

## 2. Command not found

### 2.1 Slash command does not appear in Claude Code

**Symptom**: Typing `/sessielog`, `/wiki`, `/intake`, or `/stale` does nothing or is treated as text.

**Cause**: Command markdown files were not copied to `$HOME/.claude/commands/`. This happens when answering `n` to the setup prompt.

**Fix**:
```bash
mkdir -p "$HOME/.claude/commands"
cp commands/*.md "$HOME/.claude/commands/"
```
Restart Claude Code so it re-scans the commands directory.

### 2.2 Command runs but produces no output

**Symptom**: `/wiki` runs, nothing changes in `$HOME/KennisBank/02-wiki/`.

**Cause**: No session logs in the last 7 days, or the vault subdirectories do not exist.

**Fix**:
```bash
ls "$HOME/KennisBank/01-raw/sessies/"
```
If empty, run a session and end with `/sessielog`. To compile from older logs, pass an explicit topic: `/wiki my-topic`.

### 2.3 Project commands shadow user commands

**Symptom**: A slash command works in some Claude Code sessions but not in others.

**Cause**: A project-level `<project>/.claude/commands/` directory exists and shadows `$HOME/.claude/commands/`.

**Fix**:
```bash
ls -la .claude/commands/ 2>/dev/null
cp "$HOME/.claude/commands/sessielog.md" .claude/commands/
```
Or remove the project-level directory if you never intended it.

---

## 3. Python script errors

### 3.1 semantic-tiling.py: embedding failed

**Symptom**: `Embedding mislukt via /api/embeddings. Controleer OLLAMA_HOST, ollama serve en OLLAMA_EMBED_MODEL.`

**Cause**: The script calls the Ollama HTTP API at `${OLLAMA_HOST:-http://localhost:11434}/api/embeddings` and requests the model `${OLLAMA_EMBED_MODEL:-qwen3-embedding:8b}` (the multilingual default; set `OLLAMA_EMBED_MODEL=nomic-embed-text` for the lighter English-only fallback). Either Ollama is not installed, the daemon is not running, `OLLAMA_HOST` points at the wrong server, or the configured model is not pulled. See section 8.

**Fix**:
```bash
ollama serve &
export OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
export OLLAMA_EMBED_MODEL="${OLLAMA_EMBED_MODEL:-qwen3-embedding:8b}"
curl -s "$OLLAMA_HOST/api/tags" >/dev/null && echo "ollama up" || echo "ollama down"
ollama pull "$OLLAMA_EMBED_MODEL"
ollama list | grep "$OLLAMA_EMBED_MODEL"
```

### 3.2 auto-crosslink.py: graph.json not found

**Symptom**: `graph.json niet gevonden ($HOME/KennisBank/graphify-out/graph.json) -- crosslink overgeslagen`.

**Cause**: The script depends on graphify output. Without `graph.json` it exits 0 and skips. Not an error.

**Fix**: Ignore if you do not use graphify. To enable, install the graphify skill, run `/graphify` against the vault, then re-run the script.

### 3.3 stale-check.py: wiki directory not found

**Symptom**: `Wiki-directory niet gevonden: $HOME/KennisBank/02-wiki`.

**Cause**: Setup never ran, or the vault was moved.

**Fix**:
```bash
mkdir -p "$HOME/KennisBank/02-wiki"
```
For a non-default vault path, edit `WIKI_DIR` and `SESSIES_DIR` at the top of `stale-check.py`.

### 3.4 SyntaxError on union type hints

**Symptom**: `SyntaxError: invalid syntax` on `list[float] | None`.

**Cause**: Script ran under Python older than 3.10. The scripts use 3.10+ syntax.

**Fix**:
```bash
python3 --version
brew install python@3.12
python3.12 "$HOME/KennisBank/.claude/scripts/stale-check.py"
```

### 3.5 intake-scan.py: 00-inbox not found

**Symptom**: JSON output contains `"error": "00-inbox niet gevonden"`.

**Cause**: The inbox directory was deleted or never created.

**Fix**:
```bash
mkdir -p "$HOME/KennisBank/00-inbox"
```

---

## 4. autoresearch skill not triggering

### 4.1 /autoresearch is treated as plain text

**Symptom**: Typing `/autoresearch foo` produces a normal Claude reply instead of invoking the skill.

**Cause**: The trigger snippet is missing from `$HOME/.claude/CLAUDE.md`.

**Fix**: Append this to `$HOME/.claude/CLAUDE.md`:
```
# autoresearch
- **autoresearch** (`~/.claude/skills/autoresearch/SKILL.md`) - multi-round research with lazy hierarchy check. Output to `~/Claude/research/`. Trigger: `/autoresearch`
When the user types `/autoresearch`, invoke the Skill tool with `skill: "autoresearch"` before doing anything else.
```
Verify: `grep -n autoresearch "$HOME/.claude/CLAUDE.md"`.

### 4.2 Skill directory missing

**Symptom**: Trigger snippet is in place but Claude reports the skill is unavailable.

**Cause**: `SKILL.md` was not copied because of `n` to the setup prompt.

**Fix**:
```bash
mkdir -p "$HOME/.claude/skills/autoresearch"
cp skills/autoresearch/SKILL.md "$HOME/.claude/skills/autoresearch/"
```

### 4.3 Skill cannot write its report

**Symptom**: Skill completes research but errors at the final write with `No such file or directory`.

**Cause**: `$HOME/Claude/research/` does not exist.

**Fix**:
```bash
mkdir -p "$HOME/Claude/research"
```
If you customized the path in `SKILL.md`, create that path instead.

### 4.4 Skill skips memory and wiki check

**Symptom**: `/autoresearch` jumps straight to web searches without consulting existing knowledge.

**Cause**: `$HOME/KennisBank/CLAUDE.md` is missing or its "Lazy hierarchy reading pattern" section was removed.

**Fix**:
```bash
[ -f "$HOME/KennisBank/CLAUDE.md" ] || cp CLAUDE.md.template "$HOME/KennisBank/CLAUDE.md"
grep -n "Lazy hierarchy" "$HOME/KennisBank/CLAUDE.md"
```

---

## 5. Memory file not found

### 5.1 Glob returns nothing

**Symptom**:
```bash
ls ~/.claude/projects/*/memory/MEMORY.md 2>/dev/null
```
prints nothing.

**Cause**: Memory files are created lazily. Until a session has actually written something for a given working directory, no file exists.

**Fix**: Run a Claude Code session that triggers an auto-memory write. Then:
```bash
ls -la "$HOME/.claude/projects/"
```
A directory with no `memory/MEMORY.md` is normal until something is stored.

### 5.2 Wrong project's memory loads

**Symptom**: `head -1` of the glob returns a memory file from another project.

**Cause**: `head -1` picks alphabetical first, not the slug matching the current directory.

**Fix**: Match the slug to the current directory:
```bash
ls "$HOME/.claude/projects/" | grep "$(basename "$PWD")"
```
The exact slug rule depends on the Claude Code version. Pick the candidate that matches by hand.

### 5.3 Memory file is empty

**Symptom**: `cat MEMORY.md` prints nothing or only a header.

**Cause**: A session created the file but stored no entries. Benign.

**Fix**: No action required. Edit the file by hand if you want to seed it.

---

## 6. Vault path conflicts

### 6.1 $HOME/KennisBank already contains data

**Symptom**: Running `setup.sh` against a host with an existing vault mixes new files with old.

**Cause**: `setup.sh` does not check for existing content beyond `CLAUDE.md`. Existing scripts and templates get overwritten; everything else stays.

**Fix**: Decide before running. To preserve old files but get fresh scripts:
```bash
mv "$HOME/KennisBank" "$HOME/KennisBank.old"
bash setup.sh
rsync -a --ignore-existing "$HOME/KennisBank.old/" "$HOME/KennisBank/"
```

### 6.2 Mid-install abort

**Symptom**: Ctrl-C during setup leaves a half-built vault (some directories, no scripts, or scripts but no templates).

**Cause**: `setup.sh` is sequential and not transactional.

**Fix**: Re-run from the repo root. `mkdir -p` and `cp` are idempotent:
```bash
cd "$HOME/path/to/LLmWiki-KennisBank"
bash setup.sh
```

### 6.3 Vault elsewhere than $HOME/KennisBank

**Symptom**: You want the vault under `$HOME/Documents/` or a synced folder.

**Cause**: The path is hardcoded in `setup.sh` and in every script via `Path.home() / "KennisBank"`.

**Fix**: Use a symlink (simplest):
```bash
mv "$HOME/KennisBank" "$HOME/Documents/KennisBank"
ln -s "$HOME/Documents/KennisBank" "$HOME/KennisBank"
```
Or edit `VAULT` in `setup.sh` and the path constants in each script and command file.

### 6.4 $HOME/Claude/research collides with existing files

**Symptom**: `setup.sh` creates `$HOME/Claude/research/`, but you do not want a new subdirectory under `$HOME/Claude/`.

**Cause**: The autoresearch output path is hardcoded.

**Fix**: Edit `RESEARCH` in `setup.sh` and replace every `~/Claude/research/` in `skills/autoresearch/SKILL.md` with the new path before running setup.

---

## 7. Graphify integration silent failures

### 7.1 graph.json never appears

**Symptom**: `auto-crosslink.py` always prints "graph.json niet gevonden".

**Cause**: The graphify skill has not been run against the vault.

**Fix**:
```bash
ls "$HOME/.claude/skills/graphify/SKILL.md" 2>/dev/null
```
Install the skill if missing. Then in a Claude Code session at `$HOME/KennisBank/`, run `/graphify`. Verify `$HOME/KennisBank/graphify-out/graph.json` exists.

### 7.2 .needs-rebuild flag accumulates

**Symptom**: `$HOME/KennisBank/graphify-out/.needs-rebuild` grows over time and is never cleared.

**Cause**: `/sessielog` writes the flag to signal that fresh content exists. Nothing in this repo runs graphify automatically.

**Fix**: Periodically run `/graphify`, then clear:
```bash
rm "$HOME/KennisBank/graphify-out/.needs-rebuild"
```
If you do not use graphify, ignore the file or remove the write step from `commands/sessielog.md`.

### 7.3 Crosslinks land in a freshly created section

**Symptom**: `auto-crosslink.py` creates a new `## Verbanden` heading even though the article already has one.

**Cause**: The script matches the heading exactly. Variants like `## Verbanden en context` or `### Verbanden` will not match.

**Fix**: Rename existing headings to exactly `## Verbanden`, or merge the duplicate by hand.

### 7.4 Stale source paths in graph

**Symptom**: Crosslinks point to wiki articles that have been renamed or deleted.

**Cause**: `graph.json` is a snapshot; the script trusts it.

**Fix**: Rebuild after any reorganisation:
```bash
rm "$HOME/KennisBank/graphify-out/graph.json"
```
Then re-run `/graphify`.

---

## 8. Ollama issues

### 8.1 ollama: command not found

**Symptom**: `zsh: command not found: ollama`.

**Cause**: Ollama is not installed.

**Fix**:
```bash
brew install ollama
ollama serve &
```
Or download from `https://ollama.com/download`.

### 8.2 Daemon not running

**Symptom**: `Error: could not connect to ollama app, is it running?`

**Cause**: The Ollama daemon process is down.

**Fix**:
```bash
ollama serve &
export OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
curl -s "$OLLAMA_HOST/api/tags" >/dev/null && echo "ollama up" || echo "ollama down"
```
On macOS, `/Applications/Ollama.app` also launches the daemon.

### 8.3 Model not pulled

**Symptom**: `Error: model 'qwen3-embedding:8b' not found`.

**Cause**: Ollama only loads what you pull.

**Fix**:
```bash
ollama pull qwen3-embedding:8b          # multilingual default
# or, English-only fallback: ollama pull nomic-embed-text
ollama list | grep -E 'qwen3-embedding|nomic-embed-text'
```

### 8.4 Wrong model name in script

**Symptom**: You set `OLLAMA_EMBED_MODEL` to a different model and `semantic-tiling.py` fails or returns no embedding.

**Cause**: `semantic-tiling.py` reads `OLLAMA_EMBED_MODEL` and defaults to `qwen3-embedding:8b` (with `nomic-embed-text` as the English-only fallback). The selected model may not be pulled yet, or it may return a different output schema.

**Fix**:
```bash
export OLLAMA_EMBED_MODEL=qwen3-embedding:8b
ollama pull "$OLLAMA_EMBED_MODEL"
ollama list | grep "$OLLAMA_EMBED_MODEL"
```
If the model is present but still fails, confirm it returns `{"embedding": [...]}` or `{"embeddings": [[...]]}` and adapt `get_embedding` only if the schema differs.

### 8.5 Stale embedding cache

**Symptom**: Tiling reports duplicates that no longer match disk content, or fails to deserialize the cache.

**Cause**: `$HOME/KennisBank/.claude/embeddings-cache.json` was edited by hand or written during a crash.

**Fix**:
```bash
rm "$HOME/KennisBank/.claude/embeddings-cache.json"
```
The script rebuilds the cache on next run.

---

## 9. GitHub Copilot CLI integration

Applies only when you installed the standalone GitHub Copilot CLI target
(`bash setup.sh --agents copilot`). If you never selected it, `doctor.sh` prints
`copilot integration: not configured` as INFO and counts zero failures — that is
expected, not a problem. This targets the `@github/copilot` CLI (invoked
`copilot`), not the `gh copilot` extension or VS Code agent mode.

### 9.1 copilot --version prints "no platform package found"

**Symptom**: `copilot --version` errors with *"no platform package found"*;
doctor shows `[WARN] copilot cli: ... platform_binary_missing`.

**Cause**: On Windows (notably under nvm4w), `npm install -g @github/copilot`
places the JS loader but not the optional platform binary.

**Fix**: install the matching platform package at the same version:
```bash
npm install -g @github/copilot-win32-x64      # match your platform/arch
copilot --version
```

### 9.2 doctor: "configured but copilot not installed"

**Symptom**: `[WARN] copilot cli: configured but copilot not installed`.

**Cause**: KennisBank config is present but the `copilot` binary is not on `PATH`.

**Fix**: install it, or point KennisBank at an off-PATH binary:
```bash
npm install -g @github/copilot
# or, if copilot lives somewhere not on PATH:
export KENNISBANK_COPILOT_BIN=/absolute/path/to/copilot
```
This is a WARN, not a FAIL: Copilot is optional and never blocks the install.

### 9.3 kennisbank server not in `copilot mcp list`

**Symptom**: `copilot mcp list` does not show `kennisbank`; doctor shows
`[WARN] copilot cli: ... mcp_not_listed`.

**Cause**: `~/.copilot/mcp-config.json` is missing the `mcpServers.kennisbank`
key, or `COPILOT_HOME` points somewhere other than where you are looking.

**Fix**: re-run setup (idempotent key-scoped merge, backs up first) and validate:
```bash
bash setup.sh --agents copilot
python3 "$HOME/KennisBank/.claude/scripts/_copilot.py" validate --vault "$HOME/KennisBank" --json
```
`copilot mcp list` works without a GitHub login, so a failure here is config, not
auth.

### 9.4 Config passes but a model turn fails with a login error

**Symptom**: `copilot mcp list` and doctor pass, but an actual Copilot prompt
fails asking you to log in.

**Cause**: Copilot is cloud-backed. MCP, skill, and instruction installation is
login-free, but a live model turn needs a GitHub Copilot subscription.

**Fix**: run `copilot` and complete `/login`. KennisBank never forces or stores a
login; auth tokens (`COPILOT_GITHUB_TOKEN` / `GH_TOKEN` / `GITHUB_TOKEN`) are
yours and are never written to the repo or vault.

### 9.5 Copilot activity is not showing up in recall

**Symptom**: `/watdeedik` or `/timeline` do not surface a Copilot session.

**Cause**: capture hooks are fail-open by design. A script error or malformed
payload skips capture rather than blocking Copilot.

**Fix**: confirm the capture script and event directory, then import and rebuild.
`/sessielog` is also available for explicit capture:
```bash
ls "$HOME/KennisBank/.claude/scripts/kb-copilot-capture.py"
ls "$HOME/KennisBank/.claude/copilot-events/"
python3 "$HOME/KennisBank/.claude/scripts/import-copilot.py" --vault "$HOME/KennisBank"
python3 "$HOME/KennisBank/.claude/scripts/build-activity-index.py" --vault "$HOME/KennisBank" --full
```

### 9.6 Keeping a Copilot session out of the vault (privacy)

**Symptom**: you want a Copilot session that is not recorded into KennisBank.

**Cause**: capture is on by default and fail-open.

**Fix**: launch through the wrapper with `--no-capture`, or set
`KENNISBANK_COPILOT_NO_CAPTURE=1`.

### 9.7 Copilot still prints `SessionStart hook (completed)`

**Cause**: one row is expected: Copilot renders it for the single coordinator
and child process output cannot hide it. Multiple KennisBank rows mean an older
fan-out is still installed; other rows may belong to another tool.

**Fix**: upgrade and inspect the remaining hooks:

```bash
KENNISBANK_VAULT="$HOME/KennisBank" bash setup.sh --yes --agents copilot
```

Setup replaces only legacy KennisBank SessionStart commands. If more than one
row remains, inspect `~/.copilot/hooks/*.json`; unrelated integrations are
intentionally preserved.

### 9.8 Multiple exit-hook rows or missing final-session activity

**Cause**: an older install still registers `archive-transcript.py`,
`kb-usage-scan.py`, or Copilot `kb-copilot-capture.py --event sessionEnd`
separately. One generic SessionEnd/Stop row may remain because the client owns
that UI; multiple KennisBank rows indicate legacy fan-out.

**Fix**: rerun setup for the affected clients. Migration removes only the known
KennisBank exit basenames, deduplicates `kb-session-end.py`, and preserves
unrelated exit hooks:

```bash
KENNISBANK_VAULT="$HOME/KennisBank" bash setup.sh --yes --agents claude,codex,copilot
```

The exit coordinator is silent and fail-open. Its last diagnostic state is:

```bash
python3 -m json.tool "$HOME/KennisBank/.claude/kb-session-end-state.json"
```

`"ok": false` lists the timed-out or failing child without delaying or blocking
client shutdown.
