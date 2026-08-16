---
id: TASK-196
title: >-
  CACHE_FILE freezes at import, and the machine-global KENNISBANK_VAULT makes
  test speed order-dependent
status: Done
assignee: []
created_date: '2026-08-16 10:44'
labels: []
dependencies: []
ordinal: 165700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found while shipping TASK-195's trap 1, by a 14-minute test run that py-spy caught parsing JSON.

`_embeddings.CACHE_FILE` is a module-level constant: `vault_root() / ".claude" / "embeddings-cache.json"`, frozen at first import. On this machine the user profile exports `KENNISBANK_VAULT` (the hooks need it), so any test module that imports `_embeddings` at module level — directly or through another script — freezes CACHE_FILE onto the REAL vault's multi-megabyte cache during pytest collection. Every later test whose code path calls `emb.load_cache()` (the sweep's maintenance passes call it via `current_items`, several times per `run_sweep`) then parses that file repeatedly.

Measured: `pytest test_groundcheck.py test_memory_sweep.py` went from 2s to 835s purely on import order; each file alone was fast because `test_memory_sweep` imports `_embeddings` inside `setUp` after pointing the env at a temp vault. The immediate fix in TASK-195's branch makes the new test file import lazily too, with a comment saying why the order is load-bearing.

The class of bug is bigger than one file:

1. **Any module-level `import _embeddings` in tests/ re-arms it.** Several existing test files do this; today the full suite happens to be fast, but that is luck about which tests call `load_cache` after collection-time freezing, not a property anyone chose.
2. **The hermetic pin in `tests/__init__` covers the embed ENDPOINT but not the VAULT.** Pinning `KENNISBANK_VAULT` to a fresh temp dir there would kill the whole class — but needs an audit first: any test that (deliberately or accidentally) reads the real vault would change behaviour, and that audit is exactly the kind that must not be done in a release-adjacent hurry.
3. Related to TASK-167 (the unguarded `parents[2]` setdefault): both are "vault resolution happens at import time with whatever env is lying around".

Options to weigh: make CACHE_FILE a function (`cache_file()`) resolved at call time; or pin the vault in tests/__init__ after the audit; or both. Measure the suite before/after — the fix must not quietly slow the real hot path (load_cache is called on session-start paths too).
<!-- SECTION:DESCRIPTION:END -->
