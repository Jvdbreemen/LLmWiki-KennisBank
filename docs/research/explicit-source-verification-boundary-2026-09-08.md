# Routine verification and explicit source authority — 2026-09-08

Scope: TASK-240. No owner-vault memory was promoted, changed or deleted by the
diagnosis or tests. The private source/experience read flags remain off.

## Reproduction

`_groundcheck.verify_pass` and `kb-verify.py` call `verify_grounded` without a
source callback. Previously, when the supplied transcript yielded no passage,
`verify_grounded` selected `source_recall_passage` implicitly. With the explicit
source flag enabled, that helper could search a different raw source and supply
it to the routine grounded judge. An explicit-only capability consequently also
authorized automatic source fallback.

Two new fixture tests failed before implementation: one observed an implicit
source-helper call; the second promoted one unverified memory through the
routine pass using mocked replacement source evidence. The deliberately
supplied callback control still passed. Red: **2 failed, 1 passed, 20 deselected
in 1.07s**.

## Repair and evidence

Removed only implicit callback selection. Default verification remains limited
to its supplied transcript and returns `no_transcript` when evidence is absent.
An internal caller that deliberately supplies a source callback retains the
labelled `source-recall` route. Public explicit source CLI/MCP behavior is
unchanged; an explicit read flag does not alter routine memory verification.

The focused grounded/source/policy/measurement set passed **59 tests in 4.19s**.
These are mechanism and isolation tests, not new owner-canary observations.
Current full-suite evidence remains a separate acceptance requirement.
