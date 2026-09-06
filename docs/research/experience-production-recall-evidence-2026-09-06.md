# Experience recall production evidence — 2026-09-06

## Product contract

The public route accepts explicit recall only. It searches a disposable
projection containing records that are simultaneously `validated`, backed by
verified exact SourceRefs and outcome evidence, and accepted by a human owner.
Normal recall does not call this gateway and the former `failure` advisory mode
returns `policy_disabled` before settings, storage, or embeddings are touched.

The response is deliberately smaller than the stored experience. It contains
the reusable lesson, applicability and separate attempt/resolution/outcome
states, scores, a validation stamp, and SourceRef ids. It does not contain raw
source passages or full structured SourceRefs. A caller must explicitly invoke
source recall to resolve an id to evidence.

## Retrieval and degradation evidence

- Compatible embedding model and dimensions: hybrid dense plus FTS retrieval,
  labelled `hybrid`.
- Missing embedding backend, failed query embedding, incompatible model id or
  incompatible dimensions: FTS-only retrieval, labelled `lexical_fallback`.
- A projection rebuild where any document embedding fails publishes a complete
  lexical projection rather than a partial hybrid index. The report preserves
  the failed experience ids and labels `vector_status=lexical_fallback`.
- Public output is capped at three and greedily excludes duplicate task/source
  groups.

## Automated evidence

The focused ledger, validation, review, projection, retrieval, migration,
evaluation, CLI and policy run completed with 74 passed tests. One intentionally
red TASK-233 settings-split contract was deselected because it belongs to the
next backlog item.

The locked reviewed regression fixture reports hybrid hit@3 `1.00`, evidence
precision `1.00`, zero candidate leakage and zero false warnings. It has two
positive synthetic cases and one negative probe, so it is a regression guard,
not evidence of end-user value and not a substitute for the frozen owner set.

Warm end-to-end gateway timings on the reference machine, each after one warmup:

| Route | Runs | Median | p95 | Max | Budget |
| --- | ---: | ---: | ---: | ---: | ---: |
| hybrid | 100 | 5.346 ms | 6.338 ms | 7.117 ms | 250 ms |
| lexical fallback | 100 | 3.355 ms | 5.375 ms | 6.198 ms | 250 ms |

The benchmark fixture is a one-record temporary projection. It proves bounded
gateway overhead but not large-vault utility or ranking quality.

## Unspent evidence and remaining risk

The configured owner vault currently contains no experience ledger, projection,
or legacy experience database. No owner-vault migration or canary was therefore
performed in this task. The private frozen holdout was not opened or spent and
no threshold was tuned against it. TASK-236 remains the one-shot value test;
until then the capability stays off and this work establishes production
mechanics, not a positive product verdict.
