# Source-recall and experience-memory upgrade note

Status: feature branch only (`codex/source-recall-experience-evidence`)

## Migration impact

- Existing wiki, memory, raw-source, and `kb-index.db` data is not rewritten by
  enabling these features.
- Setup already deploys every `scripts/*.py` and `commands/**/*.md` file
  idempotently. The new operational entry points are `rebuild-experience.py`,
  `kb-projection-doctor.py`, and the namespaced rebuild/proposal commands.
- `source_recall` and `experience_recall` remain `false` by default until the
  paired evaluation gates pass.
- `kb-source.db` is disposable and rebuilds from approved raw-source roots.
  `kb-experience.db` rebuilds its derived records from append-only event and
  outcome tables. Neither database is a source of truth.

## Rollback and recovery

Run the relevant builder with `--progress`. Both builders use a staging file
and atomically replace the target only after a complete successful build. A
failed read, embedding, or schema operation therefore leaves the previous
derived database in place. If a derived database is corrupt, move it aside or
restore the latest vault backup and rebuild it; raw files and append-only
experience evidence remain untouched.

`kb-projection-doctor.py` is read-only. It reports stale source hashes,
orphaned source references, redaction-affected experiences, unresolved
provenance, closed statuses, and route state. Retraction, supersession,
narrowing, and deletion close or invalidate derived use; they do not silently
delete the evidence trail.

## Known limitations

- The current live vault has no reviewed experience holdout and no deployed
  experience event database, so the product-value gate is not yet passable.
- The source smoke set is only a mechanical check; it is not a representative
  50-positive/10-negative evaluation and has no downstream answer-correctness
  labels.
- Cloud-backed client sessions may use the local bridge only when the operator
  explicitly exports retrieved context. These projections do not add a cloud
  fallback, and rebuild commands require the configured local endpoint policy.
- Existing skill evolution remains a separate human-gated task. Experience
  proposals never edit skills automatically.

## Verification evidence

The branch contains hermetic tests for source indexing/holdout contracts,
experience extraction/recall/promotion, setup deployment, doctor health,
atomic rebuild failure preservation, and the six-arm evaluation packet. The
release decision is recorded separately in the dated evidence packet; a green
unit test means the contracts work, not that the new layers are useful enough
to enable by default.
