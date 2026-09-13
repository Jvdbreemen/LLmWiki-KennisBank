# Projection build capability evidence — 2026-09-08

Scope: TASK-239, feature branch `codex/source-grounded-experience-production`.
No ADR transition, release, ordinary-recall change, or owner-canary value claim.

## Defect and test-first proof

The public `rebuild-experience.py` command accepted a selected vault without
checking `experience_projection`. A read-only probe with a mocked builder
observed `experience_projection=false`, `builder_called=true`, and exit 0.
No real projection was written by that probe.

Before implementation, four new regression tests failed: the command returned
`ok` instead of `disabled`, or exit 0 instead of `invalid` for absent vault
configuration. Two enabled-path controls passed. This is the recorded red
phase: **4 failed, 2 passed in 1.42s**.

## Repair and coverage

The command requires an explicit `--vault` or non-empty `KENNISBANK_VAULT`,
checks the selected vault's capability before loading optional embeddings or
the builder, and returns a content-free `disabled` response with no mutation
when permission is absent. Custom database paths and an enabled ambient vault
cannot grant authority to a disabled selected vault. Internal deterministic
builder functions remain available to fixture tests and explicit library users;
they are not independent deployed CLI entrypoints.

Coverage includes missing/false/string-false/corrupt/legacy-only settings,
selected versus ambient vaults, missing vault configuration, and the enabled
split-store lexical path. Real subprocess tests also prove that disabled
rebuilds preserve existing files byte-for-byte and enabled rebuilds produce a
lexical projection from a temporary canonical ledger.

Focused capture/review/rebuild/projection/policy/docs run:
**41 passed in 5.08s**. Current full-suite evidence is still required before
closing the task's final acceptance criterion.

## Private owner-vault shadow proof

After explicit owner approval of one bounded candidate, all seven exact source
references were revalidated and one content-hash-bound accepted review was
appended. No lesson text or outcome interpretation was changed by approval.

The repaired CLI first returned `disabled` in the real configured vault with
`mutated=false`. The settings file was backed up before enabling only the
projection-build capability. A lexical-only build then published one reviewed
experience and excluded forty unreviewed candidates. There were no failed
embeddings or model calls. A fast doctor reported quick SQLite integrity OK for
ledger and projection, one validated/accepted record, and both explicit read
routes still disabled. It explicitly did not perform deep source checks;
the seven-ref check above is separate evidence.

At this snapshot the ledger contained 41 events, 41 outcomes, and one review.
Counts may increase through normal shadow capture. The source canary remains
10/10 and the natural explicit-experience canary remains 0/20. This is corpus
preparation and mechanism proof, not a new natural recall or product-value pass.
Private candidate text, identities, review, source refs, and settings backup
remain only in the configured vault.
