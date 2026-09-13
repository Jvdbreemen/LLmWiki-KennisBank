# Outcome telemetry baseline

Date: 2026-08-26
Command: `KENNISBANK_VAULT=<configured-local-vault> python scripts/kb-outcome-report.py`
Mutation: none; read-only SQLite queries.

The current vault returned no structured exposure/outcome pairs. The report
returned empty `by_layer` and `by_item` aggregates and the explicit scope
`association_only`. This is an honest zero baseline, not evidence that
experience recall is useful or useless.

Before experience recall can pass its gate, the recorder must collect a frozen
set of at least 60 labelled work-units: 20 validated failures, 20 validated
successes, 10 conflict/stale or mixed cases, and 10 unknown/unrelated probes.
The downstream action benchmark and paired confidence interval are still
missing. Experience recall therefore remains `hold` and opt-in disabled.
