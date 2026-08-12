---
id: TASK-139
title: >-
  Keep the embedding model resident so the recall hook stops failing on a cold
  model
status: Done
assignee: []
created_date: '2026-08-11 17:19'
updated_date: '2026-08-12 16:31'
labels:
  - performance
  - retrieval
  - ops
dependencies: []
references:
  - scripts/_embeddings.py
  - scripts/_llm.py
  - kennisbank-llm.json
priority: high
ordinal: 133700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The retrieval hook has a 2 s hot-path budget. A cold model load takes 30-60 s (measured: 62 s). Throughout a long working session the hook repeatedly reported "embedding-model reageerde niet binnen 2s"; the feature silently does not run, which costs more in practice than any recall improvement on the eval set gains.

The mechanism to prevent this already exists and is not the problem:

- `scripts/_embeddings.py:254` sends `"keep_alive": "30m"` on every embed call.
- The environment carries `OLLAMA_KEEP_ALIVE=30m`.
- `/api/ps` confirms the model does stay resident: `qwen3-embedding:4b`, 6.24 GB VRAM, with an expiry 30 minutes out.

Two causes remain:

1. **The 30-minute TTL.** Any longer gap unloads the model, and the next prompt pays a cold load the hook cannot wait for.
2. **Eviction by a second model.** Observed directly while running the TASK-134 llm clusterer: `gemma4:12b` (~8-9 GB) plus the embedding model (6.24 GB) does not fit in the 16 GB of an RTX 3080 Laptop, so Ollama unloaded the embedding model. A trivial prompt then took 79 s and the embed probe returned None.

Directions, cheapest first. No warm-keeping worker is needed:

- Send `keep_alive: -1` instead of `"30m"` (or set `OLLAMA_KEEP_ALIVE=-1` for the Ollama server process). Cost: 6.24 GB of VRAM held permanently.
- Pin a small model for judge/extraction work in `kennisbank-llm.json` (`qwen3.5:4b` is about 3 GB and coexists; `gemma4:12b` does not). `keep_alive: -1` does NOT prevent eviction when a larger model needs the memory, so this is the load-bearing half of the fix.
- Consider reporting the resident/cold state in the session-start summary, so a cold model is visible rather than showing up as "no knowledge retrieved".

Unrelated trap noticed while measuring: the environment sets `OLLAMA_EMBED_MODEL=qwen3-embedding:8b` while the index is built with `qwen3-embedding:4b`. KennisBank reads its own config and ignores that variable today, so nothing is broken, but anything that starts honouring it would silently mix two vector spaces.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The embedding model stays resident across an idle period longer than the current 30 minute TTL, verified through /api/ps
- [x] #2 The judge/extraction model is pinned to a size that coexists with the embedding model on a 16 GB GPU, with the VRAM figures recorded
- [x] #3 A cold or evicted embedding model is visible to the user (session start or hook notice) instead of silently yielding no knowledge
- [x] #4 python -m pytest tests -q is green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause was not the keep_alive TTL but the context allocation. Ollama sizes an embedding model from num_ctx, not from document length: qwen3-embedding:4b claimed 6.24 GB of VRAM against 2.5 GB of weights. Measured on the target machine (RTX 3080 Laptop, 16 GB):

  ctx 16384 -> 6.24 GB | 8192 -> 5.00 GB | 4096 -> 4.37 GB | 2048 -> 4.06 GB | 512 -> 2.88 GB

Document lengths after doc_text: memory median 48 tokens (p95 67, max 87), wiki median 851 (max 1000, capped). Nothing approaches 2048.

Vectors are unchanged by the smaller window, proven three ways: cosine(ctx16384, ctx2048) = 1.000000 for a short query, the same for a ~1000-token document, and a fresh embedding through the new path matches the vector already in kb-index.db exactly. No re-index, no threshold recalibration.

