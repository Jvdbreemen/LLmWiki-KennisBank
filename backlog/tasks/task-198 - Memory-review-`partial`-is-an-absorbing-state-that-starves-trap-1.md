---
id: TASK-198
title: 'Memory review: `partial` is an absorbing state that starves trap 1'
status: Done
assignee: []
created_date: '2026-08-17 05:29'
updated_date: '2026-08-17 21:49'
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
Trap 1 now keeps its own record of outcomes and uses it to ORDER candidates, never to exclude them.

- `scripts/_groundcheck.py`: `load_attempts()` / `record_attempt()` / `record_attempts()` over `.claude/memory-verify-attempts.json`, keyed by vault-relative path (not bare stem: the scan is recursive and `09-memory/archive/` exists). `candidates(max_n, retry_settled)` is the single selection rule: tier A = no outcome from the current `VERIFY_PROMPT_VERSION`, oldest `created` first; tier B = recorded but past its window, oldest attempt first so retries rotate; everything else is skipped this run. `is_settled()` is the one predicate for "trap 1 will leave this alone", shared with the doctor so the pass and the report cannot disagree.
- Two windows. A real verdict holds for `KB_VERIFY_RETRY_DAYS` (7). An inconclusive outcome holds for `KB_VERIFY_RETRY_HOURS` (6), because `unparseable` is about the run while `no_transcript` is deterministic -- an empty source yields an empty passage every time -- and neither may own the cap.
- Nothing is recorded on the promoting branch: a promoted memory leaves the unverified pool, and a refused promote (locked file) is not a settled memory.
- Outcomes are collected during a pass and flushed once, in a `finally`, so bookkeeping is not quadratic and an interrupted run keeps what it learned.
- `scripts/kb-verify.py`: dropped its copied selection block in favour of `candidates()`, added `--retry-settled` for the deliberate drain, records nothing on `--dry-run`.
- `scripts/memory-doctor.py`: `rot_breakdown()` splits the rot count into `waiting` / `undecided`; `rot_count()` delegates. `undecided` requires both that trap 1 will not return to it and that what it returned was a judgement about the claim -- a broken source belongs in `waiting`, where the advice is right.
- `scripts/memory-sweep.py`: heartbeat carries `rot_waiting` and `rot_undecided` next to the existing `rot`. `_rot_count` renamed `_rot_breakdown`.
- `scripts/memory-notify.py`: one clause per bucket, each naming an action that applies. The undecided clause points at `memory-doctor.py pending` / `decide`, NOT `/kennisbank:review` -- that command is the audit-view and cannot move an unverified memory. A heartbeat without the split keys falls back to a message that states the count and names no cause.

Deliberate non-choices:
- The attempts map holds trap 1's own outcomes only. Seeding it from the existing trap-2 batch would have suppressed exactly the promotions that still drain the queue.
- Not stored in memory frontmatter: writing 40 memory files per sweep changes their `semantic_hash` and forces a knowledge-graph re-extraction.
- No lock between the sweep worker and the CLI. Merging on read bounds a concurrent run to losing the other's records, which costs re-judging and never wrong data.

`docs/superpowers/specs/2026-08-16-autonomous-memory-review-design.md` carries a correction under "No terminal limbo", which was wrong as written.

Verification: read-only simulation against the live vault -- run 1 judges the 40 known partials once with trap 1's own reading, run 2 selects 40 memories dated 2026-08-16/17 with zero overlap. The vault self-corrects after one sweep; no migration needed.

Not deployed: `$VAULT/.claude/scripts` still runs the pre-fix copy, so the live vault keeps reporting the old message until the tooling is redeployed. That is the `/kennisbank-upgrade` path and the owner's call.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-08-17 05:30
---
Scope note: AC#1 states the defect, not a remedy. An earlier draft prescribed 'exclude trap-2 partials from trap 1', which the evidence contradicts -- `verified_promoted: 2` on the 2026-08-17T04:51Z run means trap 1 said `supported` for memories the client read had graded `partial`. Excluding them would suppress the only promotions currently happening. Mechanism is left to implementation.
---

created: 2026-08-17 20:08
---
Own /code-review (high) on the branch diff produced 7 findings, all verified against the code before acting on any of them. All 7 fixed.

1. HIGH -- the new message named `/kennisbank:review`, which cannot do what the message says. Confirmed by reading `commands/kennisbank/review.md`: it calls itself "GEEN werkwachtrij meer - het is de audit-view" and offers only `demote` and `reopen` over the promotion and closure logs. An unverified memory appears in neither log. This replaced one wrong pointer with another, the exact defect class this task exists to remove. Now names `memory-doctor.py pending` and `decide <stem> approve|reject|skip`, the only path where a person moves an unverified memory (`_memory.decide` refuses any status but unverified). Same claim corrected in the `rot_breakdown` docstring and the spec.

