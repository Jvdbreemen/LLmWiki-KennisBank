# Experience candidate review

Experience extraction only creates candidates. A candidate becomes eligible for
the disposable retrieval projection after two independent checks:

1. every structured SourceRef and OutcomeRef validates against the current
   vault and the same session/task;
2. a human has appended an explicit `accepted` review for the candidate's exact
   content hash.

The review command writes only to the canonical experience ledger. It does not
promote a row, rebuild an index, or modify the experience projection.

## Prerequisite

Set the active vault explicitly:

```powershell
$env:KENNISBANK_VAULT = 'D:/Users/Robert/Documents/Claude/Projects/Kluis'
```

## Inspect before deciding

```powershell
python scripts/kb-experience-review.py list --limit 20
python scripts/kb-experience-review.py inspect <experience-id>
```

`list` and `inspect` open the ledger read-only. Copy the current
`content_hash` from `inspect`; a changed candidate deliberately invalidates an
older review.

## Append a decision

```powershell
python scripts/kb-experience-review.py review <experience-id> `
  --decision accepted `
  --actor '<reviewer>' `
  --reason '<what was checked and why this verdict follows>' `
  --content-hash 'sha256:<64 hex characters>' `
  --idempotency-key '<unique review action id>'
```

Use `--decision rejected` when the lesson, evidence, scope, or claimed outcome
is not trustworthy. Decisions are append-only: a later correction is a new
review with a new idempotency key. Reusing the same key with identical input is
a no-op; reusing it for a different decision is rejected.

An accepted review is necessary but not sufficient. Projection rebuild still
resolves the exact sources, checks outcome ownership and version stamps, and
excludes stale, missing, contradictory, rejected, superseded, retracted, and
unreviewed records.
