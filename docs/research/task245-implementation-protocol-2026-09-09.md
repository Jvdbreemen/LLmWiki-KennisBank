# TASK-245: implementation and evaluation protocol

Status: frozen before policy implementation and before new holdout inspection.

## Candidate design

Keep the existing explicit experience route and local embedding backend.
Separate candidate retrieval from applicability: compare a cheap typed lexical
support/cosine filter with a bounded local semantic evaluator where feasible.
Do not threshold rank-fusion scores or select thresholds on the 70 spent cases.
Cross-encoders are plausible but add per-pair inference and deployment cost;
see [Sentence Transformers](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html)
and [OpenSearch's RRF explanation](https://docs.opensearch.org/latest/vector-search/ai-search/hybrid-search/rrf/).

Mixed raw/wiki bundles retain original references. An explicit evaluation audit
may identify a wiki citation as supplementary only when exact raw evidence
already supports the bounded lesson. Production raw roots and human-review
requirements remain unchanged. This follows the distinction between primary
source and derivation in [W3C PROV](https://www.w3.org/TR/prov-o/).

## Data and independence

- Reproduce the 13 historical exclusions; retain all60 in the old denominator.
- A separate worker creates new auto-authored, raw-source-grounded fixtures
  from sources absent from the historical corpus. Target 12 lessons divided
  into source-disjoint development and held-out groups. Target each split:
  18 positive paraphrases and 18 nearby unsupported questions. Report smaller
  truthful counts if credible source evidence cannot meet this target.
- The implementation/calibration worker may see development data only.
  Holdout hashes are sealed before selection; no threshold search after opening.
- Auto-authored fixture labels are not canonical human reviews and do not
  establish naturally observed usefulness/harm or downstream task success.
- If no policy clears development constraints, do not spend the holdout or
  deploy a failing heuristic. Preserve candidate results and report the gap.

## Gates

Positive hit@3 >=0.85; negative no-hit specificity >=0.90; exact evidence
resolution 1.00; candidate/raw-data leakage zero; state-label preservation.
Unavailable/evaluator failures are not correct abstentions. Keep full
denominators; distinguish candidate-pool misses from applicability rejections.
Do not conflate abstention and harmful answer-generation rates.

Warm gateway p95 <=250ms both in an ordinary run and a documented concurrent
maintenance/load run. Measure direct embedding-plus-gateway latency separately,
not a sum labelled as an observed end-to-end request. Repeated diagnostics do
not erase an earlier failure. No unbounded connection caches or stale-index
reuse, no normal-route dependency on an evaluator.

## Work isolation

All private records/queries/refs and measurement artifacts stay in the active
vault evaluation directory. Telemetry is disabled for experiments; canonical
ledger/reviews/settings are not modified. Feature branch only; no deployment,
main merge or release. New tests precede their production fixes. Reports retain
hashes for code, data, policy and failed as well as successful runs.

## Research and model choice

Two research rounds covered candidate relevance evaluation, provenance roles,
RRF score semantics, local rerankers and SQLite extension lifetime. The full
ten-source research note is in the operator's Claude research directory:
`2026-09-09-experience-recall-applicability.md`.
Luna sidecars handle bounded profiling, raw-bundle auditing and separately
sealed evaluation authoring; the parent reviews implementation and evidence.
This changes development-agent allocation, not the vault's local models.
