# Bounded canonical setup health — 2026-09-08

Scope: TASK-241. The supported live deployment entrypoint remains `setup.sh`.
No raw sources, memories, canonical ledger rows, or live client settings were
changed by these tests or the read-only owner-vault check.

## Reproduction before implementation

The shell doctor's projection section read the retired `source_recall` and
`experience_recall` flags, inspected the retired mixed-store schema, and then
called `kb-projection-doctor.py` without `--fast`. Its parser also expected
experience fields at the top level instead of separate `ledger` and
`projection` records. A successful CLI unit test therefore did not prove the
actual setup boundary was correct or bounded.

Five test-first checks produced **4 failed, 1 passed in 2.54 seconds**. The
actual shell section, extracted from `doctor.sh` and executed by Git Bash
against a temporary vault, failed a stub requiring bounded summary arguments.
The failing-command warning control already passed. Three tests also recorded
the absent canonical summary formatter.

## Repair and verification

The shell now makes one `--vault ... --fast --shell-summary` call. The canonical
doctor formats content-free route and health rows, separating the append-only
ledger from the derived experience projection. It reports disabled routes as
information, unreadable stores and forbidden flags as warnings, and does not
print exception details or source text. Shell mode always selects fast checks,
even when `--deep` is also supplied. Ordinary JSON/deep operator mode is retained.

Source schema presence is **not** a successful integrity/provenance check.
Routine output explicitly says source integrity, inventory and exact reference
checks were not performed. Ledger/projection PASS rows refer to the reported
quick integrity check and do not certify practical recall value.

Focused doctor, observability, TASK-209 and collection checks:
**34 passed in 5.26 seconds**. Independent TASK-209 `unittest discover` found and
passed all 17 measurement tests in **0.423 seconds**. Git Bash syntax checking
of `setup.sh` and `scripts/doctor.sh` passed. No test allowlist was expanded.

A read-only owner-vault fast summary returned: 16,286 source documents present
(integrity/inventory not checked), 42 events, 42 outcomes, one review, one
projected experience, and both explicit read routes disabled. These are
point-in-time operational counts, not additional natural canary observations.

## Full-suite evidence remains separately gated

The preceding clean commit `8c323a06be5368e598d8b8edd64af9f660a45d79` completed
with **2,018 passed, four skipped, one failed in 636.13 seconds**. Its only failure
was test discovery: the 17 new TASK-209 tests used module-level pytest functions,
which `unittest discover` could not see. They are now ordinary TestCase methods
with temporary-vault isolation and deterministic cleanup. The product runtime
was not changed by that conversion.

The private JUnit report contains 2,023 tests, zero errors, one failure, four
skips and duration 636.098 seconds. SHA-256:
`cbd249f5f60228df3df079332d48ab8ec489b969a9295ff9763d6c1322499e00`.
It remains in the configured vault's production-canary run directory. The
repaired tree still needs its own clean-commit full-suite pass; focused checks
do not silently replace that gate. Owner experience canary remains 0/20, and
no release or ADR acceptance is implied.
