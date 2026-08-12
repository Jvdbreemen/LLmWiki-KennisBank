---
id: TASK-143
title: >-
  The judge is a reasoning model and its thinking eats the answer: send
  think=false
status: In Progress
assignee: []
created_date: '2026-08-12 19:04'
labels:
  - bug
  - llm
  - memory
  - performance
dependencies: []
references:
  - scripts/_llm.py
  - scripts/_activity.py
  - scripts/_extract.py
  - scripts/_judge.py
  - scripts/_reconcile.py
priority: high
ordinal: 137700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`qwen3.5` is a reasoning model. `_llm._call()` posts to Ollama's `/api/generate` without the `think` parameter, so the model emits its chain-of-thought first and the answer only afterwards — inside the same `num_ctx` window, which TASK-139 pinned at 4096 for VRAM reasons. When the thinking fills that window, Ollama returns `done_reason: "length"` with `response: ""` and the reasoning in a separate `thinking` field that nothing reads.

`_call` then returns None, and every seam falls back silently:

- `_extract.extract_candidates()` -> `[]`, so nothing is captured from that chunk.
- `_judge.judge()` -> `unverified`, so the memory lands in quarantine.
- `_reconcile.judge_reconcile()` -> `ADD`, so a superseding fact is written as a duplicate instead of closing the old one.

Measured on the live vault (RECONCILE_SYSTEM, three real pairs, temperature 0, num_ctx 4096):

| config | latency | eval_count | empty responses |
| --- | --- | --- | --- |
| current (thinking on) | 30.2 / 40.3 / 55.7 s | 2106 / 2861 / 3885 | 1 of 3 |
| `think: false` | 1.64 / 1.73 / 1.64 s | 39 / 48 / 40 | 0 of 3 |

So the seam is roughly 25x slower AND fails outright about a third of the time. The failure is invisible by construction: the fail-safes exist so a model outage never blocks capture, and they do exactly that here.

Corroboration in the vault: the heartbeat's last run wrote 5 memories from 10 transcripts, `09-memory` holds 23 unverified, and doctor.sh reports "5 unverified memories older than 48h (sweep/judge hangs?)". Not proof on its own — write volume tracks activity — but it is the shape this bug produces.

`think: false` is accepted by non-thinking models too: `gemma4:12b` answered normally with the parameter set (26.4 s cold, valid JSON, no HTTP error), so the flag can be sent unconditionally rather than per-model.

Scope: `scripts/_llm.py::_call` is the shared seam. `scripts/_activity.py::_llm_call` builds its own `/api/generate` payload for the opt-in temporal fallback and needs the same treatment.

Not a model-choice problem: 9b thinks too (2124 tokens on the same prompt, 42.9 s). Both sizes need the flag. The 4b-vs-9b comparison in TASK-142 is only meaningful once this is fixed, because today every arm is partly measuring the fail-safe.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 _llm._call sends think=false to Ollama, with an env override to turn thinking back on for anyone who wants it
- [ ] #2 _activity._llm_call sends the same flag
- [ ] #3 A test pins the payload for both call sites, so a refactor cannot drop the flag silently
- [ ] #4 The three seams are re-measured after the fix and the empty-response rate and latency are recorded
- [ ] #5 python -m pytest tests -q is green
<!-- AC:END -->
