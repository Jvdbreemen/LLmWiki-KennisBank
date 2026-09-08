# Canonical ledger no-clobber migration — 2026-09-08

Scope: TASK-242. Discovery occurred during supported-deployment preflight.
The owner vault has an existing canonical ledger but **no legacy mixed
experience database**, so this path was not exercised on private data and no
owner event, outcome or review was lost or modified.

## Reproduction

The former migration staged only the legacy rows, then called `os.replace`
against the canonical ledger. That could erase existing owner capture/reviews,
including a first capture occurring after the initial target-existence check.
Its shared staging filename could also delete another operation's stage.

Three test-first temporary-vault fixtures reproduced those failures:
**three failed, three passed in 1.30 seconds**. Two migrations incorrectly
returned `ok` after replacing the real SQLite target. The interruption fixture
also proved that a foreign staging file had been removed.

## Repair

- A pre-existing target without this exact legacy migration stamp is preserved
  byte-for-byte. Dry-run reports the conflict; apply returns a content-free
  `existing_ledger_requires_review` failure. No automatic history merge or
  implicit acceptance of old reviews is invented.
- A new ledger is built in an exclusively created operation-specific stage.
  Publication uses an atomic no-clobber hard link on the same filesystem,
  followed by cleanup of only this operation's stage. Concurrent first capture
  therefore wins safely instead of being overwritten.
- Unsupported hard links fail safely; there is no replacement fallback.
  Legacy backup, normal first migration and exact idempotent replay remain
  covered. Interrupted new-target migration publishes nothing and retains both
  the original and its verified backup.

Focused migration, versioned-migration, store and projection-boundary tests:
**46 passed in 3.48 seconds**. Independent unittest discovery found and passed
all eight migration tests in **0.487 seconds**. `git diff --check` passed.
Full-suite proof for the amended runtime remains pending at this checkpoint.

This is upgrade/data-preservation evidence, not a new natural experience recall.
The natural canary remains a separate owner-reviewed gate; no private source
content or identifiers are included here.
