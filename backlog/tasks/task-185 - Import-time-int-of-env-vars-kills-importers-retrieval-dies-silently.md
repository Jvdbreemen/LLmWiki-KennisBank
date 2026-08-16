---
id: TASK-185
title: Import-time int() of env vars kills importers — retrieval dies silently
status: In Progress
assignee: []
created_date: '2026-08-15 23:30'
updated_date: '2026-08-15 23:30'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by the 2026-08-15 eight-angle /code-review over main...release/v0.31.1,
verified against source before filing. Task IDs 169-179 are reserved by the
open PR #2 branch; this series starts at 180.

OLLAMA_NUM_CTX = int(os.environ.get("KB_EMBED_NUM_CTX", ...) or 2048)
(_embeddings.py:76) raises ValueError at import for any malformed value;
same pattern at _llm.py:58 (KB_LLM_NUM_CTX) and memory-sweep.py:280/290
(KB_SWEEP_*). A user setting KB_EMBED_NUM_CTX=4k kills `import
_embeddings` everywhere; the fail-open retrieval hook swallows the
ImportError and injects nothing — retrieval off for every session, no
message. kb-recall's _memory_min_cos_default in the same release wraps
the identical parse in try/except, so the repo already knows the right
pattern; it just is not shared.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A shared fail-soft env-int helper (garbage -> default) used by all four sites
- [ ] #2 A test sets a malformed value for each var and asserts import succeeds with the default
- [ ] #3 No import-time int() of environment values remains in scripts/ (grep-guarded)
<!-- AC:END -->
