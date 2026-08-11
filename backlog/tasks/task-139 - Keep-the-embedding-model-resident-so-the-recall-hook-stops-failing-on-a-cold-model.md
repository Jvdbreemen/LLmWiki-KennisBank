---
id: TASK-139
title: >-
  Keep the embedding model resident so the recall hook stops failing on a cold
  model
status: To Do
assignee: []
created_date: '2026-08-11 17:19'
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
- [ ] #1 The embedding model stays resident across an idle period longer than the current 30 minute TTL, verified through /api/ps
- [ ] #2 The judge/extraction model is pinned to a size that coexists with the embedding model on a 16 GB GPU, with the VRAM figures recorded
- [ ] #3 A cold or evicted embedding model is visible to the user (session start or hook notice) instead of silently yielding no knowledge
- [ ] #4 python -m pytest tests -q is green
<!-- AC:END -->
