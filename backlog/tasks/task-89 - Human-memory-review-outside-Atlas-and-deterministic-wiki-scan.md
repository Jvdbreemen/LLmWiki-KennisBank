---
id: TASK-89
title: 'Human memory review outside Atlas + deterministic wiki-scan (Spoor D)'
status: To Do
assignee: []
created_date: '2026-07-28 08:00'
labels:
  - memory
  - review
  - llm-wiki-adoption
dependencies: []
ordinal: 96300
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Two real gaps found comparing against llm_wiki's review-queue pattern:

D1 — The unverified->current/retracted transition has no human entry point outside the Atlas GUI (`POST /memory/decide` is the only one; TASK-23: 31 backed-up unverified memories cleared with a one-off script). Shared decision function in `_memory.py`: `DECISIONS = {approve: current, reject: retracted, skip: None}` (explicit no-op, Mem0 pattern), `pending_reviews()`, `decide(stem, decision, via)` — only `unverified` decidable (409 semantics), traversal guard, JSONL audit log (`.claude/memory-review-log.jsonl`), `review_counts(days)`. **Crash-safe order (llm_wiki #614): write the status change durably first, append the audit line after; any failure leaves the item unverified with the error surfaced — never silently "handled".** Refactor the Atlas sidecar onto the shared helper (vault-identity guard via vault_root() comparison + inline fallback for older vaults). Surfaces: `memory-doctor.py pending [--json] [--limit] / decide <stem> <decision>`, new `/kennisbank:review` command (human decides per item, command never decides), MCP `review_pending`/`review_decide` (decide only after explicit user confirmation). doctor.sh counter: queue size + decisions (30d); warn on queue >=10 with 0 decisions.

D2 — `/wiki` step 2 (candidate identification) is the last free-form LLM decision point. New `scripts/wiki-scan.py` (pattern: intake-scan/conflict-scan): deterministic candidates from (a) `wiki-kandidaat:` markers in recent session logs (--days 7, date from filename else mtime), (b) `promote_candidate: true` current memories, (c) H2 headings recurring across >=2 logs (template headings excluded); per candidate a find-similar probe (subprocess, fail-soft None); `suggested_action in (herschrijf, nieuw, overslaan)` tuple-validated, fail-safe `overslaan`; above_threshold -> herschrijf; marker/cluster/>=2 logs -> nieuw (probe-less markers still nieuw — /wiki step 3.5 revalidates); JSON with `scanned_logs` as silent-empty guard. Rewrite `/wiki` step 1-2 to follow the scan (deviation only with motivation; keep the literal `01-raw/sessies` mention for the structure test). NOT doing: narrowing memory-sweep enums (TASK-14 trigger never fired).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `decide()` approves/rejects only unverified; skip logs without writing; invalid decision 400; traversal 400; missing 404; state 409; write-failure 500 with unchanged file and no audit line
- [ ] #2 Crash-safety test: failed set_status leaves a consistent, re-decidable state
- [ ] #3 Atlas sidecar uses the shared helper (existing decide tests green) + fallback test for vaults without deployed scripts
- [ ] #4 `/kennisbank:review` + MCP tools expose the queue; the human decides every item; README command tables (EN+NL) updated
- [ ] #5 EVIDENCE: TASK-23 replay test — 31 unverified cleared via the flow, no one-off script
- [ ] #6 wiki-scan deterministic (two runs identical), enum-validated, `scanned_logs` guard; /wiki steps 1-2 follow it
- [ ] #7 EVIDENCE: one shadow week — scan misses nothing a manual run with markers would find; result here
- [ ] #8 doctor.sh counters visible
- [ ] #9 EVIDENCE OF IMPROVEMENT: TASK-23-replay test output + first real /kennisbank:review run on this vault (queue size before/after, decisions logged in memory-review-log.jsonl) + wiki-scan run on the real vault compared against a manual /wiki candidate pass — all numbers recorded here
<!-- AC:END -->
