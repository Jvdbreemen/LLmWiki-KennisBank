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
| `$HOME/.claude/skills/<name>/SKILL.md` (each skill) | `skills/<name>/SKILL.md` |

## Scope filter (NEVER contribute these)
`CLAUDE.md`, `categories.json`, `embeddings-cache.json`, any `*.bak`, the vault
content directories `00-*`..`08-*`, and `.kennisbank-version`.

For skills: only skills whose `skills/<name>/SKILL.md` path exists in the BASE
commit are eligible; locally-installed skills with no upstream repo counterpart
are excluded regardless of local edits.

## Procedure
1. Read `$VAULT/.claude/.kennisbank-version` -> `BASE` (`tag`). If absent, use
   `BASE=$(git -C "$REPO" tag --sort=-v:refname | grep '^v[0-9]' | head -1)`.
2. `git -C "$REPO" fetch --tags --quiet`.
3. For each deployed location in the reverse deploy map, CRLF-agnostic diff the
   deployed file against `BASE`'s version of the mapped repo path:
   `diff --strip-trailing-cr <(git -C "$REPO" show "$BASE:<repopath>") "<deployed>"`.
   For skills, iterate over every installed skill under
   `$HOME/.claude/skills/*/SKILL.md` and for each resolve its name and check
   whether the repo counterpart exists at BASE:
   `git -C "$REPO" ls-tree "$BASE" "skills/<name>/SKILL.md"`.
   If this exits non-zero (the skill has no counterpart in the repo at BASE),
   SKIP it silently — it is a locally-installed personal skill with no upstream
   repo counterpart and is NEVER a contribute candidate. The "missing BASE =
   added" rule applies only to scripts, templates, and commands — NOT to skills.
   For skills that do exist in the repo at BASE, diff against
   `skills/<name>/SKILL.md`; if `git show "$BASE:skills/<name>/SKILL.md"` exits
   non-zero for any other reason, treat the skill as new/added. Collect the
   changed and added repo paths, applying the scope filter.
4. If nothing qualifies, report "no contributable changes" and stop.
5. Show the user the candidate file list with per-file diffs. Let them choose
   which files to include (default: all).
6. Detect the default branch and create a branch off it:
   ```
   DEFAULT=$(git -C "$REPO" symbolic-ref --quiet refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@')
   DEFAULT=${DEFAULT:-main}
   git -C "$REPO" checkout -b "contrib/<slug>" "$DEFAULT"
   ```
   (slug from a short user-supplied description).
7. For each selected file, copy the deployed version into the repo at its mapped
   repo path. `git -C "$REPO" add` those paths.
8. Commit with a descriptive message summarizing the change.
9. `git -C "$REPO" push -u origin "contrib/<slug>"`.
10. `gh pr create --repo <upstream> --base "$DEFAULT" --head "contrib/<slug>"` with a
    title and body describing the improvement. Report the PR URL.

## Dry-run
If invoked with `--dry-run`, perform steps 1-5 and print the branch name and the
files that would be committed, but do not create the branch, commit, push, or PR.
