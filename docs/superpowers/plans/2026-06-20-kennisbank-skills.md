# Kennisbank Upgrade & Contribute Skills Implementation Plan

> **SUPERSEDED IN PART (2026-06-20, v0.6.1):** the skills deploy map was later
> generalized from `autoresearch`-only to **all `skills/*/`** (so the upgrade
> refreshes the kennisbank skills themselves and contribute can push any skill).
> The `skills/autoresearch/SKILL.md`-only deploy-map rows in the task briefs
> below reflect the original v0.6.0 build and are kept as the historical record.
> For the current generalized contract see the design spec and the live
> `skills/kennisbank-upgrade/SKILL.md` / `skills/kennisbank-contribute/SKILL.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two invocable skills — `kennisbank-upgrade` (pull latest release tag into a vault) and `kennisbank-contribute` (push local vault tooling improvements upstream as a PR) — plus the v0.6.0 release that captures the unreleased fixes.

**Architecture:** Two self-contained `SKILL.md` instruction files drive an agent through git/gh steps. A shared deploy map (repo path -> deploy path) and a JSON version stamp in the vault are the contract both skills rely on. `setup.sh` is fixed to deploy `*.sh` and to install the two new skills. Everything lands in a v0.6.0 tag/release.

**Tech Stack:** bash, git, GitHub CLI (`gh`), Python 3.12 stdlib `unittest` (existing test layer), markdown skill files.

## Global Constraints

- **Cross-platform: every script and test in this project must work on macOS, Linux, and Windows (Git Bash).** Tests must pass on all three. Never pass a Windows-style path (`C:\...`) to a bash subprocess — convert to Git Bash POSIX form (`/c/...`) first.
- Upgrade source of truth: latest **release tag** only (`v[0-9]*`), never bare `main`.
- Vault path resolves via `KENNISBANK_VAULT`, fallback `$HOME/KennisBank`. `setup.sh` honors `KENNISBANK_VAULT` too.
- Repo clone path resolves via `KENNISBANK_REPO`, else the skill asks the user.
- All deployed-vs-repo file comparisons are CRLF-agnostic (`diff --strip-trailing-cr`).
- Version stamp file: `$VAULT/.claude/.kennisbank-version`, JSON keys `tag`, `commit`, `installed_at` (UTC ISO 8601).
- Contribute scope includes only scripts, templates, commands, autoresearch skill. Never `CLAUDE.md`, `categories.json`, `embeddings-cache.json`, `*.bak`, vault content dirs `00-*`..`08-*`, or `.kennisbank-version`.
- Deploy map (authoritative):
  | Repo source | Deploy destination |
  |---|---|
  | `scripts/*.py`, `scripts/*.sh` | `$VAULT/.claude/scripts/` |
  | `templates/*.md` | `$VAULT/04-templates/` |
  | `commands/*.md` | `$HOME/.claude/commands/` |
  | `skills/autoresearch/SKILL.md` | `$HOME/.claude/skills/autoresearch/` |
- CI must stay green: `python3 -m py_compile scripts/*.py`, `bash -n setup.sh scripts/doctor.sh`, `python3 -m unittest discover -s tests`.
- Work happens on branch `feat/kennisbank-skills` (already created). Commit frequently.

---

### Task 1: Fix setup.sh to deploy shell scripts

**Files:**
- Modify: `setup.sh` — the `VAULT=` line (~94) and the Scripts copy loop (~110-114)
- Test: `tests/test_setup_deploy.py` (create)

**Interfaces:**
- Produces: a deployed vault layout where `<vault>/.claude/scripts/doctor.sh` exists after `bash setup.sh --yes`, with `setup.sh` honoring `KENNISBANK_VAULT`.

**Cross-platform note:** the test launches `bash setup.sh` as a subprocess. On
Windows, Git Bash mangles Windows-style paths (`C:\...`) passed via env, so the
test MUST convert any path it hands to bash into POSIX form (`/c/...`). The
`_bash_path` helper below does this; it is identity on macOS/Linux.

- [ ] **Step 1: Write the failing test**

Create `tests/test_setup_deploy.py`:

```python
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _bash_path(p: Path) -> str:
    """Convert a path to a form Git Bash accepts.

    On Windows, C:\\Users\\x -> /c/Users/x (drive letter lowercased, backslashes
    to forward slashes). On macOS/Linux the path is already POSIX, so identity.
    """
    if sys.platform.startswith("win"):
        s = str(p).replace("\\", "/")
        if len(s) > 1 and s[1] == ":":
            s = "/" + s[0].lower() + s[2:]
        return s
    return str(p)


class SetupDeployTest(unittest.TestCase):
    def run_setup(self):
        tmp = Path(tempfile.mkdtemp(prefix="kb-home-"))
        vault = tmp / "KennisBank"
        env = dict(os.environ)
        # HOME drives the ~/.claude deploy targets; KENNISBANK_VAULT drives the
        # vault. Both must be POSIX-form so Git Bash resolves them correctly.
        env["HOME"] = _bash_path(tmp)
        env["USERPROFILE"] = _bash_path(tmp)
        env["KENNISBANK_VAULT"] = _bash_path(vault)
        subprocess.run(
            ["bash", "setup.sh", "--yes"],
            cwd=REPO_ROOT, env=env, check=True,
            capture_output=True, text=True,
        )
        return tmp, vault

    def test_doctor_sh_is_deployed(self):
        tmp, vault = self.run_setup()
        try:
            doctor = vault / ".claude" / "scripts" / "doctor.sh"
            self.assertTrue(doctor.is_file(), f"doctor.sh not deployed at {doctor}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_python_scripts_still_deployed(self):
        tmp, vault = self.run_setup()
        try:
            common = vault / ".claude" / "scripts" / "_common.py"
            self.assertTrue(common.is_file(), "_common.py regressed out of deploy")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_setup_deploy -v`
Expected: both tests FAIL — `setup.sh` does not yet honor `KENNISBANK_VAULT`
(so the vault lands at `$HOME/KennisBank`, not the test's vault) and does not
deploy `doctor.sh`.

- [ ] **Step 3: Make setup.sh honor KENNISBANK_VAULT**

In `setup.sh`, replace the line (~94):

```bash
VAULT="$HOME/KennisBank"
```

with:

```bash
VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"
```

This matches the rest of the codebase, which already resolves the vault via
`KENNISBANK_VAULT` (see `scripts/_vaultpath.py`).

- [ ] **Step 4: Make setup.sh deploy shell scripts**

In `setup.sh`, replace the Scripts block (~110-114):

```bash
# Scripts
for f in scripts/*.py; do
  copy_file "$f" "$VAULT/.claude/scripts/$(basename "$f")"
done
chmod +x "$VAULT/.claude/scripts/"*.py
```

with:

```bash
# Scripts (Python helpers + shell tools like doctor.sh)
for f in scripts/*.py scripts/*.sh; do
  copy_file "$f" "$VAULT/.claude/scripts/$(basename "$f")"
done
chmod +x "$VAULT/.claude/scripts/"*.py "$VAULT/.claude/scripts/"*.sh
```

(`shopt -s nullglob` is already set at the top of `setup.sh`, so an empty
`*.sh` glob is safe.)

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m unittest tests.test_setup_deploy -v`
Expected: both tests PASS on this platform.

- [ ] **Step 6: Shell syntax check**

Run: `bash -n setup.sh`
Expected: no output, exit 0.

- [ ] **Step 7: Commit**

```bash
git add setup.sh tests/test_setup_deploy.py
git commit -m "fix(setup): honor KENNISBANK_VAULT and deploy scripts/*.sh (doctor.sh)"
```

---

### Task 2: Create the kennisbank-upgrade skill

**Files:**
- Create: `skills/kennisbank-upgrade/SKILL.md`
- Test: `tests/test_skill_frontmatter.py` (create)

**Interfaces:**
- Consumes: deploy map and version-stamp format from Global Constraints.
- Produces: `skills/kennisbank-upgrade/SKILL.md` with YAML frontmatter keys `name: kennisbank-upgrade` and a non-empty `description`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_skill_frontmatter.py`:

```python
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = ["kennisbank-upgrade", "kennisbank-contribute"]


def read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---"), f"{path} missing frontmatter open"
    end = text.index("\n---", 3)
    body = text[3:end]
    fm = {}
    for line in body.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, val = line.split(":", 1)
        fm[key.strip()] = val.strip()
    return fm


class SkillFrontmatterTest(unittest.TestCase):
    def test_skill_files_have_valid_frontmatter(self):
        for slug in SKILLS:
            path = REPO_ROOT / "skills" / slug / "SKILL.md"
            self.assertTrue(path.is_file(), f"missing {path}")
            fm = read_frontmatter(path)
            self.assertEqual(fm.get("name"), slug, f"{path} name mismatch")
            self.assertTrue(fm.get("description"), f"{path} empty description")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_skill_frontmatter -v`
Expected: FAIL ("missing .../kennisbank-upgrade/SKILL.md").

- [ ] **Step 3: Write the skill file**

Create `skills/kennisbank-upgrade/SKILL.md`:

```markdown
---
name: kennisbank-upgrade
description: Upgrade a deployed LLmWiki-KennisBank vault to the latest official release tag. Checks the upstream tag, shows the changelog, backs up the current deploy, copies the new tooling into the vault, stamps the version, and verifies with doctor.sh. Triggers: /kennisbank-upgrade, "upgrade kennisbank", "update kennisbank tooling".
---

# Kennisbank Upgrade

Upgrade a deployed vault to the latest **release tag** (never bare main).

## Resolve paths
- `VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`
- `REPO="${KENNISBANK_REPO}"` — if empty, ask the user for the path to their
  LLmWiki-KennisBank git checkout. Confirm it is a git repo (`git -C "$REPO" rev-parse`).

## Deploy map
| Repo source | Deploy destination |
|---|---|
| `scripts/*.py`, `scripts/*.sh` | `$VAULT/.claude/scripts/` |
| `templates/*.md` | `$VAULT/04-templates/` |
| `commands/*.md` | `$HOME/.claude/commands/` |
| `skills/autoresearch/SKILL.md` | `$HOME/.claude/skills/autoresearch/` |

`CLAUDE.md` is personalized and is NEVER overwritten.

## Procedure
1. `git -C "$REPO" fetch --tags --quiet`.
2. `LATEST=$(git -C "$REPO" tag --sort=-v:refname | grep '^v[0-9]' | head -1)`.
3. Read `$VAULT/.claude/.kennisbank-version` -> `INSTALLED` (the `tag` field).
   If the file is absent, treat as unknown/legacy and tell the user.
4. If `INSTALLED == LATEST`: report "up to date ($LATEST)" and stop.
5. Show what changed: print the CHANGELOG.md section(s) between INSTALLED and
   LATEST (`git -C "$REPO" show "$LATEST:CHANGELOG.md"`).
6. Drift guard: for every deployed tooling file, CRLF-agnostic diff against the
   INSTALLED tag's version:
   `diff --strip-trailing-cr <(git -C "$REPO" show "$INSTALLED:scripts/<f>") "$VAULT/.claude/scripts/<f>"`.
   If any differ, warn the user that local edits exist, point them to the
   `kennisbank-contribute` skill, and ask whether to proceed (local edits will
   survive only in the backup).
7. On confirmation, back up: copy `$VAULT/.claude/scripts` to
   `$VAULT/.claude/scripts.pre-$INSTALLED.bak` (matching the existing `.bak`
   convention). Back up `$VAULT/04-templates` the same way if templates changed.
8. `git -C "$REPO" -c advice.detachedHead=false checkout "$LATEST"`.
9. Copy per the deploy map: `scripts/*.py` and `scripts/*.sh` -> vault scripts;
   `templates/*.md` -> vault templates; `commands/*.md` -> `~/.claude/commands/`;
   `skills/autoresearch/SKILL.md` -> `~/.claude/skills/autoresearch/`.
   `chmod +x` the vault `.py` and `.sh` files. Do not touch `CLAUDE.md`.
10. Write `$VAULT/.claude/.kennisbank-version`:
    `{"tag":"$LATEST","commit":"<git rev-parse --short $LATEST>","installed_at":"<UTC ISO 8601>"}`.
11. `git -C "$REPO" checkout main` (return to a branch).
12. Run `bash "$VAULT/.claude/scripts/doctor.sh"` and report the PASS count.

## Dry-run
If invoked with `--dry-run`, perform steps 1-6 and print the planned copies and
backups, but make no writes (no backup, no copy, no stamp, no checkout side
effects beyond fetch).
```

- [ ] **Step 4: Run test to verify it passes (upgrade half)**

Run: `python3 -m unittest tests.test_skill_frontmatter -v`
Expected: still FAILS, now on the missing `kennisbank-contribute` file (upgrade frontmatter is satisfied). This is expected; Task 3 completes it.

- [ ] **Step 5: Commit**

```bash
git add skills/kennisbank-upgrade/SKILL.md tests/test_skill_frontmatter.py
git commit -m "feat(skills): add kennisbank-upgrade skill"
```

---

### Task 3: Create the kennisbank-contribute skill

**Files:**
- Create: `skills/kennisbank-contribute/SKILL.md`

**Interfaces:**
- Consumes: deploy map, version stamp, and `tests/test_skill_frontmatter.py` from Task 2.
- Produces: `skills/kennisbank-contribute/SKILL.md` with `name: kennisbank-contribute`.

- [ ] **Step 1: Write the skill file**

Create `skills/kennisbank-contribute/SKILL.md`:

```markdown
---
name: kennisbank-contribute
description: Isolate local tooling improvements made in a deployed LLmWiki-KennisBank vault and contribute them upstream as a pull request. Diffs deployed scripts/templates/commands/skill against the installed release tag, filters out personal vault content, then branches, commits, pushes, and opens a PR. Triggers: /kennisbank-contribute, "contribute kennisbank changes", "PR my kennisbank tweaks upstream".
---

# Kennisbank Contribute

Take local tooling edits in a deployed vault and open an upstream PR.

## Resolve paths
- `VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`
- `REPO="${KENNISBANK_REPO}"` — if empty, ask the user. Must be a git checkout
  of LLmWiki-KennisBank with a writable `origin` remote.

## Reverse deploy map (deployed location -> repo path)
| Deployed location | Repo path |
|---|---|
| `$VAULT/.claude/scripts/<f>` | `scripts/<f>` |
| `$VAULT/04-templates/<f>.md` | `templates/<f>.md` |
| `$HOME/.claude/commands/<f>.md` | `commands/<f>.md` |
| `$HOME/.claude/skills/autoresearch/SKILL.md` | `skills/autoresearch/SKILL.md` |

## Scope filter (NEVER contribute these)
`CLAUDE.md`, `categories.json`, `embeddings-cache.json`, any `*.bak`, the vault
content directories `00-*`..`08-*`, and `.kennisbank-version`.

## Procedure
1. Read `$VAULT/.claude/.kennisbank-version` -> `BASE` (`tag`). If absent, use
   `BASE=$(git -C "$REPO" tag --sort=-v:refname | grep '^v[0-9]' | head -1)`.
2. `git -C "$REPO" fetch --tags --quiet`.
3. For each deployed location in the reverse deploy map, CRLF-agnostic diff the
   deployed file against `BASE`'s version of the mapped repo path:
   `diff --strip-trailing-cr <(git -C "$REPO" show "$BASE:<repopath>") "<deployed>"`.
   A file that is new (no `BASE` version) counts as added. Collect the changed
   and added repo paths, applying the scope filter.
4. If nothing qualifies, report "no contributable changes" and stop.
5. Show the user the candidate file list with per-file diffs. Let them choose
   which files to include (default: all).
6. Create a branch: `git -C "$REPO" checkout -b "contrib/<slug>" main`
   (slug from a short user-supplied description).
7. For each selected file, copy the deployed version into the repo at its mapped
   repo path. `git -C "$REPO" add` those paths.
8. Commit with a descriptive message summarizing the change.
9. `git -C "$REPO" push -u origin "contrib/<slug>"`.
10. `gh pr create --repo <upstream> --base main --head "contrib/<slug>"` with a
    title and body describing the improvement. Report the PR URL.

## Dry-run
If invoked with `--dry-run`, perform steps 1-5 and print the branch name and the
files that would be committed, but do not create the branch, commit, push, or PR.
```

- [ ] **Step 2: Run the frontmatter test to verify both skills pass**

Run: `python3 -m unittest tests.test_skill_frontmatter -v`
Expected: PASS (both skill files now present with valid frontmatter).

- [ ] **Step 3: Commit**

```bash
git add skills/kennisbank-contribute/SKILL.md
git commit -m "feat(skills): add kennisbank-contribute skill"
```

---

### Task 4: Install the new skills via setup.sh

**Files:**
- Modify: `setup.sh:153-165` (the skill install block) and `setup.sh:43` usage text
- Test: `tests/test_setup_deploy.py` (extend)

**Interfaces:**
- Consumes: the two skill files from Tasks 2-3.
- Produces: a deployed `$HOME/.claude/skills/kennisbank-upgrade/SKILL.md` and `.../kennisbank-contribute/SKILL.md` after `bash setup.sh --yes`.

- [ ] **Step 1: Write the failing test (extend)**

Append to `tests/test_setup_deploy.py` inside `SetupDeployTest`:

```python
    def test_new_skills_are_installed(self):
        tmp, vault = self.run_setup()
        try:
            base = tmp / ".claude" / "skills"
            for slug in ("kennisbank-upgrade", "kennisbank-contribute"):
                skill = base / slug / "SKILL.md"
                self.assertTrue(skill.is_file(), f"{slug} not installed at {skill}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_setup_deploy -v`
Expected: `test_new_skills_are_installed` FAILS.

- [ ] **Step 3: Implement the install**

In `setup.sh`, find the autoresearch skill `--yes` branch (around line 155-157):

```bash
elif [ "$ASSUME_YES" = "1" ]; then
  mkdir -p "$CLAUDE_SKILLS/autoresearch"
  copy_file skills/autoresearch/SKILL.md "$CLAUDE_SKILLS/autoresearch/SKILL.md"
```

Replace that two-line copy with a loop over every skill directory:

```bash
elif [ "$ASSUME_YES" = "1" ]; then
  for sdir in skills/*/; do
    sname="$(basename "$sdir")"
    mkdir -p "$CLAUDE_SKILLS/$sname"
    copy_file "${sdir}SKILL.md" "$CLAUDE_SKILLS/$sname/SKILL.md"
  done
