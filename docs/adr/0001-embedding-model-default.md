# ADR-0001: Default embedding model for semantic tiling

- **Status**: Accepted
- **Date**: 2026-06-20
- **Deciders**: Jvdbreemen, Robert van den Breemen

## Context

Semantic tiling (`scripts/semantic-tiling.py`) computes text embeddings via the
Ollama HTTP API to flag duplicate and related wiki articles. The embedding model
is configurable through the `OLLAMA_EMBED_MODEL` environment variable, but the
*default* shipped value matters: it is what most users actually run, and it
determines the cosine-similarity thresholds the script ships with.

The vault content is predominantly Dutch (and mixed-language in general). The
original default, `nomic-embed-text`, is English-centric: it is small (~274 MB)
and fast, but its similarity scores on non-English text are unreliable and it
spreads cosine values high, requiring thresholds around `0.90` / `0.80`.

## Decision

Make **`qwen3-embedding:8b`** the default embedding model.

- Multilingual (119 languages) — works for Dutch and mixed-language vaults out
  of the box, which is the common case for this project.
- Thresholds are recalibrated for this model: `TILING_THRESHOLD_ERROR = 0.85`
  and `TILING_THRESHOLD_REVIEW = 0.62` (qwen3 spreads lower than nomic).
- `nomic-embed-text` is retained as a documented **fallback** for English-only
  vaults that want a lighter, faster model — selected via
  `OLLAMA_EMBED_MODEL=nomic-embed-text`, with thresholds set to `0.90` / `0.80`.

The choice is overridable end to end through `OLLAMA_EMBED_MODEL`; nothing is
hard-coded beyond the default and its matching thresholds.

## Consequences

**Positive**

- Correct out-of-the-box behaviour for the project's actual (multilingual)
  content — no silent quality loss on non-English articles.
- Thresholds and default model are consistent across code and docs.

**Negative / trade-offs**

- Larger download (~4.7 GB vs ~274 MB) and higher memory/compute per embedding.
  Mitigated by the documented `nomic-embed-text` fallback for English-only,
  resource-constrained setups.
- Thresholds are model-specific: switching the model means recalibrating
  `TILING_THRESHOLD_ERROR` / `TILING_THRESHOLD_REVIEW`. Documented in
  `CONFIGURATION.md` and inline in `semantic-tiling.py`.

## References

- `scripts/semantic-tiling.py` — `OLLAMA_MODEL` default and threshold parsing.
- `CONFIGURATION.md` §4 — embedding model and threshold configuration.
- Commit `7528624` — "feat: make qwen3-embedding:8b the default".
- Commit `e18b6b5` — robust threshold parsing (NL comma + fallback).
