# AGENTS.md

Instructions for an AI coding agent (Claude Code, Cursor, Aider, etc.) installing this repo on behalf of a user.

The human-facing guide is `README.md`. This file is operational. Read it end-to-end before touching anything.

## 1. Purpose

This repo deploys a personal LLM-wiki layer on top of Claude Code, based on Karpathy's LLM Wiki concept. It installs a vault at `$HOME/KennisBank/`, a research output directory at `$HOME/Claude/research/`, four global slash commands (`/sessielog`, `/wiki`, `/intake`, `/stale`), and one skill (`/autoresearch`).

Your job: install this system on the user's machine without breaking their existing Claude Code configuration. You are not refactoring the repo. You are deploying it.

## 2. Pre-flight checks

Run these before installing. Each line is the check, followed by how to interpret the result.

```bash
# Working directory: confirm you are inside the repo clone
test -f ./setup.sh && test -d ./commands && echo OK || echo "WRONG DIR"
```
If "WRONG DIR": stop. Ask the user where the repo was cloned.

```bash
# Vault: does it already exist?
test -d "$HOME/KennisBank" && echo EXISTS || echo NEW
```
If EXISTS: do not assume the structure matches. Inspect with `ls $HOME/KennisBank` and confirm with the user before running setup. `setup.sh` is idempotent for `mkdir -p` but will not overwrite an existing `CLAUDE.md`.

```bash
# Claude Code commands directory
test -d "$HOME/.claude/commands" && echo EXISTS || echo NEW
```
If NEW: `setup.sh` will create it. If EXISTS: check for filename collisions before copying.

```bash
# Filename collisions in commands
for f in commands/*.md; do
  base=$(basename "$f")
  test -f "$HOME/.claude/commands/$base" && echo "COLLISION: $base"
done
```
Any COLLISION line: stop and ask the user whether to overwrite.

```bash
# Skill collision
test -f "$HOME/.claude/skills/autoresearch/SKILL.md" && echo "SKILL EXISTS" || echo "SKILL NEW"
```
If SKILL EXISTS: ask before overwriting.

```bash
# Python version (3.10+ required)
python3 --version
```
If lower than 3.10: scripts using modern syntax may fail. Warn the user.

```bash
# Ollama presence (optional, for semantic tiling)
command -v ollama >/dev/null && echo PRESENT || echo MISSING
```
If MISSING: not a blocker. Note it in the hand-off so the user knows semantic tiling will be skipped.

```bash
# Memory directory exists
ls "$HOME/.claude/projects/"*/memory/MEMORY.md 2>/dev/null | head -1
```
Empty output: the lazy-hierarchy memory check in commands will silently skip Layer 1. Not a blocker.

```bash
# Global Claude config present
test -f "$HOME/.claude/CLAUDE.md" && echo EXISTS || echo NEW
```
Record this. You will append to it later. Never overwrite.

## 3. Non-interactive install path

Recommended path once `--yes` is merged (it skips the two interactive prompts in `setup.sh`):

```bash
bash setup.sh --yes
```

This installs everything: vault structure, scripts, templates, commands, and the autoresearch skill.

If `--yes` is not yet present in the version you cloned, fall back to the manual path.

### Manual path (always works)

```bash
VAULT="$HOME/KennisBank"
RESEARCH="$HOME/Claude/research"
CLAUDE_COMMANDS="$HOME/.claude/commands"
CLAUDE_SKILLS="$HOME/.claude/skills"

mkdir -p "$VAULT"/{00-inbox,01-raw/sessies,02-wiki,03-projecten,04-templates,05-bronnen,06-claude,07-media,08-archive}
mkdir -p "$VAULT/.claude/scripts" "$VAULT/graphify-out" "$RESEARCH"

cp scripts/*.py "$VAULT/.claude/scripts/"
chmod +x "$VAULT/.claude/scripts/"*.py
cp templates/*.md "$VAULT/04-templates/"

# Only if not present
test -f "$VAULT/CLAUDE.md" || cp CLAUDE.md.template "$VAULT/CLAUDE.md"

mkdir -p "$CLAUDE_COMMANDS"
cp commands/*.md "$CLAUDE_COMMANDS/"

mkdir -p "$CLAUDE_SKILLS/autoresearch"
cp skills/autoresearch/SKILL.md "$CLAUDE_SKILLS/autoresearch/"
```

Use the manual path when:
- `setup.sh` lacks `--yes` and you cannot block on `read REPLY` prompts
- The user wants to skip the commands or skill copy
- A pre-flight check found a collision and you need fine-grained control

## 4. What to ask the user before installing

Ask these as a single grouped message. Defaults are in brackets.

1. Vault path. Default: `$HOME/KennisBank`. If they pick a different path, note that paths are hard-coded in several places and you will need to patch them (see Section 9).
2. Research output path. Default: `$HOME/Claude/research`. Same caveat.
3. Install global commands to `$HOME/.claude/commands/`? Default: yes.
4. Install autoresearch skill to `$HOME/.claude/skills/`? Default: yes.
5. Append the autoresearch trigger snippet to `$HOME/.claude/CLAUDE.md`? Default: yes if the file exists, otherwise create it from the snippet only.

If the user says "just install it" without specifying: take the defaults and report what you did.

## 5. Post-install verification

Run the doctor script:

```bash
bash scripts/doctor.sh
```

Expected output: every check line ends in `OK`. Any `FAIL` is a blocker. Any `WARN` is non-fatal but should be reported in the hand-off.

If `scripts/doctor.sh` is missing in the version you cloned, run these manual checks:

```bash
# Vault structure
ls "$HOME/KennisBank/" | sort
# Expected: 00-inbox 01-raw 02-wiki 03-projecten 04-templates 05-bronnen 06-claude 07-media 08-archive CLAUDE.md

# Scripts copied and executable
ls -l "$HOME/KennisBank/.claude/scripts/"*.py

# Templates present
ls "$HOME/KennisBank/04-templates/"

# Commands installed
ls "$HOME/.claude/commands/" | grep -E '^(sessielog|wiki|intake|stale)\.md$'

# Skill installed
test -f "$HOME/.claude/skills/autoresearch/SKILL.md" && echo OK

# CLAUDE.md present (not overwritten if it already had user content)
head -3 "$HOME/KennisBank/CLAUDE.md"

# Python scripts at least parse
python3 -c "import ast; ast.parse(open('$HOME/KennisBank/.claude/scripts/stale-check.py').read())"
```

## 6. Patching `$HOME/.claude/CLAUDE.md`

The autoresearch skill needs a trigger registered in the global `CLAUDE.md`. Append, do not overwrite.

Snippet to append:

```
# autoresearch
- **autoresearch** (`~/.claude/skills/autoresearch/SKILL.md`) - multi-round research with lazy hierarchy check. Output to `~/Claude/research/`. Trigger: `/autoresearch`
When the user types `/autoresearch`, invoke the Skill tool with `skill: "autoresearch"` before doing anything else.
```

Safe append:

```bash
GLOBAL="$HOME/.claude/CLAUDE.md"
if ! grep -q "^# autoresearch" "$GLOBAL" 2>/dev/null; then
  printf '\n# autoresearch\n- **autoresearch** (`~/.claude/skills/autoresearch/SKILL.md`) - multi-round research with lazy hierarchy check. Output to `~/Claude/research/`. Trigger: `/autoresearch`\nWhen the user types `/autoresearch`, invoke the Skill tool with `skill: "autoresearch"` before doing anything else.\n' >> "$GLOBAL"
fi
```

Rules:
- Always check for an existing `# autoresearch` heading first. If present, skip.
- Never use `>` redirection. Only `>>`.
- If the file does not exist, create it with the snippet alone. Do not invent surrounding content.

## 7. Common mistakes

Things agents typically get wrong here:

1. **Overwriting an existing `CLAUDE.md`.** Both the global `$HOME/.claude/CLAUDE.md` and the vault `$HOME/KennisBank/CLAUDE.md` can have user customizations. Append. Never `cp` over them.
2. **Hardcoding `/Users/X/` paths from training data.** Always use `$HOME` or `~`. The user's username is not in your training set.
3. **Assuming Ollama is installed.** It is optional. If absent, semantic tiling is skipped silently. Do not install Ollama for the user without asking.
4. **Running `setup.sh` from the wrong directory.** The script uses relative paths (`scripts/*.py`, `commands/*.md`). Run it from the repo root. Verify with the working-directory check in Section 2.
5. **Blocking on `read REPLY` prompts.** Default `setup.sh` is interactive. Use `--yes` once available, or use the manual path. Do not pipe `yes` into setup.sh blindly; that answers prompts you may not want to accept.
6. **Treating the vault as read-only.** `$HOME/KennisBank/CLAUDE.md` is meant to be edited. After install, point the user to `[YOUR NAME]` and `[YOUR PROJECTS]` placeholders.
7. **Copying scripts to the wrong location.** They go to `$HOME/KennisBank/.claude/scripts/`, not `$HOME/.claude/scripts/`. The commands reference the vault path.
8. **Forgetting `chmod +x` on the Python scripts** when using the manual path.
9. **Skipping the collision check.** A user with existing slash commands of the same name will lose them silently if you `cp` without checking.

## 8. Hand-off to user

After install completes, tell the user:

1. The vault is at `$HOME/KennisBank/`. Edit `CLAUDE.md` there to fill in `[YOUR NAME]` and `[YOUR PROJECTS]`.
2. Four new slash commands are available: `/sessielog`, `/wiki`, `/intake`, `/stale`.
3. The `/autoresearch` skill is available; trigger it with `/autoresearch [topic]`.
4. Research output lands in `$HOME/Claude/research/`.
5. If Ollama is not installed, semantic tiling is skipped. To enable: `ollama pull nomic-embed-text`.
6. To verify any time: `bash scripts/doctor.sh` from the repo clone.
7. Restart Claude Code (or reload commands) so the new slash commands are picked up.

Report any pre-flight WARN or skipped optional step. Do not report items as done that you did not do.

## 9. Customization pointers

If the user wants non-default paths or thresholds, edit these locations.

| Setting | File | What to change |
|---|---|---|
| Vault path | `setup.sh` | `VAULT="$HOME/KennisBank"` |
| Vault path (runtime) | `commands/*.md`, `skills/autoresearch/SKILL.md` | Hardcoded `~/KennisBank/...` references |
| Research output | `setup.sh` | `RESEARCH="$HOME/Claude/research"` |
| Research output (runtime) | `skills/autoresearch/SKILL.md` | Output paths in "Output aanmaken" and report sections |
| Stale threshold | `scripts/stale-check.py` | `THRESHOLD_DAYS` constant, or pass `--days N` |
| Memory file lookup | `CLAUDE.md.template`, `skills/autoresearch/SKILL.md` | The `ls ~/.claude/projects/*/memory/MEMORY.md` glob |
| Vault `CLAUDE.md` content | `CLAUDE.md.template` | Template copied to vault on install |

If the user picks a non-default vault path, do a sweep before declaring done:

```bash
grep -rn "KennisBank" commands/ skills/ scripts/
```

Patch every match to the new path, or warn the user that the default path remains baked into command bodies.

## 10. Notes on this file

This file lives at the repo root. Its peer for humans is `README.md`. If you change behavior in `setup.sh` or the install paths, update both. Keep this file terse, declarative, and operational.
