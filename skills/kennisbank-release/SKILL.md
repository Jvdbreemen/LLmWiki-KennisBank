---
name: kennisbank-release
description: >-
  Release a new LLmWiki-KennisBank version end to end. Proposes the next
  semantic version from the commit delta, writes the changelog section and
  compare links, bumps both README highlight sections, runs the gate, opens a
  pull request upstream, processes the Copilot review, merges, verifies the
  merge landed, tags that commit and publishes the GitHub release. Triggers:
  /kennisbank-release, "release kennisbank", "cut a kennisbank release".
---

# Kennisbank Release

Codifies the release procedure that has been done by hand since v0.16.0. Every
step below exists because a manual release got it wrong at least once.

## Ground rules

- **Never tag a branch tip.** Tag only a SHA you have confirmed is on
  `origin/main` after the merge. A tag placed on the assumption that a merge
  landed points at different code than main contains.
- **Never skip the Copilot review.** It runs automatically on every pull
  request and its comments are *not* visible through `gh pr view`. On the
  v0.20.0 release all five of its comments were correct, one of them exposing a
  hole in a guard written in that same pull request. Green CI does not cover
  this: CI tests behaviour, not whether a guard covers what it claims to.
- **Fail closed on a red gate.** Stop and report; never release past a failure.
- `--dry-run` prints the planned version, changelog section and actions, and
  writes nothing.

## Step 0 — refuse to run in the wrong place

Confirm the working directory is a clone of this repository (`git remote -v`
contains `LLmWiki-KennisBank`) and that the tree is clean. A deployed vault copy
has scripts but no git history; releasing from there is meaningless.

Confirm the remotes: `origin` is the upstream (Jvdbreemen), `fork` is the user's
own (rvdbreemen). Push branches to `fork`, open pull requests against `origin`.

## Step 1 — propose the version

```bash
LAST=$(git tag --sort=-v:refname | grep '^v[0-9]' | head -1)
git log --oneline "$LAST"..HEAD
```

Classify from the delta, then state the proposal *and the reason*, and ask for
confirmation:

- only `fix:` and docs → patch
- any `feat:`, a schema change, a dropped table, a changed output contract, or a
  new dependency → minor
- a breaking change to the CLI, commands or vault layout → major

Do not propose a major to signal maturity. Semver-major means breaking.

## Step 2 — changelog

Add a dated `## [X.Y.Z]` section in Keep-a-Changelog shape, and update the two
compare links at the bottom: point `[Unreleased]` at the new tag and add a line
for the new version.

Write what a reader needs, not a commit dump: what broke, how it manifested, and
what changes for them. Behaviour changes that a user could notice — a changed
field in MCP output, tables dropped on their vault, a new deploy glob — go in
explicitly.

## Step 3 — README highlights, both languages

Update **`README.md`** (`## Feature highlights (vX.Y.Z)` and `### New in vX.Y.Z`)
and **`README.nl.md`** (`## Functie-highlights (vX.Y.Z)` and `### Nieuw in
vX.Y.Z`). Both, in the same edit.

The Dutch and English variants are co-edited translations, not forks. A commit
that touches only one of them is how stale claims survive: `e7b014d` corrected
just the English paragraph and left the Dutch on superseded text for weeks.

## Step 4 — gate

```bash
python3 -m pytest tests -q
```

Steps 2 and 3 are one unit with this step: do not run the suite between them, or
the documentation-consistency lint fails by construction on a half-updated tree.

Stop on any failure. Report the failing test; do not continue.

## Step 5 — branch, push, pull request

Commit the release documentation, push the branch to `fork`, and open a pull
request against `origin/main` describing the load-bearing changes.

Choose the merge method deliberately. This repository uses both: PRs #41–#45 are
merge commits, #48–#53 squashes. Prefer a **merge commit** when the branch
carries one commit per task and individual reverts have value — a release that
drops database tables is exactly that case. Prefer squash for a series of small
commits that are one logical change.

## Step 6 — CI and the Copilot review

Wait for both.

```bash
gh pr checks <n> --repo Jvdbreemen/LLmWiki-KennisBank --watch
gh api repos/Jvdbreemen/LLmWiki-KennisBank/pulls/<n>/comments \
  --jq '.[] | "=== \(.path):\(.line // .original_line) [\(.user.login)]\n\(.body)\n"'
gh api repos/Jvdbreemen/LLmWiki-KennisBank/pulls/<n>/reviews \
  --jq '.[] | "[\(.user.login)] \(.state)\n\(.body)"'
```

Treat every comment as possibly correct and check it against the code or a
measurement. Do not dismiss on instinct, and do not apply on instinct either.
Fix what holds in a follow-up commit on the same branch, and say why for
anything you leave.

## Step 7 — merge, then verify

```bash
gh pr merge <n> --repo Jvdbreemen/LLmWiki-KennisBank --merge
git fetch origin
git log --oneline origin/main -3
```

Confirm the merge commit is present on `origin/main` before going further.

## Step 8 — tag the verified commit

```bash
SHA=$(git rev-parse origin/main)
git tag -a vX.Y.Z "$SHA" -m "…"
git push origin vX.Y.Z
git rev-list -n1 vX.Y.Z          # must equal $SHA
```

## Step 9 — publish

Extract the changelog section to a file **with explicit UTF-8 encoding and an
absolute path**, then publish and verify the body is not empty:

```bash
gh release create vX.Y.Z --repo Jvdbreemen/LLmWiki-KennisBank \
  --title "…" --notes-file "<absolute path>" --verify-tag
gh release view vX.Y.Z --repo Jvdbreemen/LLmWiki-KennisBank --json body -q '.body | length'
```

Both halves of that verification exist because both failed once. A generator
script died on cp1252 and wrote zero bytes, and `gh` published the empty file
without complaint. Then `--notes-file /tmp/...` read a different file than
Python had written: Python's `/tmp` on Windows is `C:\tmp\`, while Git Bash maps
it elsewhere.

## Step 10 — close out

Set the release task and every task in the release to `Done`, commit that, and
push. Then offer to upgrade the user's vault from the new tag with
`/kennisbank-upgrade`.

Note on timing: the suite takes roughly twenty minutes on a Windows development
machine and about two and a half on the Linux CI runner. Base any timeout
margin on the runner measurement; use the local one only to decide whether to
wait or work on something else meanwhile.