2. MEDIUM-HIGH -- the `undecided` bucket treated any record as final while `candidates()` requeued on a prompt-version mismatch or an elapsed cooldown, so the message claimed 'decide by hand' about work the next sweep was about to redo. Both now share one predicate, `_groundcheck.is_settled`.

3. MEDIUM -- the verdict was recorded before `_memory.promote` and regardless of its result, so a refused write (locked file, ordinary on Windows with a sync client) parked a memory trap 1 wanted to promote for a week with nothing in the promote log. Nothing is recorded on the promoting branch at all now: a promoted memory leaves the unverified pool, and a refused promote is not a settled memory.

4. MEDIUM -- `record_attempt` did a full read-modify-write per verdict, quadratic on a full drain. Outcomes are collected during the pass and flushed once through `record_attempts`, in a `finally` so an interrupted run still keeps what it learned.

5. LOW-MEDIUM -- fail-open on a corrupt attempts file returned {} and the next write erased the history. The unreadable file is moved to `.corrupt` first.

6. LOW -- lost updates between the sweep worker and the CLI. Merging on read bounds it: the run finishing second keeps its own records and loses at most the other's, which costs re-judging and never wrong data. Documented in `record_attempts` rather than adding a lock.

7. MEDIUM -- not introduced here but not closed either: `no_transcript` is deterministic, not transient. An empty or truncated source yields an empty passage on every run, so those memories stayed in the never-judged tier forever and the `created` sort parks them at the head of the queue -- the same starvation from the other side. Inconclusive outcomes are now recorded under a short window (`KB_VERIFY_RETRY_HOURS`, default 6) so a dead model costs hours while a permanently broken source cannot own the cap.

Re-verified read-only against the live vault after the changes: run 1 judges the 40 known partials once, run 2 selects 40 memories dated 2026-08-16/17, overlap 0.
---

created: 2026-08-17 20:41
---
Copilot review on PR #5 (fork): check-run `completed / success`, 5 inline comments, all verified against the code and all accepted.

- Four of them are the same defect in four places: I wrote `decide <stem> approve|reject` while `memory-doctor.py` documents `approve|reject|skip` (usage at lines 360 and 390). Corrected in `memory-notify.py`, the `rot_breakdown` docstring, the spec and this task file. Worth noting that this is the third variant of the same failure in one branch -- naming a path without checking what it actually accepts.
- A Dutch typo in the `rot_breakdown` docstring: `dat command` -> `dat commando`.
- `tests/test_kb_verify.py` was written in Dutch while AGENTS.md sets English as the default for code comments. Translated. The Dutch additions to `tests/test_memory_doctor.py` and `tests/test_memory_notify.py` are deliberately left as they are: those files are Dutch throughout and predate this branch, so matching them keeps each file internally coherent. Converting them is separate work, not this task's.

Process note for next time: Copilot does not appear under `requested_reviewers`, it appears as a `copilot-pull-request-reviewer` check-run. Checking the wrong field led me to report the review as absent when it was in progress. Poll the check-run, not the reviewer list.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Shipped in v0.34.0 (`110d57e`).

Trap 1 had no memory of what it had already judged, and a verdict is a property of claim-against-passage rather than a coin flip, so `partial` came back `partial` every sweep. Measured: all 24 memories past the rot cutoff had been graded `partial` by a whole-transcript client read; together with 16 younger ones they held 40 of 40 slots of `VERIFY_PASS_CAP`, so 49 newer memories were never judged at all and the same 40 were re-judged every run at 6-8 s of local model each. The session-start message reporting this named `/kennisbank:settings` and Ollama, both demonstrably fine.

Trap 1 now records its outcomes in `.claude/memory-verify-attempts.json` and orders candidates in two tiers. It orders, it never excludes: trap 1 reads a selected passage where the client reads the whole transcript, so it still promotes memories the client graded `partial`, and those were the only promotions still draining the queue.

Verified read-only against the live vault: run 1 covers the 40 known-undecided memories, run 2 covers 40 dated 2026-08-16/17 with zero overlap. No migration.

Reviewed twice before landing. Own `/code-review` found 7 issues, Copilot 5; all 12 were checked against the code and fixed. Three of them were the same mistake in different clothes -- naming a path without checking what sits at the other end -- which is the defect this task is about, committed while fixing it.

Not yet deployed to the vault at close time: `/kennisbank-upgrade` from the new tag does that.
<!-- SECTION:FINAL_SUMMARY:END -->
