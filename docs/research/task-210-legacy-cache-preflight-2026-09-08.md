# TASK-210: legacy embedding cache removal is blocked

Observed on 2026-09-08, 05:08:45–05:10:37 UTC, on branch
`codex/source-grounded-experience-production`. This is a bounded, read-only
preflight of the explicitly configured active vault. No document paths, document
text, individual hashes, or vectors are included in this evidence.

## Decision

Keep `_legacy_bytes_hash`, `_legacy_file_hash`, and both migration branches in
`scripts/_embeddings.py`. The live cache still has 4,663 valid entries that need
the file-hash compatibility branch. Removing it now would turn those cache hits
into misses: read-only callers would lose the vectors, and recomputing callers
would request new embeddings.

The eight-character `text_hash` count is zero, but that alone is insufficient:
every entry predates `text_hash` entirely. TASK-210 remains In Progress, blocked
on parent coordination for deployment and cache migration. Production code and
tests were not changed.

## Aggregate live evidence

The cache is `.claude/embeddings-cache.json` under the active
`KENNISBANK_VAULT`. The environment was explicitly set to the user-provided vault
for every inspection and test command.

| Observation | Count |
| --- | ---: |
| Total cache entries | 4,807 |
| Malformed entries | 0 |
| Eight-character `text_hash` | 0 |
| Missing or empty `text_hash` | 4,807 |
| Eight-character file `hash` | 4,807 |
| Sixteen-character `text_hash` | 0 |
| Valid legacy file-hash hits for the active embedding identity | 4,663 |
| Active identity, but current file bytes no longer match the old hash | 134 |
| Different embedding identity | 10 |

The active backend resolved to `ollama:qwen3-embedding:4b`, without a document
prefix. Neither the model nor its default was changed.

The first inspection counted hash lengths without calling the embedding module.
The second loaded the repository module and called
`get_cached(path, readonly_cache, recompute=False)` for entries with the active
identity. Both the outer cache and each entry were wrapped in `MappingProxyType`.
`embed` and `save_cache` were replaced with functions that raise if invoked.
Cache paths were checked to remain within the active vault before file reads.
No model calls or cache writes occurred; `migrated()` remained zero.

All 4,797 entries with the active identity reached the hash comparison: 4,663
hits plus 134 mismatches. There were no skipped outside-vault paths, missing
files, or read failures in that group. The 10 other-identity entries were counted
without reading their document paths.

The cache size was 362,571,557 bytes and its modification timestamp was
`1788811866405872800` nanoseconds since the epoch in both inspections. Size and
modification time were stable across each inspection and between the two.
These are point-in-time observations, not a lock on future writers or a claim
that every document remained unchanged throughout the scan.

## Why ordinary runs have not migrated this cache

Read-only inspection of the deployed `.claude/scripts/_embeddings.py` found:

- `bytes_hash` still returns eight hexadecimal characters from MD5.
- `get_cached` keys reuse on that file hash and embedding identity.
- Its cache writer records `hash`, `id`, `dim`, and `embedding`, without
  `text_hash`.

That deployed module had a modification time of 2026-08-19 04:37:54 UTC. Its
observed implementation cannot perform the newer SHA-256/body-key migration.
Waiting for more runs of that implementation cannot satisfy the removal gate.

The repository has the transition code and persistence hooks:
`scripts/build-embed-index.py` and `scripts/build-kb-index.py` save the cache when
`emb.migrated()` is nonzero. The former visits wiki files; the latter visits wiki
and current memory according to its layer settings. Those visit sets do not
prove that every historical cache entry will be migrated.

## Safe next steps requiring parent coordination

1. Keep compatibility in this branch while coordinating the deployed writers.
   Use the repository's supported `setup.sh` deployment workflow when that
   operation is authorized; replacing individual live scripts is not the
   deployment contract.
2. Prepare a controlled migration with the current cache/corpus as its baseline
   and verify its proposed changes before persisting anything. Preserve vectors
   only where the existing compatibility checks prove the file and embedding
   identity still match. The 134 changed-file entries and 10 other-identity
   entries must not be relabelled as current SHA-256 hits without that evidence.
3. Coordinate cache persistence and old writers, then recheck all cache entries,
   including entries outside the normal builders' visit sets. Do not assume a
   successful builder run means the whole cache is migrated.
4. Resume TASK-210 only after no required legacy entries remain. Then reground
   the regression tests, record the failing run, remove the compatibility code,
   and record the passing bounded tests. Full-suite validation remains with the
   parent.

No deployment, migration, cache cleanup, index rebuild, or live memory/review
change was performed in this task.

## Test evidence and limits

With the active vault environment explicitly preserved at process launch:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m pytest -q -p no:cacheprovider tests/test_embed_cache_body_key.py tests/test_cache_file_resolution.py
```

Result: **17 passed in 0.69 seconds**, exit code 0. The existing pytest session
fixture isolates tests in a temporary vault and restores the environment;
individual file fixtures are temporary as well.

This was an unchanged-code baseline, including the legacy migration tests.
There is no red/green implementation cycle to report: the live-data prerequisite
failed before test or production-code edits were permitted. The full suite was
not run, and no full-suite result is claimed.

The remaining `hashlib.md5` call in `scripts/_embeddings.py` is intentional while
this prerequisite remains unmet. No claim is made that TASK-210's removal
acceptance criteria are complete.
