# Production source/experience recall evidence — 2026-09-07

Branch: `codex/source-grounded-experience-production`

Task: TASK-236

Decision boundary: evidence packet only; no rollout or ADR acceptance

## Current decision

Update 2026-09-09: the [independent automated evaluation](automated-experience-regression-evidence-2026-09-09.md)
now supersedes the current-acceptance interpretation of the historical locked
retrieval and latency results below. It found mixed-provenance coverage gaps,
0/10 correct negative abstentions and an under-load latency failure. TASK-236
AC2/AC4 are reopened; TASK-245 tracks fixes. The dated measurements below are
preserved, not retroactively changed. The automated evaluation required no new
owner labels and is complete; it did not manufacture natural-use observations.

**Hold.** The production mechanics, locked experience regression, source
owner-canary, latency, failure recovery, privacy boundary, and normal-route
isolation pass. The experience owner-canary has zero of the required twenty
naturally occurring explicit recalls. The configured owner vault now has a
canonical ledger and, after explicit owner review on 2026-09-08, one accepted
source-grounded task experience in a lexical shadow projection. Copying the old evaluation database
into production would not fix that: it contains curated projection rows rather
than append-only events plus content-hash-bound owner reviews.

Shadow capture and projection building are enabled; both explicit read flags
remain off. The dated snapshots below preserve their original observations.
No release or ADR transition is authorized by this packet. Full-suite evidence
below is bound to `468acd1`; a later run has no recoverable final result and is
not claimed as a current-HEAD pass.

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

The definitive complete Python repository suite ran alone on clean commit
`468acd1`, with no concurrent client or frontend jobs:

```text
1991 passed, 4 skipped in 857.54s (0:14:17)
```

The four skips are existing platform or optional-capability skips. There were
no failures or timeout reports. This current-commit run includes cross-client
install/generated-artifact, MCP-wire, setup, and recovery smokes. The unchanged
Atlas frontend had separately passed TypeScript compilation and all 39 tests in
this branch cycle. The npm install reported six pre-existing audit findings
(three moderate, three high); no automatic dependency mutation was performed.

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

### Owner-vault shadow-capture activation

After the capture repair and complete suite passed, the owner vault was checked
before mutation. It had no canonical experience ledger or projection and did
not yet contain the production capture/review scripts. A narrow shadow cohort
was deployed with a timestamped local backup of the prior settings and
session-end coordinator. All ten copied script hashes matched clean feature
commit `468acd1`; the existing coordinator received only the fail-open
post-capture outcome job rather than a wholesale client reinstall.

The resulting live flag state is intentionally asymmetric:

| Capability | State |
| --- | --- |
| experience capture | enabled |
| experience projection build | disabled |
| explicit experience recall | disabled |
| explicit source recall | disabled |

A pre-enable invocation returned `disabled`. After enabling capture, an empty
invalid event returned exit 2 with a bounded validation reason. Neither smoke
created a ledger. All deployed modules compiled, and no synthetic event was
inserted. Future session-end outcomes can now accumulate prospectively; useful
candidate content must still be source-grounded explicitly and owner-reviewed.

A default doctor run was stopped after more than five minutes while hashing the
full 16,318-file, approximately 0.82 GiB raw-source inventory. It made no
mutation and is not counted as a pass. This exposes a scale-cost in the doctor
path, not a capture or recall failure. The added `--fast` mode then completed
read-only in 546.8 ms. It reported the source store present with 16,286 manifest
documents, both experience stores absent, both read routes disabled, and
`mutated=false`; expensive inventory, source integrity, chunk, and exact-ref
fields were explicitly `not_checked`/null. Exact full/deep checks remain an
off-hot-path operation.

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
| #7 twenty natural experience reviews | **fail/incomplete** | 0/20; one approved corpus experience is not a natural recall |
| #8 sanitized aggregate packet | pass | this packet plus privacy/canary contracts |
| #9 full suite and all client smokes | pass | clean `468acd1`: 1991 passed, 4 skipped; client smokes included; unchanged Atlas 39/39 |

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

1. Continue controlled shadow capture, now active, and source-grounded corpus
   preparation. Do not import curated eval projection rows as canonical history.
2. Let the owner review candidates against exact SourceRefs and outcome refs,
   then atomically build the disposable experience projection.
3. Collect twenty naturally occurring, explicit experience recalls and record
   usefulness, harm, evidence correctness, leakage, and latency independently.
4. Keep the decision at hold if any safety rate fails. Only after the complete
   canary and current-HEAD full/client suites are green may TASK-237 present an
   accept/amend/reject choice to the owner.

## Live corpus-preparation follow-up

A read-only baseline found 33 events, 33 outcomes, and zero reviews. A private
operator preflight resolved seven exact SourceRefs before any ledger write.
One bounded task candidate and its observed outcome were then appended from
archived raw evidence; all pre-existing events/outcomes and the review table
were preserved. An immediate replay created no duplicate. The initial failure
and subsequently validated repair remain separate fields; the existing mixed
session outcome was not rewritten. Scope limitations remain in the candidate.

The post-append fast doctor reported 34 events, 34 outcomes, zero reviews,
quick integrity OK, absent projection, and both read routes disabled. Source
inventory and deep integrity were explicitly not checked. Exact validation of
this candidate succeeded, but its status remains candidate/unreviewed. Private
source text, identifiers, preparation script, and pending review packet remain
in the vault, outside Git. This retrospective corpus preparation contributes
zero natural explicit-recall observations.

The live canary report still shows source 10/10 and experience 0/20. Focused
capture, review, extraction, and canary regressions passed: **30 passed in
2.70s**. No production code, retrieval flags, owner decisions, or release state
changed during this follow-up.

## Follow-up 2026-09-08

One bounded candidate received explicit owner acceptance bound to its unchanged
content hash. Seven exact refs were revalidated; the shadow projection contains
that one record and excludes forty unreviewed candidates. Details and the
test-first build-capability repair are in
`projection-build-capability-evidence-2026-09-08.md` (TASK-239).

A separate adversarial check found that default grounded verification could
implicitly search sources when the explicit source flag was enabled. This is
repaired with red/green promotion-isolation evidence under TASK-240 in
`explicit-source-verification-boundary-2026-09-08.md`. Neither repair advances
the 0/20 natural experience canary. Current full-suite proof remains open.