VRAM budget, all measured with both models loaded:
  qwen3-embedding:4b @ ctx 2048 = 4.06 GB
  qwen3.5:4b @ ctx 4096 = 3.13 GB   -> both resident: 7.19 GB, 7.6 GB free
  qwen3.5:9b @ ctx 4096 = 5.49 GB   -> alternative judge, 9.55 GB total
  gemma4:12b @ ctx 4096 = 8.06 GB   -> does not fit beside the embedding model; this is what evicted it

Done (commit 8d11970): num_ctx 2048 and keep_alive -1 in _embeddings.py with KB_EMBED_NUM_CTX / KB_EMBED_KEEP_ALIVE overrides, tests/test_embed_residency.py pinning both, and the deploy copy in $VAULT/.claude/scripts refreshed. Judge model switched to qwen3.5:4b in kennisbank-llm.json AND in the user-scope KB_LLM_MODEL environment variable, which was set to gemma4:12b and silently overrode the config file.

Still open: AC #1 (verify residency across an idle gap longer than 30 minutes) and AC #3 (surface a cold model at session start instead of reporting no knowledge). Also note scripts/install-agent-envs.py:463 and scripts/_copilot.py:49 still write KB_LLM_MODEL = gemma4:12b as the repo default, so re-running the installer would undo the environment change.

Full measurements and web sources: ~/Claude/research/2026-08-11-ollama-modelcombinatie-16gb-kennisbank.md

Finished 2026-08-12.

AC #1 (residency across an idle gap) — verified through /api/ps rather than waited out, because keep_alive -1 removes the TTL entirely. Forced a fresh embed through the current _embeddings path first (0.9 s warm, dim 2560), then read the process table:

  qwen3-embedding:4b  4.06 GB VRAM  ctx 2048  expires 2318-11-22
  qwen3.5:4b          3.13 GB VRAM  ctx 4096  expires +30 min

An expiry three centuries out is what 'no TTL' looks like in Ollama's answer, so no idle gap can unload it. Total 7.19 GB of 16 GB, exactly the measured budget.

AC #3 (a cold model is visible) — the retrieval hook already reported the miss, but only AFTER the answer had been given without the vault. The session-start status line now reads /api/ps and appends `embedding-model koud`, or `embedding-model koud (wordt geladen)` when a warm-up child is actually alive. Warm says nothing; unknown (another provider, Ollama down) also says nothing, because guessing 'cold' would send the user hunting for a VRAM problem that is not there. Capped at 100 ms: a live local Ollama answers in ~3 ms, and a dropped connection must not eat the 250 ms budget the status line is held to.

The regression the notes warned about is closed. install-agent-envs.py wrote gemma4:12b in FOUR generated surfaces plus two gemma4:latest fallbacks, and _copilot.py in a fifth; re-running the installer would have undone the environment fix. They now share one constant with _llm.OLLAMA_DEFAULT_MODEL = qwen3.5:4b, guarded by tests/test_llm_model_default.py, which also fails if a literal reappears. _activity.py's opt-in Layer-3 date fallback carried its own gemma4:12b and is pinned to the same value -- deliberately still off the provider chain, since routing it through _llm could hand a user's phrasing to a configured cloud provider.

Docs swept in the same pass: README, README.nl, CONFIGURATION (with the VRAM table), AGENTS, docs/agent-integrations, ADR-0003's config snippet, kennisbank-llm.example.json and setup.sh's interactive default.

Still true and NOT fixed here: the environment sets OLLAMA_EMBED_MODEL=qwen3-embedding:8b. _embeddings._resolve() DOES honour that variable as a legacy fallback when neither KB_EMBED_MODEL nor kennisbank-embed.json names a model -- measured: a vault without that config resolves to the 8b model. The real vault pins 4b in its config, so nothing is broken today, but the trap is one deleted config file away.

Gate: `python -m pytest tests -q` -> 1217 passed, 2 skipped in 5:01, exit 0.
<!-- SECTION:NOTES:END -->
