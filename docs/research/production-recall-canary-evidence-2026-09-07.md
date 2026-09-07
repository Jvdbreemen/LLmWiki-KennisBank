# Production source/experience recall evidence — 2026-09-07

Branch: `codex/source-grounded-experience-production`

Task: TASK-236

Decision boundary: evidence packet only; no rollout or ADR acceptance

## Current decision

**Hold.** The production mechanics, locked experience regression, source
owner-canary, latency, failure recovery, privacy boundary, and normal-route
isolation pass. The experience owner-canary has zero of the required twenty
naturally occurring explicit recalls because the configured owner vault has no
canonical experience ledger or projection. Copying the old evaluation database
into production would not fix that: it contains curated projection rows rather
than append-only events plus content-hash-bound owner reviews.

All four feature flags remain off. No release or ADR transition is authorized
by this packet.

## Evidence classes

### Prior, spent evidence

The frozen 70-case experience holdout was run once before this production
cycle. Its content-bound report remains immutable and was verified in place,
not rerun or tuned:

| Binding or metric | Result |
| --- | ---: |
| holdout input SHA-256 | `0f5881ee6181fe8d9df94ea2779a1404ab71403dca61c7b29fccd443e36208be` |
| aggregate report SHA-256 | `5605f249927b370b9424a1d0ad75d0b10691a5a707c440179df2f65bccff3954` |
| hybrid hit@3 | 0.900 |
| validated failure-attempt hit@3 | 0.931 |
| evidence precision | 1.000 |
| candidate leakage | 0 |
| warm p95 | 129.338 ms |

This satisfies the locked regression thresholds of hit@3 at least 0.85,
evidence precision 1.00, candidate leakage zero, and experience p95 at most
250 ms. It is regression evidence only. It is not a new holdout result and not
owner-canary evidence.

The prior blinded paired action experiment also remains relevant value evidence:
experience context produced 43/60 correct actions versus 19/60 for baseline,
delta +0.40, 95% bootstrap interval +0.20 to +0.5833. That positive value result
does not erase the old automatic-advisory false-warning failure of 2/10. The
production design therefore removed automatic advisory, ranking, injection,
and promotion routes rather than averaging that safety failure away.

### Current production regression evidence

The current branch ran the locked retrieval fixture, exact hydration, source
and experience projection rebuild/recovery, interrupted migration, policy,
and canary contracts together:

```text
57 passed in 10.85s
```

The subsequent shadow-capture audit found that `kb-outcome.py` still wrote to
the retired mixed store and did not enforce `experience_capture`. That means
the earlier mechanics were insufficient for a real canary even though the
retrieval-side tests passed. The repair is test-first and deliberately does
not count as a natural canary case:

- session outcomes now obey the capture flag of the same explicitly resolved
  vault and append an idempotent observation plus outcome to the canonical
  ledger;
- `kb-experience-capture.py` accepts private JSON on stdin, creates exact
  structured SourceRefs from approved vault-relative ranges, rejects
  ungrounded or content-leaking shapes before writing, and returns only opaque
  ids and counts;
- extraction now preserves attempt, resolution, and final outcome as separate
  states instead of defaulting the first two away;
- a synthetic closed-gate proof completed capture -> success outcome -> exact
  content-hash owner review -> atomic lexical rebuild with one
  `validated/verified/accepted` record and zero candidate leakage;
- 236 source/experience/projection/outcome/policy regressions passed, with one
  existing Windows symlink fixture skipped; deployment of the new capture
  script through a temporary real setup passed in 68.63 seconds.

This closes the mechanism needed to start prospective shadow capture. It does
not manufacture the required twenty naturally occurring recalls, and it does
not justify turning on a flag in the owner vault by itself.

The privacy boundary separately passed 17 tests. They reject tracked private
eval sets, content-bearing canary fields, query/path telemetry, changed reuse of
an idempotency key, and reports containing per-case identifiers.

Failure injection proves:

- an interrupted ledger migration leaves the previous good ledger byte-for-byte
  intact;
- failed source and experience rebuilds leave the previous good indexes intact;
- an unavailable or incompatible embedding path publishes or serves the labelled
  lexical fallback rather than a partial vector index;
- normal recall and disabled routes remain fail-open.

