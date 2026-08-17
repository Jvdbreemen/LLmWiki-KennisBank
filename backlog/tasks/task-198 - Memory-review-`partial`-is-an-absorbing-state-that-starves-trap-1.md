---
id: TASK-198
title: 'Memory review: `partial` is an absorbing state that starves trap 1'
status: In Progress
assignee: []
created_date: '2026-08-17 05:29'
updated_date: '2026-08-17 19:50'
labels:
  - memory
  - autonomous-review
  - regression
dependencies: []
references:
  - scripts/_groundcheck.py
  - scripts/kb-autoreview.py
  - scripts/memory-notify.py
  - scripts/memory-sweep.py
  - docs/superpowers/specs/2026-08-16-autonomous-memory-review-design.md
modified_files:
  - scripts/_groundcheck.py
  - scripts/kb-verify.py
  - scripts/memory-doctor.py
  - scripts/memory-notify.py
  - scripts/memory-sweep.py
  - tests/test_groundcheck.py
  - tests/test_kb_verify.py
  - tests/test_memory_doctor.py
  - tests/test_memory_notify.py
  - tests/test_memory_sweep.py
  - docs/superpowers/specs/2026-08-16-autonomous-memory-review-design.md
priority: high
type: bug
ordinal: 166700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Symptom

Every session start reports `geheugen: 24 unverified memories ouder dan 48u (sweep/judge promoot ze niet - draai /kennisbank:settings of check Ollama)`. Both suggested causes are empirically false: all toggles in `kennisbank-settings.json` are on (incl. `auto_review_llm`), Ollama answers on :11434, and the sweep heartbeat of 2026-08-17T04:51Z reports `errors: 0`, `model_unreachable: false`, `verified_promoted: 2`.

## Root cause

`partial` is a terminal verdict that no code path acts on.

- Trap 1 (`scripts/_groundcheck.py:verify_pass`): `if r["verdict"] != "supported": continue` — partial changes nothing.
- Trap 2 (`scripts/kb-autoreview.py:apply`): promotes `supported`, retracts `absent` + `refuted:false`, and drops everything else into `left_unverified`.

Both are deliberate and documented ("undecidable cases are exactly the ones an autonomous system should not force"). The design assumed such cases get "retried next cycle" and resolve. They cannot: a `partial` verdict is a stable property of the claim-vs-transcript relation, not a coin flip. `docs/superpowers/specs/2026-08-16-autonomous-memory-review-design.md:93` claims "No terminal limbo"; in practice this is exactly terminal limbo.

## Measurements (2026-08-17, vault Kluis)

- All 24 rot memories were in batch `batch-20260816-145620` (134 cases) and **all 24 returned verdict `partial`** — 0 supported, 0 absent. Batch totals: supported 90, partial 42, absent 2; applied 92.
- 89 memories are `unverified` with a source transcript on disk. 40 of the 42 partials are still unverified.
- `VERIFY_PASS_CAP = 40`, and `verify_pass` sorts oldest-first with no record of past verdicts. The cap window is **40/40 known-partial**. The 49 newer unverified memories (2026-08-16 and later) are never reached by trap 1 at all.
- Cost: those 40 are re-judged on every sweep at roughly 6-8 s of local LLM each, producing the same verdict.
- The count only grows: 25 partials dated 2026-08-13 (now rot) plus 17 dated 2026-08-15 that roll past the 48 h cutoff next.

Reconciliation of the three n's: heartbeat `unverified: 34` is a per-run write counter, not a total. `rot_count` uses a strict `created < today - 2d` cutoff, so the 16 memories dated 2026-08-15 are excluded — 40 unverified at >= 2 days minus those 16 = the reported 24.

## Two defects

1. **Starvation** — a growing set of permanently undecidable memories occupies the whole trap-1 budget, so newly captured memories get no grounded check.
2. **Misdiagnosing notification** — the session-start message names two causes that are both fine here and offers no action that resolves the state.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Trap 1's candidate ordering does not starve newly captured memories: given more unverified-with-source memories than `VERIFY_PASS_CAP`, the candidate window is not composed entirely of previously-judged ones
- [x] #2 Memories that trap 1 can still promote keep being judged. Specifically, a trap-2 `partial` does not by itself disqualify a memory from trap 1 -- the two read different inputs (selected 6000-char passage vs whole transcript), and trap 1 currently promotes some memories the client read graded `partial`. That is the only thing draining the queue today and must not be suppressed
- [x] #3 The session-start message distinguishes 'not yet judged' from 'judged and undecidable', and names an action that actually applies to each
- [x] #4 A regression test covers the starvation case: more previously-judged memories than the cap, plus newer unverified ones, asserting the newer ones enter the candidate window
- [x] #5 `python -m pytest tests -q` is green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Trap 1 now keeps its own record of decisive verdicts and uses it to ORDER candidates, never to exclude them.

- `scripts/_groundcheck.py`: `load_attempts()` / `record_attempt()` over `.claude/memory-verify-attempts.json` (compact map, atomic write, capped at 5000 newest). `candidates(max_n, retry_settled)` is now the single selection rule: tier A = no decisive verdict at the current `VERIFY_PROMPT_VERSION`, oldest `created` first; tier B = judged longer than `KB_VERIFY_RETRY_DAYS` (default 7) ago, oldest attempt first so retries rotate. `verify_pass` records every decisive verdict.
- `scripts/kb-verify.py`: dropped its copied selection block in favour of `candidates()`, added `--retry-settled` for the deliberate drain, records nothing on `--dry-run`.
- `scripts/memory-doctor.py`: `rot_breakdown()` splits the rot count into `waiting` / `undecided`; `rot_count()` delegates to it.
- `scripts/memory-sweep.py`: heartbeat carries `rot_waiting` and `rot_undecided` next to the existing `rot`.
- `scripts/memory-notify.py`: one clause per bucket. A heartbeat without the split keys falls back to a message that states the count and names no cause -- a wrong pointer costs more than none.

Deliberate non-choices:
- The attempts map holds trap 1's own verdicts only. Seeding it from the existing trap-2 batch would have suppressed exactly the promotions that still drain the queue.
- Indecisive answers (`unparseable`, `no_transcript`, exceptions) are not recorded, so a briefly dead model cannot cost a batch its cooldown. Unreadable timestamps read as due, so a corrupt record cannot freeze a memory.
- Not stored in memory frontmatter: writing 40 memory files per sweep changes their `semantic_hash` and forces a knowledge-graph re-extraction.

`docs/superpowers/specs/2026-08-16-autonomous-memory-review-design.md` carries a correction under "No terminal limbo", which was wrong as written.

Verification: `python -m pytest tests -q` -> 1591 passed, 3 skipped. Read-only simulation against the live vault: run 1 judges the 40 known partials once with trap 1's own reading, run 2 selects 40 memories dated 2026-08-16/17 with zero overlap. The vault self-corrects after one sweep -- no migration needed.

Not deployed: `$VAULT/.claude/scripts` still runs the pre-fix copy, so the live vault keeps reporting the old message until the tooling is redeployed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-08-17 05:30
---
Scope note: AC#1 states the defect, not a remedy. An earlier draft prescribed 'exclude trap-2 partials from trap 1', which the evidence contradicts -- `verified_promoted: 2` on the 2026-08-17T04:51Z run means trap 1 said `supported` for memories the client read had graded `partial`. Excluding them would suppress the only promotions currently happening. Mechanism is left to implementation.
---
<!-- COMMENTS:END -->
