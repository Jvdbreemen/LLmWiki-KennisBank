---
id: TASK-157
title: >-
  Everything in the code speaks English: translate every Dutch string, comment
  and prompt
status: In Progress
assignee: []
created_date: '2026-08-13 20:21'
labels:
  - docs
  - policy
  - refactor
  - llm
dependencies: []
priority: high
ordinal: 151700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The repository language policy is stated at the top of both AGENTS.md and CLAUDE.md: all documentation, comments, commit messages and PR descriptions are English by default, with Dutch permitted only as an explicitly named variant such as `README.nl.md`. The code has never actually met it. Most of the memory layer — `_memory.py`, `_reconcile.py`, `_maintenance.py`, `memory-sweep.py`, `memory-doctor.py` and many others — is Dutch end to end, and so are the LLM prompts inside them.

The Copilot review on PR #116 flagged two new files for exactly this, which is what makes it worth doing properly rather than one file at a time: the policy is either true of the codebase or it is decoration.

**One category needs care rather than translation, and it is the reason this is not a find-and-replace.** The prompts are not comments; they are inputs to a model, and the vault they operate on is Dutch. The measured NOOP improvement on the reconcile prompt (25% to 0% on unrelated pairs) was obtained with a Dutch prompt against Dutch memories. Translating a prompt changes what was measured, so every translated prompt is re-measured against the same pairs, and any regression is reported rather than absorbed.

**Test fixtures that encode a language-specific bug stay in Dutch, with an English comment saying why.** `test_volatility.py` pins that 'off' hides inside "officieel" and 'uit' inside "uitgebreid"; translating those bodies deletes the reason the test exists. These are data, not documentation.

Approach, deliberately incremental because a large diff makes a regression expensive to locate:

1. Inventory every script and list every Dutch string, comment and docstring.
2. Inventory the prompts separately, because they carry behavioural risk.
3. Translate in small batches, running the affected tests after each.
4. Re-measure every translated prompt against its recorded baseline.
5. A final sweep proving no Dutch remains outside the named exceptions.

A checkpoint tag is created before any of this, so the whole thing can be undone in one command.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A complete inventory of Dutch strings, comments and docstrings per script exists before any translation starts
- [ ] #2 Prompts are inventoried separately, because translating them changes model behaviour rather than only readability
- [ ] #3 Translation happens in small batches with the affected tests run after each one
- [ ] #4 Every translated prompt is re-measured against its recorded baseline and any regression is reported, not absorbed
- [ ] #5 User-facing CLI output is translated too, not only comments
- [ ] #6 Test fixtures that encode a Dutch-language bug stay Dutch, with an English comment stating why
- [ ] #7 A final scan shows no Dutch remains outside the explicitly named exceptions
- [ ] #8 python -m pytest tests -q is green
- [ ] #9 A checkpoint tag exists from before the first translation commit
<!-- AC:END -->
