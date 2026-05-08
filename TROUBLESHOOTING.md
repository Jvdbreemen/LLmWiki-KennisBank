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

**Symptom**: `Embedding mislukt. Is nomic-embed-text geïnstalleerd?`

**Cause**: The script shells out to `ollama embed --model nomic-embed-text`. Either Ollama is not installed, the daemon is down, or the model is not pulled. See section 8.

**Fix**:
```bash
which ollama && ollama list | grep nomic-embed-text
ollama pull nomic-embed-text
ollama serve &
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
curl -s http://localhost:11434/api/tags >/dev/null && echo "ollama up" || echo "ollama down"
```
On macOS, `/Applications/Ollama.app` also launches the daemon.

### 8.3 Model not pulled

**Symptom**: `Error: model 'nomic-embed-text' not found`.

**Cause**: Ollama only loads what you pull.

**Fix**:
```bash
ollama pull nomic-embed-text
ollama list | grep nomic-embed-text
```

### 8.4 Wrong model name in script

**Symptom**: You replaced the embedding model and `semantic-tiling.py` fails or returns no embedding.

**Cause**: `OLLAMA_MODEL` in the script is hardcoded to `nomic-embed-text`. Different models can return different output schemas.

**Fix**: Edit `OLLAMA_MODEL` at the top of `$HOME/KennisBank/.claude/scripts/semantic-tiling.py`. Confirm the new model returns `{"embedding": [...]}` or `{"embeddings": [[...]]}`. Adapt `get_embedding` if it returns something else.

### 8.5 Stale embedding cache

**Symptom**: Tiling reports duplicates that no longer match disk content, or fails to deserialize the cache.

**Cause**: `$HOME/KennisBank/.claude/embeddings-cache.json` was edited by hand or written during a crash.

**Fix**:
```bash
rm "$HOME/KennisBank/.claude/embeddings-cache.json"
```
The script rebuilds the cache on next run.
