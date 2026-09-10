# Independent automated experience evaluation — 2026-09-09

## Decision

**The automated evaluation is complete; release acceptance is not.** Experience
recall still has positive evidence of value, and exact source reconstruction
works. However, the current production contract cannot reproduce the old
coverage claim unchanged, and explicit search does not reliably abstain when
there is no suitable experience. These are engineering findings, not a request
for the owner to label another batch of questions.

Tracking: TASK-244 (evaluation), TASK-245 (follow-up), TASK-236 (release evidence).
Branch: `codex/source-grounded-experience-production`.
Production code evaluated: `1cca6a2b087521105fdddcd897967f2d8c9e8536` (runtime
unchanged since `b74a008`). New evaluation harness is bound separately below.

## Method and boundaries

The [protocol](automated-experience-regression-protocol-2026-09-09.md) was written
before execution. Tests first failed because the harness did not exist, then
passed after implementation. The current public experience gateway processed
the previously owner-reviewed 70 questions: 60 positive and 10 negative. This
is an explicitly labelled **historical regression replay**, not a new holdout.
No ranking threshold, case, answer label or production code was tuned.

Both arms used the same isolated projection. Historical document vectors were
reused only after an exact indexed-body comparison and model-ID/dimension
checks. All 70 query vectors were newly obtained from the configured local
`ollama:qwen3-embedding:4b` backend (2,560 dimensions), with no failed requests
and no hybrid-to-lexical fallback. Historical model weights were not separately
fingerprinted, so model-ID equality is not proof of identical model binaries.

An evaluation-only adapter converted old reference strings to structured
SourceRefs, preserving the frozen byte hash and the original reviewed range.
It accounts for the old universal-newline offsets versus the new raw Unicode
offsets. Accepted review labels apply only to these historical fixtures; no
canonical owner review, event, outcome or lesson was created or promoted.

The explicit-read flags were enabled only inside the evaluation process.
Telemetry was disabled. Frozen inputs and owner databases were opened read-only;
new indexes and private result packets live under the vault's evaluation folder.
Regular maintenance continued concurrently. All four frozen input hashes were
unchanged afterwards. The owner snapshots were also equal: 62 events, 62
outcomes, one review, one eligible projected experience, seven valid exact refs.
These counts are corpus preparation, not 62 successfully reusable lessons.

## Measured results

| Check | Lexical only | Hybrid | Predeclared criterion |
| --- | ---: | ---: | --- |
| Expected experience in top three, full denominator | 37/60 (61.7%) | 42/60 (70.0%) | >=85%: both fail |
| Conditional retrieval within 47 eligible fixtures | 37/47 (78.7%) | 42/47 (89.4%) | Diagnostic only; does not replace full denominator |
| Correct no-hit on negative questions | 0/10 | 0/10 | Diagnostic target >=90%: both fail |
| Exact reference resolution | 443/443 | 449/449 | 100%: pass |
| Attempt/resolution/outcome label checks | 111/111 | 126/126 | All checked labels correct: pass |
| Candidate or raw-passage leakage in recall response | 0 | 0 | Zero: pass |
| Unavailable requests | 0/70 | 0/70 | Zero: pass |
| Warm gateway p95, first measured run | 30.1 ms | 515.1 ms | <=250 ms: hybrid fails |

Reference counts are exposures, not distinct references. Resolution proves
identity, freshness and exact passage recovery; **it does not independently
prove that every lesson is semantically entailed by that passage**. The label
checks prove preservation of reviewed labels, not newly observed task success.
No new answer-generation or task-completion experiment was performed.

Hybrid gained five positive hits and lost none versus lexical. The paired
bootstrap difference was +8.3 percentage points (95% interval +1.7 to +16.7;
10,000 samples, seed 224). This is ranking evidence on a spent corpus, not a
generalization guarantee or a fresh product-value estimate.

### Why thirteen fixtures were excluded

All thirteen contain at least one `02-wiki` citation alongside raw-session or
transcript references. The current SourceRef contract accepts approved raw
roots, not the derived wiki. The adapter conservatively rejected the whole
fixture instead of silently removing part of its reviewed evidence bundle.
This is **not** evidence that thirteen original raw sources disappeared or
changed. Their mixed evidence bundles need a source-lineage review before they
can be represented by the production contract. Some raw evidence already exists.

Coverage under this strict adapter is 47/60 (78.3%), so the 85% full-corpus gate
cannot pass even with perfect ranking. Reporting only 42/47 would conceal that
contract mismatch. Conversely, calling all thirteen exclusions ranking failures
would also be misleading. Both denominators are retained above.

### Why negative questions still return experiences

The runtime's FTS expression ORs all tokens of at least four characters; it does
not remove common Dutch words. In hybrid search, lexical hits bypass the cosine
floor. Lexical fallback likewise ranks matching rows without an applicability
decision. These code paths explain why having no appropriate experience is not
equivalent to getting an empty result. A returned source-grounded lesson can
still be irrelevant to the question. Valid provenance is not relevance.

Do not fix this by choosing a threshold on these ten spent negatives. Use them
as regression failures; develop and calibrate any abstention policy separately,
then freeze a new evaluation set. Preserve explicit on-demand use and do not
reintroduce automatic advice.

