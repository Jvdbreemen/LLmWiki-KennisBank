---
id: DRAFT-2
title: 'Per-seam LLM routing, and make --model reach claude-cli at all'
status: Draft
assignee: []
created_date: '2026-08-12 20:34'
labels:
  - llm
  - privacy
  - memory
dependencies: []
references:
  - scripts/_llm.py
  - docs/superpowers/specs/2026-08-12-self-correcting-memory-layer-design.md
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
GATED: this reverses a recorded decision and needs the user's explicit go-ahead before implementation. `CLAUDE.md` states "Lokaal, altijd", and a memory from 2026-07-02 records *"Gebruik een lokaal generatie-model via Ollama in plaats van headless Claude om cloud-leaks te voorkomen."*

Two defects block the choice from even being available.

**1. `--model` never reaches the CLI.** `_llm._call` runs `subprocess.run(["claude", "-p", full])` and never uses `model_for(provider)`. So `models: {"claude-cli": "haiku"}` in `kennisbank-llm.json` does nothing today and the caller silently gets the session default, which is the most expensive model available.

**2. One chain for every seam.** `_llm.providers()` is global, so reconcile cannot be routed to a stronger model without dragging extraction along — and extraction is the seam that would ship raw 6000-character transcript chunks off the machine.

Measured, on the same reconcile prompt:

| | outcome on a supersede pair | outcome on an unrelated pair | latency |
| --- | --- | --- | --- |
| local `qwen3.5:4b` | SUPERSEDE | **NOOP (wrong)** | 1.6 s |
| `claude -p` (session default) | SUPERSEDE | ADD | 25.3 / 15.8 s |
| `claude -p --model haiku` | SUPERSEDE | ADD | 18.0 / 20.5 s |

Haiku matches the default on correctness here, so the expensive model buys nothing on this task. Latency is nearly identical across models because it is agent startup, not inference.

Volume decides where cloud is affordable:

| seam | calls | payload | proposal |
| --- | --- | --- | --- |
| extract | ~32 per transcript, ~8000 per rebuild | raw chunk, 6000 chars | local |
| judge | ~3 per chunk | candidate text | local |
| reconcile | at most 2 per written memory | two distilled bodies | chain, cloud allowed |
| supersede_pass | only pairs above the threshold | same | chain, cloud allowed |

The seam that may go to the cloud also carries the smallest and cleanest payload. A full rebuild through claude-cli is impossible regardless (8000 calls x 20 s is about 44 hours), so `--all` stays local; only the incremental sweep would route out.

Batching is the optimisation that makes the startup cost bearable: one call judging N pairs turns roughly ten calls per sweep into one.

Whatever is built must keep the existing guarantees: the loud stderr warning per cloud step, `is_local` in the heartbeat reflecting reality, and local as the fallback in the chain so an outage degrades to a local answer rather than to silence.

Design context: `docs/superpowers/specs/2026-08-12-self-correcting-memory-layer-design.md`, per-seam routing and open question 3.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 _llm._call passes --model to claude-cli when a model is configured, proven by a test on the argv
- [ ] #2 A seam can be routed independently of the others, with local remaining the default for every seam
- [ ] #3 Extraction cannot be routed to a cloud provider by accident: it requires its own explicit setting
- [ ] #4 The loud cloud warning and the is_local heartbeat flag stay correct under per-seam routing
- [ ] #5 The recorded local-always decision is explicitly superseded, or the task is closed unimplemented
- [ ] #6 python -m pytest tests -q is green
<!-- AC:END -->
