---
id: TASK-127
title: Remove the cozempic claim from /sessiestart
status: Done
assignee: []
created_date: '2026-08-02 18:02'
updated_date: '2026-08-02 18:03'
labels:
  - docs
dependencies: []
priority: low
ordinal: 122700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`commands/sessiestart.md:26` tells the user that the context layers complement "cozempic context hygiene". Cozempic is a third-party tool that a user may not have — and after removing it from this machine, the line describes a relationship to something that is not there. A deployed command should not assert the presence of tooling it does not ship or check for.

This cannot be fixed in the vault: the deployed copy comes from the repo, so removing the line locally is drift that the next `setup.sh` reverts.

Deliberately out of scope:

- `docs/superpowers/plans/2026-06-21-vault-onderhoud-laag.md` and the matching spec mention cozempic in their R8 rationale. Those are dated design documents recording what was decided in June; rewriting them would falsify the record.
- `scripts/build-karpathy-index.py:94` carries `cozempic` in a tag-to-category routing set. No vault article uses that tag, so it is dead routing rather than a wrong claim. Harmless either way; not worth coupling to this fix.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 commands/sessiestart.md no longer claims a relationship to cozempic
- [x] #2 The surrounding context-layer explanation still reads as a whole
- [x] #3 Documentation test subset green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Parked before the edit: the session redirected to TASK-126. Nothing was changed in commands/sessiestart.md yet; the analysis in the description stands.
<!-- SECTION:NOTES:END -->


## Final Summary

Removed the sentence from `commands/sessiestart.md`; the context-layer explanation now closes with
what the levels cost the reader instead of what they complement. A deployed command should not
assert a relationship to third-party tooling it neither ships nor checks for.

Left in place on purpose: `scripts/build-karpathy-index.py` still routes a `cozempic` tag to the
Claude Code category. No vault article carries that tag, so it is dead routing rather than a wrong
claim, and removing it would only matter if someone had tagged an article that way. The June design
documents under `docs/superpowers/` keep their references: they record what was decided at the time,
and rewriting them would falsify the record.
