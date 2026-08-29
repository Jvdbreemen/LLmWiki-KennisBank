# Source and experience memory smoke evidence

Date: 2026-08-26
Branch: `codex/source-recall-experience-evidence`
Embedding backend: local Ollama `qwen3-embedding:4b` (2560 dimensions)

## Source recall smoke

Three real local session files from the configured KennisBank vault were read
without changing the vault. Their first source windows were indexed in an
in-memory SQLite/sqlite-vec database. Queries were derived from the selected
windows only to verify the retrieval and provenance plumbing.

| arm | hit@1 | hit@3 | MRR |
| --- | ---: | ---: | ---: |
| lexical-only | 0.33 | 1.00 | 0.67 |
| hybrid vector + lexical | 1.00 | 1.00 | 1.00 |

Provenance precision was `1.00` for returned smoke hits. No production index,
raw file, memory status, or usage database was changed.

This is not product-value evidence: the sample is n=3, contains no negative
queries, and the queries are partly extractive. It does not satisfy the frozen
source gate (50 positive and 10 negative queries plus paired answer
correctness). Verdict: **hold**.

## Experience recall smoke

The durable event store, outcome derivation, evidence gates, validated-only
recall, failure advisory, and proposal-only promotion paths are covered by
hermetic contract tests. The live vault currently has no experience projection
or labelled experience holdout, so no live experience usefulness claim is
made. Verdict: **hold**.

## Next evidence required

1. Freeze at least 50 positive and 10 negative source cases before indexing.
2. Freeze 60 experience cases across success, failure, conflict/stale, and
   unknown/unrelated categories.
3. Compare downstream answer/action correctness with paired confidence
   intervals against the strongest non-experimental baseline.
4. Keep both routes off by default until their respective gates pass.
