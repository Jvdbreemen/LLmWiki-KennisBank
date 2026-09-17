---
id: "ADR-012"
title: "Research and evaluation tools live in scripts/dev/ and are not deployed"
status: "Accepted"
date: "2026-09-17"
binding: true
gate: null
documents_shipped: false
verified_in: ["TASK-252"]
supersedes: []
superseded_by: null
format: "madr"
topics:
  - deploy
  - evaluation
  - migrations
---

# ADR-012: Research and evaluation tools live in scripts/dev/ and are not deployed

## Status

Accepted, 2026-09-17.

## Status History

```yaml
status_history:
  - date: 2026-09-17
    status: Proposed
    changed_by: Claude
    reason: Owner asked whether the evaluation scripts can be dropped before release or split into a separate project
    changed_via: manual
  - date: 2026-09-17
    status: Accepted
    changed_by: Robert van den Breemen
    reason: "Accepted by the user in session 2026-09-17 (explicit: 'Accept adr-012') after the sandbox upgrade evidence"
    changed_via: manual
```

## Context and Problem Statement

LLmWiki-KennisBank is a distribution: `setup.sh` copies `scripts/*.py`,
`scripts/*.sh` and `scripts/*.json` into `$VAULT/.claude/scripts/`, and the
`kennisbank-upgrade` skill deploys through the same script. Every research
harness written to decide a retrieval or experience question therefore landed
in every vault, next to the code that runs there. On 2026-09-17 that was 28 of
155 deployed files, none of them called by a command, a skill, a hook,
`doctor.sh` or runtime code.

Two constraints shape the answer. The evidence rule (TASK-86/87) says a
retrieval feature is activated only after a measured A/B, so the tools that
produce that measurement must stay usable. And several harnesses import the
runtime modules they measure (`_experience`, `_rank`, `_source_recall`,
`kb-recall.py`), so the measuring code and the measured code must not drift
apart.

## Considered Options

* Move the tools to `scripts/dev/` in the same repository; prune old copies
  with a schema migration.
* Split them into a separate evaluation repository.
* Delete them.
* Keep deploying everything.

## Decision Outcome

Chosen option: **`scripts/dev/` in the same repository, with a pruning
migration**. The deploy glob does not recurse, so no deploy code changes. The
tools run from a checkout and import the shipped modules of that same commit.
Evaluation data stays where it already is: in the vault and in the private
eval-set repository, never here.

A tool stays in `scripts/` when anything that ships calls it: a
`/kennisbank:*` command, a skill, a hook, `doctor.sh`, runtime code, or a
user-facing section of the README. `kb-eval.py` is the main example.

`setup.sh` copies and never prunes, so a vault installed before the move would
keep its copies. Migration 0.39.0 (`dev-scripts-uit-de-vault`) deletes the
files named in `_migrations.RETIRED_SCRIPTS`, and only those.

### Consequences

* Good, because a vault carries only what runs in it.
* Good, because the A/B tools remain one checkout away and cannot drift from
  the code they measure.
* Bad, because a dev tool must add the shipped `scripts/` to its import path
  and must compute the repository root as two levels up. The move showed that
  "parent of this file" silently narrowed a private-data boundary to
  `scripts/`.
* Bad, because the retired list is manual. A test keeps it equal to
  `scripts/dev/` plus the deleted one-offs and disjoint from `scripts/`.

## Decision Contract

### Must

* Anything a shipped command, skill, hook, `doctor.sh` or runtime module calls
  lives in `scripts/`.
* A file added to `scripts/dev/` is added to `_migrations.RETIRED_SCRIPTS` if an
  earlier release shipped it.
* A dev tool that guards "outside the repository" derives the repository as
  `Path(__file__).resolve().parents[2]`.

### Must Not

* The migration must not delete a file that `scripts/` still ships.
* Private evaluation sets must not be committed to this repository.

### Verification

* `tests/test_migrations.py::DevScriptsLeaveTheVaultTest`
* `tests/test_source_sparse_eval_cli.py::SourceSparseEvalCliTest::test_private_boundary_rejects_repository_paths`
* Sandbox run on 2026-09-17: install from v0.38.0 HEAD, then `setup.sh --yes`
  from this change. 155 deployed files became 127, all 28 retired names were
  gone, `kb-eval.py`, `doctor.sh`, `memory-doctor.py` and `kb-retrieve.py`
  remained, and the stamp moved to 0.39.0.

## Related Decisions

* ADR-008: removed the scene layer and introduced the prune-by-migration
  pattern this record reuses.
