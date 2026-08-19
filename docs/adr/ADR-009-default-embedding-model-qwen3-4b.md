---
id: "ADR-009"
title: "Default embedding model moves to qwen3-embedding:4b"
status: "Accepted"
date: "2026-08-19"
binding: true
gate: null
documents_shipped: false
verified_in: []
supersedes: ["ADR-0001"]
superseded_by: null
format: "madr"
---

# ADR-009: Default embedding model moves to qwen3-embedding:4b

## Context and Problem Statement

ADR-0001 (2026-06-20) made `qwen3-embedding:8b` the shipped default for the
embedding backend, chosen for multilingual quality over the English-centric
`nomic-embed-text`. Since then the vault grew and an eval harness landed,
making the choice measurable instead of assumed. The 2026-08-03 model sweep
(`docs/research/embedding-model-sweep-2026-08.md`) measured latency, wiki-eval
and memory-eval scores and VRAM across candidates on the real vault.

The code default was flipped to `qwen3-embedding:4b` on the strength of that
sweep (`scripts/_embeddings.py:64`), and TASK-182 closed the migration gap the
flip exposed (index `embed_id` mismatch made recall return `[]` until a
rebuild; the upgrade path now detects it and names the fix). ADR-0001 kept
claiming 8b — recorded as drift by the C4 documentation pass of 2026-08-18.
This record settles the decision the code already made.

## Decision

The default embedding model is **`qwen3-embedding:4b`**.

Measured against the incumbent 8b on both eval sets (RTX 3080, 16 GB):

| model | latency | wiki-eval | memory-eval | VRAM |
|---|---|---|---|---|
| qwen3-embedding:4b | 322 ms | 0.967 | **0.540** | 6.2 GB |
| qwen3-embedding:8b | 347 ms | 0.961 | 0.530 | 8.4 GB |

The 4b is not a compromise: it scores at least as well on both sets, is
faster, and leaves ~2 GB of VRAM headroom that the judge model and Atlas
share (the VRAM budget is a single shared constraint across every
LLM-calling container).

Unchanged from ADR-0001:

- The choice stays overridable end to end via the configuration chain
  (`kennisbank-embed.json` / `OLLAMA_EMBED_MODEL`); nothing is hard-coded
  beyond the default.
- The semantic-tiling thresholds `0.85` (error) / `0.62` (review) hold for
  the qwen3-embedding family and are not recalibrated.
- `nomic-embed-text` remains a documented fallback for English-only vaults
  (thresholds `0.90` / `0.80`), though the sweep flags it as a trap for this
  vault's mixed-language content.

## Consequences

- Existing indexes built under 8b carry a mismatching `embed_id`; recall
  gates on it rather than serving cross-model vectors. The upgrade path
  detects the mismatch and instructs `ollama pull qwen3-embedding:4b` plus an
  index rebuild (TASK-182). Deleting the embedding cache is safe and costs
  one re-embed pass.
- ADR-0001 is superseded, not retired: its reasoning about multilingual
  defaults and threshold pairing still governs; only the size choice moved
  with the evidence.
- Any future default flip must clear the same bar: measured on both eval
  sets on the real vault, with the migration path in the same change.
