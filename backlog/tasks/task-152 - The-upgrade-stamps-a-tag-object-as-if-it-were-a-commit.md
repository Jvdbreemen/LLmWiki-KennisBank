---
id: TASK-152
title: The upgrade stamps a tag object as if it were a commit
status: In Progress
assignee: []
created_date: '2026-08-13 05:18'
labels:
  - bug
  - release
  - tooling
dependencies: []
references:
  - skills/kennisbank-upgrade/SKILL.md
priority: medium
ordinal: 146700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Step 10 of `skills/kennisbank-upgrade/SKILL.md` writes the version stamp as:

```
{"tag":"$LATEST","commit":"<git rev-parse --short $LATEST>","installed_at":"..."}
```

For an **annotated** tag, `git rev-parse v0.29.0` returns the SHA of the tag object, not of the commit it points at. Every tag in this repository is annotated (`git cat-file -t v0.29.0` -> `tag`), so this fires on every upgrade, every time.

Observed on two consecutive upgrades:

| | stamp written | tag object | actual commit |
| --- | --- | --- | --- |
| v0.28.0 | `80b0285` | `80b0285` | `86eb290` |
| v0.29.0 | `1506a9c` | `1506a9c` | `1cb608d` |

Why it matters, given that this repository is careful about exactly this class of mistake elsewhere: the release procedure refuses to tag a branch tip and verifies that `git rev-list -n1 <tag>` equals the merged SHA, precisely so that a version reference points at code someone can find. The upgrade then records a reference that appears in no branch and matches no line of `git log`. Some git commands peel the tag transparently (`git merge-base --is-ancestor` says yes), which is what let it pass unnoticed: it looks right until something compares it to a commit SHA, or a human tries to match it against the history.

Fix: `git rev-parse --short "$LATEST^{}"`. The `^{}` suffix peels an annotated tag to its commit and is a no-op on a lightweight tag, so it is correct either way.

Two places need it, because the deployed copy is what actually runs when the skill is invoked:

- `skills/kennisbank-upgrade/SKILL.md` in the repo
- `~/.claude/skills/kennisbank-upgrade/SKILL.md`, otherwise the next upgrade still follows the old instruction (setup.sh refreshes skills in step 9, but the agent has already loaded the instructions it is executing)

The stamp on this machine has been corrected by hand to `1cb608d`; older vaults still carry a tag-object SHA and will self-correct on their next upgrade.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The upgrade skill peels the tag with ^{} so the stamp records a commit that exists in the history
- [ ] #2 Both the repo copy and the deployed copy of the skill carry the fix
- [ ] #3 A note in the skill says why, so the next editor does not simplify it back to the shorter form
<!-- AC:END -->