```

Apply the identical loop to the interactive branch (around line 161-163):

```bash
  if [ "$REPLY" = "y" ] || [ "$REPLY" = "Y" ]; then
    for sdir in skills/*/; do
      sname="$(basename "$sdir")"
      mkdir -p "$CLAUDE_SKILLS/$sname"
      copy_file "${sdir}SKILL.md" "$CLAUDE_SKILLS/$sname/SKILL.md"
    done
  fi
```

Update the usage line `setup.sh:42` describing `--no-skill` from "de autoresearch skill" to "de skills (autoresearch, kennisbank-upgrade, kennisbank-contribute)".

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_setup_deploy -v`
Expected: all three deploy tests PASS.

- [ ] **Step 5: Shell syntax check**

Run: `bash -n setup.sh`
Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add setup.sh tests/test_setup_deploy.py
git commit -m "feat(setup): install all skills/ dirs, not just autoresearch"
```

---

### Task 5: Document v0.6.0 in the changelog

**Files:**
- Modify: `CHANGELOG.md` (the `[Unreleased]` section and the link refs at the bottom)

**Interfaces:**
- Consumes: nothing.
- Produces: a `## [0.6.0]` section listing the qwen3 default, configurable thresholds, doctor.sh OLLAMA_EMBED_MODEL awareness, the setup.sh `*.sh` fix, and the two new skills.

- [ ] **Step 1: Edit CHANGELOG.md**

Replace the empty `## [Unreleased]` line with:

```markdown
## [Unreleased]

## [0.6.0] - 2026-06-20

Multilingual embedding default, configurable tiling thresholds, a deploy-gap
fix, and two new lifecycle skills for upgrading a vault and contributing
improvements upstream.

### Added

- **`kennisbank-upgrade` skill** — upgrades a deployed vault to the latest
  official release tag: checks the upstream tag, shows the changelog, guards
  against clobbering local edits, backs up the current deploy, copies the new
  tooling, stamps `$VAULT/.claude/.kennisbank-version`, and verifies with
  `doctor.sh`.
- **`kennisbank-contribute` skill** — isolates local tooling edits in a
  deployed vault (scripts, templates, commands, skill), filters out personal
  vault content, and opens an upstream PR.
- **`qwen3-embedding:8b` as the default embedding model** (multilingual, 119
  languages) with `nomic-embed-text` as the lighter English-only fallback via
  `OLLAMA_EMBED_MODEL`.
- **Configurable tiling thresholds** `TILING_THRESHOLD_ERROR` /
  `TILING_THRESHOLD_REVIEW`, with robust NL-decimal parsing and a safe fallback
  instead of a crash on bad input.

### Fixed

- **`setup.sh` now deploys `scripts/*.sh`**, so `doctor.sh` ships with every
  install instead of relying on a manual copy.
- **`doctor.sh` respects `OLLAMA_EMBED_MODEL`** and reports the actual default
  (`qwen3-embedding:8b`) instead of hardcoding `nomic-embed-text`.
```

At the bottom of the file, update the link reference block. Replace:

```markdown
[Unreleased]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.5.0...HEAD
```

with:

```markdown
[Unreleased]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.6.0
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: changelog for v0.6.0"
```

---

### Task 6: Run the full suite, open the PR, release v0.6.0, stamp the live deploy

**Files:**
- No source files; release + deploy actions.

**Interfaces:**
- Consumes: all prior tasks merged to `main`.
- Produces: tag `v0.6.0`, a GitHub release, and a stamped live Kluis deploy.

- [ ] **Step 1: Run the full test suite locally**

Run:
```bash
python3 -m py_compile scripts/*.py
bash -n setup.sh scripts/doctor.sh
python3 -m unittest discover -s tests -v
```
Expected: all green.

- [ ] **Step 2: Push the branch and open the PR**

```bash
git push -u origin feat/kennisbank-skills
gh pr create --base main --head feat/kennisbank-skills \
  --title "feat: kennisbank-upgrade & contribute skills + v0.6.0" \
  --body "Adds two lifecycle skills, fixes the setup.sh .sh deploy gap, and cuts v0.6.0. See docs/superpowers/specs/2026-06-20-kennisbank-upgrade-contribute-skills-design.md."
```

Wait for CI to pass and for the user to merge (the user owns the merge decision).

- [ ] **Step 3: After merge, tag and release v0.6.0**

```bash
git checkout main && git pull
git tag -a v0.6.0 -m "v0.6.0 — multilingual embeddings, threshold config, lifecycle skills"
git push origin v0.6.0
gh release create v0.6.0 --title "v0.6.0 — lifecycle skills + multilingual embeddings" --notes-from-tag
```
Expected: `gh release list` shows v0.6.0 as Latest.

- [ ] **Step 4: Stamp the live Kluis deploy**

Write `D:/Users/Robert/Documents/Claude/Projects/Kluis/.claude/.kennisbank-version`:

```json
{"tag": "v0.6.0", "commit": "<git rev-parse --short v0.6.0>", "installed_at": "<UTC ISO 8601>"}
```

(The live deploy already runs v0.6.0 content; this records it so the
`kennisbank-upgrade` skill sees it as up to date.)

- [ ] **Step 5: Verify the deploy is healthy**

Run: `bash "D:/Users/Robert/Documents/Claude/Projects/Kluis/.claude/scripts/doctor.sh"`
Expected: PASS, ollama line reports `qwen3-embedding:8b: installed`.

---

## Self-Review

**Spec coverage:**
- Two skills (upgrade, contribute) — Tasks 2, 3. ✓
- Tag-based upgrade source of truth — upgrade skill step 2. ✓
- Cut v0.6.0 — Tasks 5, 6. ✓
- Contribute scope filter — contribute skill scope-filter section. ✓
- Deploy map incl. `*.sh` fix — Task 1, both skills. ✓
- Version stamp — defined in constraints, written by upgrade skill, stamped live in Task 6. ✓
- CRLF-agnostic diffing — both skills. ✓
- setup.sh installs the skills — Task 4. ✓
- Vault/repo resolution — both skills' "Resolve paths". ✓
- Testing (dry-run, doctor gate, round-trip) — dry-run sections + Task 6 step 5. ✓

**Placeholder scan:** No TBD/TODO; every code/edit step shows concrete content. `<slug>`, `<f>`, `<upstream>`, `<UTC ISO 8601>` are runtime-substituted values inside skill instructions, not plan placeholders.

**Type/name consistency:** `.kennisbank-version` keys (`tag`, `commit`, `installed_at`), `KENNISBANK_VAULT`, `KENNISBANK_REPO`, `TILING_THRESHOLD_ERROR/REVIEW`, and the deploy-map paths are used identically across all tasks and both skills.
