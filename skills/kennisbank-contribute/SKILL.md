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
content directories `00-*`..`08-*`, `.kennisbank-version` (release-tag-stamp), and
`.kennisbank-schema-version` (migratie-schema-stamp). Beide stempels zijn lokaal
gegenereerd en nooit upstream-contributabel.

For skills: only skills whose `skills/<name>/SKILL.md` path exists in the repo
at BASE — verified via `git cat-file -e "$BASE:skills/<name>/SKILL.md"` (exits
0) — are eligible. Locally-installed skills with no upstream repo counterpart
(probe exits non-zero) are excluded regardless of local edits and must NEVER
be contributed.

### Localization auto-skip (deploy-path / vault-name rewrites)

Deployment rewrites the portable `~/KennisBank` path and the `KennisBank` vault
name in the upstream files to the LOCAL vault's absolute path and display name
(e.g. `~/KennisBank/01-raw` -> `D:/Users/Robert/.../Kluis/01-raw`,
`KennisBank vault` -> `Kluis vault`). A file whose ONLY difference from BASE is
those rewrites is **deploy-localization, never a contributable edit** — pushing
it upstream would hard-code one machine's absolute path and vault name and break
portability for every other user. The tell is a symmetric `+N -N` diffstat (pure
line replacements, no net add/remove).

Before flagging a file changed in step 3, normalize those rewrites back to the
portable form and re-diff. If the normalized diff is empty, SKIP the file:

```bash
VAULT_NAME=$(basename "$VAULT")               # e.g. "Kluis"
norm() { sed -e "s#${VAULT}#~/KennisBank#g" -e "s#\\b${VAULT_NAME}\\b#KennisBank#g" "$1"; }
if diff --strip-trailing-cr <(git -C "$REPO" show "$BASE:<repopath>") <(norm "<deployed>") >/dev/null 2>&1; then
    : # localization-only -> SKIP, not a candidate
else
    : # real change remains after normalization -> keep as candidate
fi
```

Only the residual, normalization-surviving changes are real candidates.

## Procedure
1. Read `$VAULT/.claude/.kennisbank-version` -> `BASE` (`tag`). If absent, use
   `BASE=$(git -C "$REPO" tag --sort=-v:refname | grep '^v[0-9]' | head -1)`.
2. `git -C "$REPO" fetch --tags --quiet`.
3. For each deployed location in the reverse deploy map, CRLF-agnostic diff the
   deployed file against `BASE`'s version of the mapped repo path:
   `diff --strip-trailing-cr <(git -C "$REPO" show "$BASE:<repopath>") "<deployed>"`.
   Apply the **Localization auto-skip** above first: if the only difference is the
   deploy path/vault-name rewrite, the file is NOT a candidate.
   For skills, iterate over every installed skill under
   `$HOME/.claude/skills/*/SKILL.md` and for each resolve its name and check
   whether the repo counterpart exists at BASE:
   `git -C "$REPO" cat-file -e "$BASE:skills/<name>/SKILL.md"`.
   If this exits non-zero (exit 128 when the path is absent), SKIP it silently
   — it is a locally-installed personal skill with no upstream repo counterpart
   and is NEVER a contribute candidate. A skill absent at BASE must NEVER be
   routed to "added"; the "missing BASE = added" rule applies ONLY to scripts,
   templates, and commands — NOT to skills.
   For skills confirmed to exist at BASE (probe exits 0), diff against
   `skills/<name>/SKILL.md` at that ref. Collect changed repo paths, applying
   the scope filter.
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

## Gotcha: contribute work goes on a branch, never the default branch first

This skill assumes the tooling edits live ONLY in the deployed files (step 7 copies
the deployed version into the repo). If you (or a prior session) already committed
them to local `$DEFAULT` (e.g. straight to `main`), step 6's `checkout -b contrib/<slug>
$DEFAULT` branches off a tip that ALREADY contains them, so a same-tip PR has no diff
to show, and local `$DEFAULT` is left ahead of origin with PR-bound commits that a
stray `git push` would land on the default branch, bypassing review.

If you find commits already on local `$DEFAULT` that belong in the PR: move them to the
branch and reset the default branch back to origin before pushing:
```
git -C "$REPO" branch "contrib/<slug>"                 # branch keeps the commits at HEAD
git -C "$REPO" checkout "$DEFAULT" && git -C "$REPO" reset --hard "origin/$DEFAULT"
git -C "$REPO" checkout "contrib/<slug>"               # PR-bound work now lives only here
```
`gh pr create --base "$DEFAULT"` compares against origin/$DEFAULT, so the PR then shows
exactly your changes. Rule: never commit contribute work to the default branch.

## Dry-run
If invoked with `--dry-run`, perform steps 1-5 and print the branch name and the
files that would be committed, but do not create the branch, commit, push, or PR.