### Latency qualification

The first hybrid run exceeded budget while vault maintenance was active and
the focused test process overlapped part of the run. Three subsequent diagnostic
replays reused the same 70 query vectors and returned identical rankings:

| Diagnostic replay | Gateway p50 | Gateway p95 | Maximum |
| --- | ---: | ---: | ---: |
| 1 | 108.9 ms | 183.4 ms | 219.9 ms |
| 2 | 64.4 ms | 142.3 ms | 199.4 ms |
| 3 | 64.1 ms | 167.2 ms | 305.8 ms |

These follow-up runs show that warm retrieval can meet budget, but do not erase
the initial under-load failure or isolate its cause. Test resource contention
and extension/open overhead separately before claiming stable production p95.
The query-embedding p95 was 1,279.8 ms. The first run's per-query sum of separately
measured embedding and gateway time had p95 1,520.8 ms. The private JSON calls
this `end_to_end_p95_ms`; it is a **component-sum estimate**, not a directly
observed full MCP request or a source-verification-inclusive response time.

## Source safety, prior utility and remaining uncertainty

All 22 routing/evidence controls passed: normal routes do not implicitly enter
the deeper layers, disabled flags suppress reads, prohibited automatic modes
remain disabled, and malformed/stale/missing/redacted evidence never returns
a passage. Focused production tests also exercise unreviewed, unverified,
retracted and superseded candidate filtering; the historical replay itself
contains eligible fixtures rather than injected candidate distractors.

The historical blinded action comparison was independently rescored after
verifying the option/query hashes: **43/60 correct with experience versus 19/60
with baseline**, difference +40 points, bootstrap interval +20 to +58.3 points.
This confirms the stored result, not new answers from the current runtime.
It remains the strongest practical-value signal from the experiment.

This run tests experience retrieval and exact source verification, not a new
raw-source search-ranking benchmark, live interaction through all installed
clients, automatic extraction quality, or naturally observed usefulness/harm.
Those distinctions do not prevent us from evaluating engineering quality
autonomously. No new owner case labels are required to finish this evaluation
or to reproduce its failures. The old twenty-natural-use counter remains an
unmeasured separate claim, not something an automated replay can fill in.

## Evidence and reproduction

Private directory, relative to the configured vault:
`06-claude/evaluations/automated-regression-2026-09-09-run1/`.
Queries, references, lessons, per-case responses, stored vectors and projection
DB are private. No such content is included in this report.

| Artifact | SHA-256 |
| --- | --- |
| Harness used in run | `f61ada20a6e416a8892d7d58c3e052b0d03e86f07ee93506790e5d3791557de1` |
| Private aggregate.json | `347d80393962838a316c9011118e30440843d73753854bd9c38a3d382e55c081` |
| Initial focused pytest.xml (60 passed, 1 skipped, 20.08 s) | `76f26893395be4783e120f47032fe10702212b6ec8b4046ec6280fadcc64cea0` |
| Final focused pytest-verified.xml (64 passed, 1 skipped, 19.39 s) | `94e5dd6a5b4a05e8c65b73847292ffe56e50c8d1c9b00f97096edb94e60a0099` |
| Final evaluation-harness tests | `2c5760099ea85d58f4c30850decffc9c487b1c1c9af27f381819f58c4d6d1d24` |
| Frozen cases | `0f5881ee6181fe8d9df94ea2779a1404ab71403dca61c7b29fccd443e36208be` |
| Frozen historical DB | `cd22f0d925066275b54cf1e7ccfeefdd308921360b9521edd0dd3c1daf0a4ff9` |
| Historical action master | `96e1cf021a82cdc8bcad9dc8e7bb9cb18ca7ea4e612c3fff480ef8822f3fc461` |
| Historical action reviews | `f95c402934af9b649f973593d3cebe09242685f4e92aa168ab9734e974063bf5` |

Four additional harness tests cover existing-output rejection, exclusion of
derived wiki evidence, Unicode/newline offsets and a database write refusal.
The first expanded run exposed a test-fixture cleanup error on Windows: a
SQLite context manager commits but does not close its connection. Explicitly
closing that fixture fixed it; the final run has no failures or errors. The
intermediate failed XML is retained as `pytest-final.xml`, SHA-256
`de604793e8262b267e00af860a006a2b99db1cb09cf3c6129545b598005c17ae`.
The remaining skip is the existing symlink test because this Windows process
lacks symlink-creation privileges. No product failure was silently skipped.

Reproduce with `scripts/evaluate-experience-regression.py --vault <configured-vault>
--input-dir <private-historical-corpus> --output-dir <new-private-evaluation-dir>`.
Set `KENNISBANK_VAULT` to that same vault. Existing output directories are rejected.
The command's successful exit means the evaluation completed, not that its
acceptance gates passed; inspect the aggregate's gate fields.

## Recommendation

Keep the source-first design and the experience layer: both exact source
recovery and the previously measured answer improvement are meaningful assets.
**Do not yet release this as reliably applicable experience advice.** Close the
mixed-provenance contract gap, add independently evaluated abstention, and
establish predictable latency under normal maintenance load. Those are specific,
automatable next steps, not another open-ended owner-labelling exercise.
