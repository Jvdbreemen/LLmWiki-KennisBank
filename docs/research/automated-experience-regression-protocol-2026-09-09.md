# Automated experience evaluation protocol (TASK-244)

Freeze before execution. This is an engineering regression replay of the
previously owner-reviewed 70-case corpus (60 positive, 10 negative), not a new
holdout or a natural-use canary. No thresholds are tuned during this run.

Run the current explicit gateway over an isolated projection. The historical
database predates structured SourceRefs and the production review contract.
An evaluation-only adapter may convert its legacy refs only if the frozen
source hash and reviewed range still match the original bytes. Accepted fixture
labels represent the historical reviewed corpus; they never become reviews in
the owner's canonical ledger. Report exclusions against the full denominator.
Reuse historical document vectors only when the indexed text exactly matches;
embed queries with the configured local production model. Run lexical and
hybrid arms on identical inputs and report fallback/failed embeddings separately.

Predeclared gates: positive hit@3 >= 0.85; exact evidence precision 1.00 on
shown references; candidate leakage zero; correct attempt/resolution/outcome
state for every correctly retrieved expected experience; warm gateway p95 <=
250 ms. Measure query embedding time separately from the warm retrieval timing.
Report negative no-hit specificity against a diagnostic target of 0.90. This
target evaluates explicit search abstention, not the removed advisory mode.
Any failed gate stays failed; successful policy rejection is a separate result.

Negative controls exercise malformed, stale, missing and redacted SourceRefs,
disabled routing, and prohibited advisory modes. Sources are read only;
negative evidence fixtures change reference objects or isolated files only.
Audit the owner ledger/projection counts and eligibility without promoting
candidates. Check all exact refs attached to the current public projection.

Measure ranking independently from action utility. Existing blinded action
judgments may be rescored with the historical scorer for consistency, identified
as prior evidence. Do not infer new task completion, useful/harmful judgments,
or causality from retrieval hits or model opinions.

Private rows, queries, references, vectors and evaluation indexes remain under
the configured vault's evaluation directory. Repository evidence contains
aggregate metrics, hashes and code revision only. Disable all usage telemetry.
Hash-bind frozen inputs before/after; report current owner state as a snapshot
because regular maintenance may continue concurrently.