### New owner-vault canary evidence

Ten deterministic positive cases were selected from the existing frozen,
owner-reviewed source oracle. On the live configured vault, each stored source
hash was checked, a structured SourceRef was created from its reviewed window,
and the production `reconstruct` gateway hydrated it. Only opaque ids, counters,
latency, and owner verdict metadata were written to the private append-only log.

| Source owner-canary metric | Result | Gate |
| --- | ---: | --- |
| owner-reviewed exact reconstructions | 10 | pass, minimum 10 |
| correct byte-exact reconstructions | 10/10 | pass |
| shown passages | 10 | observation |
| provenance precision | 1.000 | pass |
| candidate leakage | 0 | pass |
| first-read p50 / p95 | 13.631 / 56.314 ms | observation, cold mixed-file read |
| warm exact-hydration p95, 100 calls | 16.671 ms | pass, maximum 50 ms |
| warm source FTS p95, 100 calls | 129.071 ms | pass, maximum 250 ms |

The source flag was restored to its prior off value in a `finally` block. The
private rows remain under the configured vault's
`06-claude/evaluations/production-canary/` directory and are not tracked.

The experience canary has not begun:

| Experience owner-canary metric | Result | Gate |
| --- | ---: | --- |
| naturally occurring explicit recalls reviewed | 0/20 | **fail/incomplete** |
| useful rate | unmeasured | **fail/incomplete**, minimum 70% |
| harmful rate | unmeasured | **fail/incomplete**, maximum 5% |
| evidence precision | unmeasured | **fail/incomplete**, required 100% |
| candidate leakage | no eligible exposure | not claimed as positive evidence |

The recorder deliberately treats a zero-case harmful rate as unmeasured and
failed, not as a vacuous safety pass. Eval prompts and retrospective replays are
labelled non-natural and cannot satisfy the twenty-case gate.

## Normal-route compatibility and overhead

With both explicit-recall flags off, 5,000 calls per gateway returned the exact
`{"status":"not_routed","hits":[]}` shape. Compared with construction of the
same baseline result, p95 overhead was 0.0020 ms for source and 0.0021 ms for
experience, both below the 1 ms production bound. Neither normal route opened a
projection or invoked embeddings.

## Acceptance matrix

| TASK-236 criterion | State | Evidence |
| --- | --- | --- |
| #1 canary provenance 100%, leakage zero | partial | source 10/10 and zero leakage; experience canary absent |
| #2 locked experience hit@3 and precision | pass | immutable 70-case aggregate verified by hashes; no rerun |
| #3 normal compatibility and <=1 ms p95 | pass | exact shape, +0.0020/+0.0021 ms p95 |
| #4 route latency budgets | pass | experience 129.338, source FTS 129.071, hydration 16.671 ms p95 |
| #5 fail-open and previous-good recovery | pass | focused failure-injection suite green |
| #6 ten source reconstructions before experience | pass | 10/10; experience canary not started |
| #7 twenty natural experience reviews | **fail/incomplete** | 0/20; no canonical owner-vault experience data |
| #8 sanitized aggregate packet | pass | this packet plus privacy/canary contracts |
| #9 full suite and all client smokes | pending | focused/client smokes pass; isolated current-HEAD full suite still required |

## Reproduction boundary

The content-safe status command is:

```bash
python3 "$KENNISBANK_VAULT/.claude/scripts/kb-projection-canary.py" report
```

Per-case recording is documented in
`commands/kennisbank/projection-canary.md`. Keep the JSONL and any source or
experience content inside the configured vault. Only the aggregates in this
document belong in Git.

## Next evidence required

1. Deploy the feature-branch tooling under controlled shadow capture and build
   a canonical ledger from newly captured typed events and outcomes; do not
   import curated eval projection rows as canonical history.
2. Let the owner review candidates against exact SourceRefs and outcome refs,
   then atomically build the disposable experience projection.
3. Collect twenty naturally occurring, explicit experience recalls and record
   usefulness, harm, evidence correctness, leakage, and latency independently.
4. Keep the decision at hold if any safety rate fails. Only after the complete
   canary and current-HEAD full/client suites are green may TASK-237 present an
   accept/amend/reject choice to the owner.
