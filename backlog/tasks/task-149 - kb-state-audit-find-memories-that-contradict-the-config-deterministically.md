---
id: TASK-149
title: 'kb-state-audit: find memories that contradict the config, deterministically'
status: To Do
assignee: []
created_date: '2026-08-12 20:33'
updated_date: '2026-08-12 20:42'
labels:
  - memory
  - audit
  - tooling
dependencies: []
references:
  - docs/superpowers/specs/2026-08-12-self-correcting-memory-layer-design.md
  - scripts/kb-lint.py
  - scripts/_memory.py
priority: medium
ordinal: 143700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The `second-brain-audit` skill ships a deterministic scanner. Run against this vault it found **zero** contradictions while four were demonstrably present, because it compares monetary values only and this vault has none. Its own guidance covers that case: *"A zero is not a clean bill of health"*, and it prints a coverage warning when it knows it was blind.

Build the KennisBank equivalent, for the value types this vault actually carries: model tags, thresholds, version numbers, paths, toggle states. With one advantage the skill's script does not have — an **authority** to compare against rather than a second opinion: `kennisbank-embed.json`, `kennisbank-llm.json`, `kennisbank-settings.json`, and the repo's own constants.

The four cases it must catch, all `status: current` today and therefore injectable by the recall hook:

| memory | claims | authority says |
| --- | --- | --- |
| `2026-07-02-embedding-model-specificaties` | `qwen3-embedding:8b` is the default | `kennisbank-embed.json` pins `4b` |
| `2026-07-02-gebruik-qwen3-embedding8b-op-gpu` | 8b chosen for latency | same |
| `2026-07-02-drempelwaarden-voor-deduplicatie` | 0.85 / 0.62-0.84 | floors are 0.50 and 0.45 |
| `2026-07-05-default-model-selection` | always `claude-opus-4-8` | version stale, policy still valid |

Output follows the skill's three piles, plus a coverage line that is not optional:

```
CONTRADICTED  n    memory says X, the authority says Y
UNSUPPORTED   n    a claim whose value appears in no authority
CONFIRMED     n
COVERAGE      n    current memories with no checkable value -- here the audit was blind
```

Constraints: no LLM, read-only, JSON output for the heartbeat, and a non-zero exit only when the caller asks for it. Scope to `status: current`, because that is exactly the set the recall hook can inject — in this vault there is no harmless archive, everything current is always-loaded.

The last pile is the point. A number without its blind spot is how the skill's own script reported a clean bill of health on a vault with four contradictions in it.

Design context: `docs/superpowers/specs/2026-08-12-self-correcting-memory-layer-design.md`, artifact 2.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The script finds all four known-stale memories without any LLM call
- [ ] #2 Every report ends with a coverage line stating how many current memories carried no checkable value
- [ ] #3 Output is available as JSON so the sweep heartbeat can carry the counts
- [ ] #4 The script never writes to the vault, proven by a test
- [ ] #5 A memory that agrees with the authority is reported as confirmed, not silently omitted
- [ ] #6 python -m pytest tests -q is green
- [ ] #7 Memories that look state-shaped but carry volatility=event (or no volatility at all) are listed as a separate pile, so the safe default does not silently disable self-correction
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Adversarial review, 2026-08-12. This task gains weight rather than losing it.

P1c showed supersede_pass has 11 candidate pairs in the entire corpus, so the after-the-fact LLM mechanism corrects almost nothing today. A deterministic audit that compares memories against the authoritative config files does not depend on similarity at all, and it caught all four known-stale memories in the manual pass. It is the cheapest and most reliable of the three artifacts in the spec.

It also carries mitigation 1 from TASK-146: report memories that look state-shaped but are labelled or defaulted to event. Without that, the safe default silently turns self-correction off for anything the extractor was unsure about.
<!-- SECTION:NOTES:END -->
