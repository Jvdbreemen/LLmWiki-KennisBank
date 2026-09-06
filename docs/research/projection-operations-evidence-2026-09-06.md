# Projection operations evidence — 2026-09-06

## Decision scope

This packet covers operational readiness for the explicit source-recall and
reviewed experience-recall projections. It does not claim that either layer has
passed the frozen product-value gate, and it does not enable any feature flag.
All live checks used the configured local `KENNISBANK_VAULT`; no hosted model,
remote database, prompt, passage, lesson, embedding, full SourceRef, or absolute
personal path was recorded in telemetry or copied into this document.

## Sanitized live-vault preflight

The migration preflight returned:

| Field | Result |
|---|---:|
| status | `no_legacy` |
| mutated | `false` |
| legacy files / rows | `0 / 0` |
| ledger / projection schema | absent / absent |
| estimated migration bytes | `0` |
| four production feature flags | all `false` |
| backup target | not applicable because no legacy store exists |

No migration was applied to the live vault. Temporary-vault tests cover the
ready, dry-run, success, interrupted, rerun, and setup-migration paths.

## Sanitized live-vault doctor

The default read-only doctor completed in 299.3 seconds. Its slow runtime is a
real operational cost: it performs SQLite `quick_check` and hashes current raw
sources to detect drift. The optional `--deep` mode performs the more expensive
full `integrity_check`; neither belongs on the prompt hot path.

| Field | Result |
|---|---:|
| schema | `2` |
| source / experience route | disabled / disabled |
| forbidden legacy flags | `0` |
| source status / integrity | ready / ok (`quick`) |
| source documents / chunks | 16,286 / 490,317 |
| exact provenance coverage | 100% |
| retrieval backend | `sqlite_fts5` |
| stale / missing / redacted source files | 0 / 0 / 0 |
| vector-like source tables | 0 |
| experience ledger / projection | missing / missing |
| mutated | `false` |

The absence of live experience stores is expected and means the later canary
must first create reviewed ledger evidence; it is not evidence of product value.

## Recovery and lifecycle proof

- Migration copies canonical rows to a staged ledger, verifies SQLite integrity
  and row counts, records the legacy digest, atomically publishes, preserves the
  original store, and creates a content-hash-named backup. Reruns are idempotent.
- Failure injection before migration swap and during source/experience rebuild
  leaves the previous good database byte-for-byte intact.
- Source rebuild tests cover bounded progress, deletion, redaction, changed
  hashes, unreadable input, provenance offsets, and vector-free FTS publication.
- The projection doctor resolves current SourceRefs rather than trusting stored
  evidence labels, so changed hashes, missing files, and redaction are counted.
- Retracted and superseded experiences remain in the retained ledger audit trail
  but are excluded from public recall. V1 performs no automatic canonical
  retention deletion.
- Embedding outage publishes a complete, explicitly labelled lexical projection
  instead of contacting a hosted fallback or publishing a partial hybrid index.

## Privacy field audit

`projection_metrics` accepts and stores only day, layer, route, status, call
count, hit count, total latency, and maximum latency. Values are allowlisted and
bounded. Its function signature cannot accept content fields. Existing exposure
logging calls from the two gateways receive an empty query and no source path or
full SourceRef. Static tests guard both call sites.

## Verification

The TASK-234 suite passed:

```text
75 passed in 9.44s
2 setup deployment tests passed in 71.17s
3 focused doctor tests passed in 0.68s
```

The 75-test set covers migration, doctor, privacy schema, CLI fallback,
lifecycle, public experience recall, source rebuild, source recall, setup-runner
migration, and rollback. The two slower setup tests confirm that the new scripts
and default-off settings survive an isolated temporary-vault deployment.

## Residual risks

1. A full live doctor takes about five minutes on the current 2.4 GiB source
   projection. It is support tooling, not a readiness endpoint.
2. The live vault currently has no experience ledger or projection, so real
   owner-canary evidence still has to be created under the disabled-by-default
   policy.
3. Passing operations tests proves recoverability and privacy properties, not
   usefulness. Frozen evaluation and owner decision remain separate gates.
