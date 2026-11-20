---
id: TASK-262
title: Opt-in cloud map step for draining a large /destilleer backlog
status: In Progress
assignee: []
created_date: '2026-11-19T23:46:00Z'
updated_date: '2026-11-20T11:57:00Z'
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
- [x] #1 New toggle distill_cloud_map in _settings.DEFAULTS, default False; distill-map.py exits non-zero with a clear message and makes no network call when it is off
- [x] #2 Map call uses explicit provider/model/endpoint (no fallback to the vault llm config); test proves the vault config cannot leak into it
- [x] #3 Every call records HTTP status/error body, usage tokens and cost; failures are reported, never silently treated as empty extraction
- [x] #4 OpenRouter provider prefs data_collection=deny are sent; inline secrets are redacted before sending
- [x] #5 Large stripped transcripts are chunked and per-chunk results merged; empty transcripts skip the call and are recorded as empty
- [x] #6 Resumable: existing per-stem output is skipped; outputs live outside scratch
- [x] #7 /destilleer documents the optional map+reduce path with per-batch watermarking
- [x] #8 Trial batch of ~10 stems run with real token/cost/JSON-valid numbers reported before the full drain
- [ ] #9 pytest suite green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Run 2026-11-20 on the owner vault: 364 transcripts mapped with deepseek-v4-flash-0731, 42.8M chars, ~$1.93 total incl. $0.44 lost before the chunk cache existed. Bugs found and fixed on this branch: prompt injection from archived judge prompts (transcript now sent as delimited data), one broken JSON chunk discarded a whole stem (retry + per-chunk cache), all-NUL outputs after a hard stop were skipped (fsync + JSON-validity resume), digest crashed on side files, Codex transcripts stripped to 0 chars (fallback to _sweepstate.transcript_text), archive filter blind behind session-owner (entrypoint sdk-cli + one prompt). GLM 5.3 Flash rejects reasoning off (HTTP 400) -> --reasoning low; :batch variants need the async batch API (HTTP 404), not supported. Full suite: 24 failures that also fail on clean origin/main (embed_residency, hermes_install, opruimen_skill, proc_bounded, vaultpath), not caused by this branch.
<!-- SECTION:NOTES:END -->
