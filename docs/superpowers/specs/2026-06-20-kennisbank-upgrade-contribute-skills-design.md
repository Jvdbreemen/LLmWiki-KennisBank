# Design: kennisbank-upgrade & kennisbank-contribute skills

Date: 2026-06-20
Status: Approved (design), pending implementation plan
Target repo: LLmWiki-KennisBank (upstream: Jvdbreemen/LLmWiki-KennisBank)

## Problem

The kennisbank tooling (scripts, templates, commands, autoresearch skill) is
distributed by `setup.sh`, which copies files into a vault and into the global
`~/.claude/` tree. There is no mechanism to:

1. Detect whether a deployed vault is behind the latest released version and
   upgrade it safely.
2. Take improvements made locally in a deployed vault and contribute them back
   upstream as a pull request.

Both are currently manual, error-prone, and depend on remembering file-mapping
details. This session surfaced two concrete failure modes the design must fix:

- `setup.sh` only copies `scripts/*.py`, so `scripts/doctor.sh` is never
  deployed by setup (it reached vaults by ad-hoc manual copy).
- Naive diffing of deployed files vs repo files produces false positives from
  CRLF (deployed, Windows checkout) vs LF (`git show`) line endings.

## Decisions (locked)

- **Cross-platform: every script and test must work on macOS, Linux, and
  Windows (Git Bash).** Tests pass on all three. Paths handed to a bash
  subprocess are converted to Git Bash POSIX form (`/c/...`) on Windows.
  `setup.sh` honors `KENNISBANK_VAULT` like the rest of the script layer.
- Upgrade source of truth: **latest release tag** (official tags only; main is
  ignored for upgrades).
- **Cut v0.6.0** so the unreleased qwen3/threshold/doctor fixes (currently past
  the v0.5.0 tag on main) are captured by tag-based upgrade.
- Contribute scope: **scripts + templates + commands + every skill under skills/*/**
  Personal vault content and config are excluded.
- **Two separate skills**: `kennisbank-upgrade` and `kennisbank-contribute`.

## Shared foundations

### Deploy map (single source of truth for both skills)

| Repo source                      | Deploy destination               | Notes                          |
|----------------------------------|----------------------------------|--------------------------------|
| `scripts/*.py`                   | `$VAULT/.claude/scripts/`        | executable                     |
| `scripts/*.sh`                   | `$VAULT/.claude/scripts/`        | NEW — closes the doctor.sh gap |
| `templates/*.md`                 | `$VAULT/04-templates/`           |                                |
| `commands/*.md`                  | `~/.claude/commands/`            | global                         |
| `skills/*/SKILL.md` (each skill dir) | `~/.claude/skills/<name>/`   | global                         |
| `CLAUDE.md.template`             | `$VAULT/CLAUDE.md`               | personalized — never upstream  |

### Path resolution

- Vault: `KENNISBANK_VAULT` env var, fallback `$HOME/KennisBank`.
- Repo clone: known path; if not found, the skill asks the user.

### Version stamp

- File: `$VAULT/.claude/.kennisbank-version` (JSON: `tag`, `commit`, `installed_at`).
- Written on every successful upgrade. Absent = legacy/unknown (treat as
  pre-v0.6.0; warn).

### CRLF-agnostic diffing

All file comparisons use CRLF-insensitive diff (`diff --strip-trailing-cr` or
`git diff --ignore-cr-at-eol`). Never compare `git show` (LF) against a deployed
file (CRLF) without normalization.

## Skill 1: kennisbank-upgrade (upstream tag -> vault)

1. Resolve vault + repo clone.
2. `git -C <repo> fetch --tags --quiet`. Latest tag via
   `git tag --sort=-v:refname | head -1`; cross-check `gh release view`.
3. Read stamp -> installed tag (or "unknown"). Semver-compare with latest.
   Up to date -> report and exit.
4. Show CHANGELOG section(s) between installed..latest.
5. Drift guard: CRLF-agnostic diff of deployed tooling vs the installed tag's
   files. If local edits exist -> warn, point to `kennisbank-contribute`, ask
   whether to proceed (edits will be preserved only in the backup).
6. Confirm. Back up current deploy dirs (`scripts` ->
   `scripts.pre-<oldtag>.bak`, matching existing convention; templates likewise).
7. Check out the latest tag (detached) in the repo clone. Copy deployables per
   the deploy map: `scripts/*.py` + `scripts/*.sh`, templates, commands, skill.
   `CLAUDE.md` is left untouched.
8. Re-stamp `.kennisbank-version`.
9. Run `doctor.sh`; report PASS count.

Flags: `--dry-run` (show planned changes, no writes).

## Skill 2: kennisbank-contribute (vault -> upstream PR)

1. Resolve vault + repo clone.
2. Baseline = installed tag (stamp), else latest tag.
3. CRLF-agnostic diff of deployed tooling vs baseline across all four deploy
   locations (vault `.claude/scripts/`, vault `04-templates/`,
   `~/.claude/commands/`, `~/.claude/skills/*/`). Build
   changed/added list.
4. Scope filter. Include: scripts, templates, commands, every skill (skills/*/SKILL.md).
   Exclude: `CLAUDE.md`, `categories.json`, `embeddings-cache.json`, `*.bak`,
   vault content dirs (`00-*`..`08-*`), `.kennisbank-version`.
5. Present the candidate diff; user selects which files to include.
6. In the repo clone: branch `contrib/<slug>` off main; map vault paths back to
   repo paths via the deploy map; copy; commit; push;
   `gh pr create` against the upstream main.
7. Report the PR URL.

Flags: `--dry-run` (build branch/diff locally, no push/PR).

## Supporting one-off changes (land in v0.6.0)

- `setup.sh`: also copy `scripts/*.sh` (close the doctor.sh gap), so fresh
  installs match deployed reality.
- Cut v0.6.0: update CHANGELOG `[Unreleased]` -> `[0.6.0]`, commit,
  `git tag v0.6.0`, push tag, `gh release create v0.6.0`.
- Stamp the current Kluis deploy as `v0.6.0` (it already runs that content).

## Skill placement

- Repo: `skills/kennisbank-upgrade/SKILL.md`,
  `skills/kennisbank-contribute/SKILL.md`.
- Installed into `~/.claude/skills/` (globally invocable); `setup.sh` extended
  to copy them alongside `autoresearch`.

## Testing

- `--dry-run` on both skills.
- `doctor.sh` as the post-upgrade verification gate.
- Manual round-trip: bump a script in the vault -> `kennisbank-contribute`
  produces a PR; roll a deploy back to an older tag ->
  `kennisbank-upgrade` catches it up.

## Out of scope (YAGNI)

- Auto-update daemon / scheduled checks.
- Multi-vault support.
- A dedicated rollback command (`.bak` backups + git tags cover recovery).
