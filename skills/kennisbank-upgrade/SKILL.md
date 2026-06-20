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
