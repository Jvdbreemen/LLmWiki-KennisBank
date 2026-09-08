---
id: TASK-210
title: Verwijder de md5-herkenning uit _embeddings zodra de cache gemigreerd is
status: In Progress
assignee: []
created_date: '2026-08-23 19:11'
updated_date: '2026-09-08 05:12'
labels:
  - hygiene
  - agent-geheugen
dependencies: []
references:
  - docs/research/task-210-legacy-cache-preflight-2026-09-08.md
ordinal: 174700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
De sha256-overstap liet een enkele md5-aanroep staan: _legacy_bytes_hash. Die produceert nooit een nieuwe identiteit; hij VERIFIEERT alleen bestaande cache-entries zodat get_cached ze kan upgraden zonder opnieuw te embedden. Zonder dat pad kost de overstap ruim drie uur lokale GPU-tijd voor vectoren die bit-identiek zijn aan wat er al ligt.

Zodra geen enkele entry nog een text_hash van 8 tekens draagt, is het pad dood gewicht en kan het weg: _legacy_bytes_hash, _legacy_file_hash, en de twee migratietakken in get_cached.

Controleren zonder te raden:

  python3 -c "import json,collections,pathlib,os; c=json.loads(pathlib.Path(os.environ['KENNISBANK_VAULT'],'.claude/embeddings-cache.json').read_text('utf-8')); print(collections.Counter(len(e.get('text_hash','')) for e in c.values()))"

Staat daar alleen nog 16, dan is de migratie rond. Let op: entries migreren pas wanneer een aanroeper de cache wegschrijft, en dat doen alleen build-embed-index en build-kb-index. De hot loops in _maintenance en memory-sweep lezen wel maar schrijven nooit, dus reken op een paar dagen normale runs voordat de teller op nul staat.

Robert wil geen md5 in zijn codebases; deze aanroep is de laatste, en staat er alleen als overgangsmaatregel.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Geverifieerd met de teller dat geen enkele cache-entry nog een text_hash van 8 tekens heeft
- [ ] #2 _legacy_bytes_hash, _legacy_file_hash en beide migratietakken uit get_cached verwijderd
- [ ] #3 Geen enkele hashlib.md5-aanroep meer in scripts/
- [ ] #4 Testsuite groen; de tests die legacy-entries construeren zijn mee verwijderd of omgezet
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Inspect the active vault embedding cache read-only; report aggregate hash-length counts, including eight-character text_hash values and older entries without text_hash. Do not print document paths, text, or vectors.
2. Proceed only if no eligible legacy entries remain. Otherwise investigate read-only alternatives and return to the parent without changing compatibility or the live cache.
3. Reground the cache/hash regression tests on the SHA-256-only contract and record their failing run before changing scripts/_embeddings.py.
4. Remove _legacy_bytes_hash, _legacy_file_hash and the MD5 migration branches while preserving the embedding default, SHA-256 identities and cache-hit behavior.
5. Run the bounded related tests, scan scripts/ for hashlib.md5 calls, self-review the scoped diff, and record sanitized evidence with exact red/green counts and remaining integration risk. Full-suite validation belongs to the parent.
Write scope: scripts/_embeddings.py, directly related cache/hash tests, this task via the backlog CLI, and docs/research/task-210-*.md. Keep the current branch; no commit, deployment, live-cache write or memory/review mutation.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-09-08 bounded worker preflight: BLOCKED on required live compatibility; task remains In Progress.

Read-only live counts: 4,807 entries; 0 eight-character text_hash values; 4,807 entries without text_hash and with an eight-character file hash. The zero text_hash counter alone does not mean migration is complete. Current-repo get_cached(recompute=False), with immutable cache/entry views and embed/save_cache guarded against invocation, returned 4,663 valid legacy file-hash hits. Another 134 active-identity entries have changed file bytes; 10 entries use a different embedding identity. No model calls, cache writes, or in-memory migrations occurred. Cache size (362,571,557 bytes) and mtime_ns (1788811866405872800) stayed stable through both inspections.

The deployed _embeddings.py still writes MD5 file hashes and no text_hash (observed deployed module mtime: 2026-08-19 04:37:54 UTC). Ordinary runs of that code cannot perform the new migration. The active backend resolves to ollama:qwen3-embedding:4b with no document prefix.

No production or test changes were made. Existing bounded baseline: python -B -m pytest -q -p no:cacheprovider tests/test_embed_cache_body_key.py tests/test_cache_file_resolution.py -> 17 passed in 0.69s, exit 0. No red/green cycle was started because the removal prerequisite failed. Full suite not run. Acceptance criteria remain unchecked; the literal zero count in AC #1 is not sufficient with pre-text_hash entries present.

Parent coordination is required for supported deployment plus a controlled, verified cache migration before this task can remove compatibility. Do not relabel changed-file or other-model entries as valid, delete historical entries, or assume normal builder visit sets cover the entire cache. Keep scripts/_embeddings.py and existing SHA-256/default behavior unchanged until the prerequisite is met.

Sanitized evidence and safe alternatives: docs/research/task-210-legacy-cache-preflight-2026-09-08.md. Changed paths for this bounded task: this backlog file and that evidence document only. No branch change, commit, push, release, live index/cache/memory/review modification, or overlap with projection CLI or TASK-209 work.
<!-- SECTION:NOTES:END -->
