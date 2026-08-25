# Source Recall and Experience Memory Evaluation Plan

Date: 2026-08-25  
Status: pre-registered; metrics and gates were written before implementation

## Question

Do a provenance-first raw-source retrieval path and an outcome-validated
experience path add useful recall that the existing wiki/memory path cannot
provide, without regressing normal retrieval or presenting weak evidence as
knowledge?

The two hypotheses are independent. One layer may pass while the other fails.

## Test-first rule

Contract tests, fixtures, arm definitions, minimum sample sizes, and winner
rules are committed before feature implementation. Synthetic fixtures verify
mechanics only. Value claims require a frozen holdout drawn from real local
sources and reported as aggregate metrics without committing private content.

## Definitions

* **Source hit**: a returned passage whose stable source id and source hash
  match the labelled source and whose offsets include the labelled evidence.
* **Validated experience hit**: a returned experience with the labelled id,
  `validated` status, and at least one resolvable source/outcome evidence link.
* **False warning**: a failure-prevention warning on a labelled unrelated or
  insufficient-evidence query.
* **Normal path**: current wiki plus memory retrieval with both experimental
  routes disabled.
* **Unknown**: insufficient evidence to assign success, failure, or mixed; it
  is a valid result and not counted as a failure classification error.

## Datasets

### Contract fixtures

Small repository fixtures cover chunk boundaries, exact offsets, duplicate
sources, no-hit queries, conflicting experiences, candidate/unknown status,
and fail-open behaviour. They are not evidence of product value.

### Frozen source holdout

At least 30 query/source pairs from approved live-vault raw sources, with at
least five no-hit queries, five historical/supersession queries, and five
queries whose expected evidence crosses a chunk boundary. Expected source ids
and evidence spans are frozen before the source index is built for the run.

### Frozen experience holdout

At least 20 labelled task/work-unit experiences, including at least five
validated failures, five validated successes, five unknown/candidate cases,
and five unrelated warning probes. Each validated item has independent local
evidence such as a test result, commit/diff, explicit user feedback, or later
reversal. The query author must not see retrieval output before labels freeze.

## Arms

| Arm | Retrieval path | Purpose |
| --- | --- | --- |
| A | current wiki + memory | production control |
| B | lexical-only raw source | cheap source baseline |
| C | hybrid source recall | test source-layer value |
| D | A plus explicit source recall | evidence-answer composition |
| E | lexical-only validated experiences | cheap experience baseline |
| F | hybrid validated experience recall | test experience-layer value |
| G | A plus gated source and experience recall | experimental composed path |
| H | G plus outcome-aware reranking | research-only; never default here |

## Source metrics and winner rule

Report source hit@1, hit@5, mean reciprocal rank, exact provenance precision,
no-hit precision, index coverage, p50/p95 query latency, build duration, and
derived index size.

Source recall passes only if all hold:

1. at least 30 labelled positive queries and five labelled no-hit queries;
2. hybrid source hit@5 is at least 0.70;
3. hybrid source hit@5 improves lexical-only by at least 0.10 absolute, or the
   lexical baseline already reaches 0.85 and hybrid does not regress it;
4. exact provenance precision is 1.00 for every reported hit;
5. no-hit precision is at least 0.80;
6. normal-path p50 and p95 change by less than 5 ms while the route is off;
7. explicit warm source query p95 is below 2 seconds locally;
8. rebuild failure leaves the prior known-good index queryable.

If hybrid does not beat a strong lexical baseline, the vector arm is rejected
and source recall may ship lexical-only or remain a verification tool.

## Experience metrics and winner rule

Report validated experience hit@1/hit@3, success hit@3, failure hit@3, lexical
baseline delta, evidence-link precision, candidate leakage, false-warning rate,
unknown calibration, p50/p95 latency, and coverage.

Experience recall passes the retrieval/usefulness gate only if all hold:

1. at least 20 labelled experiences with the category minima above;
2. validated experience hit@3 is at least 0.70;
3. hybrid hit@3 improves lexical-only by at least 0.10 absolute, or lexical
   already reaches 0.85 and hybrid does not regress it;
4. validated failure hit@3 is at least 0.70;
5. evidence-link precision is 1.00;
6. candidate/unknown-as-validated leakage is zero;
7. false-warning rate is at most 0.10;
8. normal-path latency remains within the same 5 ms off-route bound.

Passing these gates proves retrieval of evidence-bound experience, not improved
future task completion. Claims about fewer repeated failures or better task
outcomes require a later longitudinal paired dataset with at least 30 exposed
and 30 control task/work-units. Until then, outcome-aware ranking and automatic
skill promotion remain rejected.

## Attribution checks

The outcome ledger stores exposure, use evidence, session/task outcome evidence,
and attribution strength separately. Reports may state association only.
An individual memory or source receives a causal helpful/harmful label only
when explicit feedback or a controlled comparison supports it.

## Privacy and mutation controls

* Raw live-vault content never enters committed fixtures or reports.
* Evaluation writes isolated indexes and telemetry databases.
* `KB_USAGE_DISABLE=1` is set for evaluation.
* No evaluation run changes memory status, source files, skills, or production
  usage/outcome counters.
* Reports store aggregate metrics, fixture ids, code revision, configuration,
  model identity, and index fingerprints.

## Stop conditions

Stop and reject or redesign an arm when:

* the oracle source/evidence is absent or cannot be identified reliably;
* provenance cannot be exact;
* normal recall regresses while the route is disabled;
* a candidate or unknown item appears as validated;
* failure warnings exceed the false-positive gate;
* results depend on test-set-specific thresholds or prompt leakage;
* a full rebuild can destroy the prior good index;
* the measured benefit is explainable by lexical lookup alone.

## Evidence packet

TASK-220 produces a versioned report containing dataset counts, frozen hashes,
arm configuration, all metrics, paired deltas, latency distributions, failures,
and a separate go/hold/reject verdict for source and experience recall. The
packet also states which claims remain untested. ADR-010 cannot be accepted
without this packet and explicit owner confirmation.

