---
id: TASK-90
title: 'Structural hardening from ecosystem failure modes (Spoor E)'
status: To Do
assignee: []
created_date: '2026-07-28 08:00'
labels:
  - hardening
  - lint
  - llm-wiki-adoption
dependencies: []
ordinal: 96400
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The most expensive lessons mined from production issue trackers across the LLM-wiki ecosystem (llm_wiki 155 issues, Arkon, Pratiyush, geronimo-iia), each replayed as a fixture test:

- E1 Aggregate audit — "render views, don't prompt them": inventory every artifact an LLM (re)writes wholesale as aggregate/catalog. Prior audit verdict: kb-orientation.py = pure SQL (rendered); 02-wiki index.md/log.md = not generated (absent by design); /weeklog = deterministic rollup. No attack surface today; standing rule: any future regeneration must be atomic (temp+rename) with a snapshot (llm_wiki #536: 436 pages corrupted by one truncated index rewrite; mindbase rollback pattern).
- E2 Index-drift lint (advisory): ghost docs in kb-index.db (indexed paths gone from disk) surfaced by kb-lint — best-confirmed failure mode of the field (llm_wiki #580, Pratiyush `index_sync`, Arkon dashboard-vs-linter).
- E3 Deterministic post-pass: `scripts/kb-normalize.py` — idempotent form normalization after every LLM write in /wiki (step 4.4) and /reconcile (step 3.5): path-prefixed wikilinks -> bare stems (05-bronnen paths kept per kb-lint contract), backslashes -> forward slashes, bare tags line -> list; byte-preserving outside normalized spots (llm_wiki #576: deterministic = always right, prompted = always wrong, same file).
- E4 Pre-write gates: (a) refusal/empty-evidence gate in `_extract` — REFUSAL_MARKERS + `looks_like_refusal()`; refusal candidates dropped before persisting (arkon#25: "I cannot answer this" stored as canonical page content); (b) no runtime downloads — socket-blocked test proving deterministic ingest paths (intake-scan, wiki-scan, provenance) make zero network calls (arkon#29).
- E5 Producer provenance: `model_id` + `prompt_version` (EXTRACT_PROMPT_VERSION constant, bump per template change) stamped on sweep-written memories via `_memory.render(model_id=, prompt_version=)`; sweep `_producer_id()` = `<provider>/<model>` from _llm. Bi-temporal covers when; this covers what produced it.
- E6 Epistemic axis: KennisBank's axis lives in the LAYERS (01-raw/05-bronnen = source; 02-wiki = knowledge; 09-memory = conclusions); missing piece was enforcement. New kb-lint `self-source` rule (HARD): provenance links inside `## Sessie-herkomst` to `02-wiki/`, `09-memory/`, `.claude/`, `06-claude/` rejected — a stored conclusion never re-enters as evidence (llm_wiki #538's self-confirmation loop, invisible to any judge or stale-check).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Aggregate audit recorded with per-artifact verdict; atomic+snapshot rule documented
- [ ] #2 kb-lint self-source (HARD) + index-drift (advisory) rules with fixtures; index-drift excluded from warned/clean counts
- [ ] #3 kb-normalize.py idempotent (two runs byte-identical), wired into /wiki and /reconcile, with #576 fixture tests
- [ ] #4 Refusal gate with arkon#25-replay fixture; structural field validation stays fail-closed in _memory.render
- [ ] #5 Socket-blocked no-network-during-ingest test
- [ ] #6 model_id + prompt_version roundtrip test; absent by default on human-typed memories
- [ ] #7 Epistemic-axis decision recorded; self-source rule fixture-tested
- [ ] #8 EVIDENCE OF IMPROVEMENT: each gate proven by a replayed-failure fixture (arkon#25 refusal, #576 normalization, #538 self-source, #580 index-drift) PLUS one run of kb-lint + kb-normalize --check on the real vault with finding counts recorded here (evidence the gates catch real-world material, not only fixtures)
<!-- AC:END -->
