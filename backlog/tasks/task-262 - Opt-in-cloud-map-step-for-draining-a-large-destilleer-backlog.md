---
id: TASK-262
title: Opt-in cloud map step for draining a large /destilleer backlog
status: In Progress
assignee: []
created_date: '2026-11-19T23:46:00Z'
updated_date: '2026-11-19T23:46:00Z'
labels:
  - destilleer
  - llm
dependencies: []
ordinal: 195600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
When hundreds of archived transcripts wait for distillation, the agent-driven /destilleer cannot read them all in one context. Add scripts/distill-map.py: strip each pending transcript, redact inline secrets, call one explicitly chosen OpenRouter model (default deepseek/deepseek-v4-flash-0731) per chunk, and write compact candidate-knowledge JSON per stem to a resumable store. The main session then reduces those candidates into the wiki and watermarks per batch. Cloud is opt-in and temporary: gated by a new settings toggle distill_cloud_map (default off), switchable via /kennisbank:settings. The map call never inherits the vault's kennisbank-llm.json, so background jobs stay local.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 New toggle distill_cloud_map in _settings.DEFAULTS, default False; distill-map.py exits non-zero with a clear message and makes no network call when it is off
- [ ] #2 Map call uses explicit provider/model/endpoint (no fallback to the vault llm config); test proves the vault config cannot leak into it
- [ ] #3 Every call records HTTP status/error body, usage tokens and cost; failures are reported, never silently treated as empty extraction
- [ ] #4 OpenRouter provider prefs data_collection=deny are sent; inline secrets are redacted before sending
- [ ] #5 Large stripped transcripts are chunked and per-chunk results merged; empty transcripts skip the call and are recorded as empty
- [ ] #6 Resumable: existing per-stem output is skipped; outputs live outside scratch
- [ ] #7 C:/Program Files/Git/destilleer documents the optional map+reduce path with per-batch watermarking
- [ ] #8 Trial batch of ~10 stems run with real token/cost/JSON-valid numbers reported before the full drain
- [ ] #9 pytest suite green
<!-- AC:END -->
