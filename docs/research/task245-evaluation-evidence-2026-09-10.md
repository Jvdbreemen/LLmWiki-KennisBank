# TASK-245 evaluation evidence — 2026-09-10

Status: **not release-ready**. This report records the engineering evidence
from the `codex/source-grounded-experience-production` feature branch. It does
not promote a memory, accept a fixture, or enable a production route.

## Decision in one paragraph

The new evaluator and profiling harness are useful additions, but the measured
applicability problem is not solved by adding another vector database, a
reranker, or a local LLM judge. None of the tested applicability policies met
both pre-registered gates: at least 85% positive hit@3 and at least 90% correct
negative no-hit specificity. The gateway itself is fast enough with cached
vectors, while the real qwen3-embedding:4b query plus gateway path is right on
the ordinary 250 ms p95 boundary and misses it under concurrent maintenance
load. Therefore TASK-245 keeps production recall unchanged and does not wire a
new automatic applicability/advisory route.

## Evaluation boundary and inputs

The independent private development split contains 36 cases: 18 positive
paraphrases and 18 nearby hard negatives across six lesson groups. The six
records and their raw source proofs are outside the repository under the active
vault's `06-claude/evaluations/task245-independent-2026-09-09/` directory.
Labels are auto-authored, source-grounded fixture judgments. They are not
owner labels, canonical reviews, observed natural-use outcomes, or proof of
causal usefulness. The sealed holdout was not opened.

Input hashes:

| Input | SHA-256 |
|---|---|
| `development.jsonl` | `0667a00cd4501bbd675709f7ab983bcfd3f3d1e0ad75a769823c9a09cb0fbd90` |
| `records-development.json` | `b67cf3877af074a688aca4f32ad3f81d2cda39359de862058bda3aaf0017d06f` |

Every runner rejects empty queries, missing expected IDs, duplicate case IDs,
incomplete candidate score maps, duplicate JSON judge keys, non-boolean judge
values, and non-finite scores. Scoring text contains only bounded content
fields with explicit field boundaries; source references, paths, confidence,
review state, and acceptance metadata are excluded.

## Applicability results

Thresholds were selected on the development split only. A missing or malformed
model response is a failure, never a correct abstention.

| Arm | Best balance (hit@3 / negative specificity) | Best point with specificity >=90% | Result |
|---|---:|---:|---|
| Lexical overlap | 61.1% / 61.1% | 38.9% / 94.4% | rejected |
| qwen3-embedding:4b cosine | 77.8% / 72.2% | 38.9% / 94.4% | rejected |
| BGE reranker v2 m3, local CUDA | 83.3% / 77.8% | 72.2% / 94.4% | rejected |
| qwen3.5:4b local answerability judge | 83.3% / 5.6% | no point | rejected |

The lexical arm's looser 94.4% positive result is not a contradiction: its
best recall point shows 17/18 positives but also exposes every negative. This
is precisely the candidate-ranking-versus-applicability distinction the task
was meant to test.

The local judge completed 36/36 cases with no parse failures, but took p95
2,642.7 ms per case and classified 17/18 negatives as answerable at the
strict binary point. It is therefore neither a safe hot-path gate nor a useful
abstention policy on this fixture set.

Private artifacts:

- `task245-applicability-lexical-2026-09-10/aggregate.json`
- `task245-applicability-cosine-2026-09-10/aggregate.json`
- `task245-applicability-bge-2026-09-10/aggregate.json`
- `task245-applicability-judge-2026-09-10/aggregate.json`

The BGE score map was generated with the locally cached
`BAAI/bge-reranker-v2-m3` safetensors model, whose private model-file hash is
`d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286d`.
The reranker environment is isolated from production dependencies.

## Latency and integrity results

The profiler now measures projection opening, compatibility, extension loading,
search, close, real query embedding, gateway time, and end-to-end time
separately. It hashes the projection and the private telemetry database plus
SQLite sidecars before and after the run. The gateway logs are disabled and the
telemetry environment is redirected to the isolated evaluation vault.

| Run | Gateway p95 | Query embedding p95 | End-to-end p95 | Load | Integrity |
|---|---:|---:|---:|---|---|
| cached-vector ordinary | 146.6 ms | n/a | n/a | none | projection and telemetry unchanged |
| cached-vector concurrent FTS scan | 92.0 ms | n/a | n/a | 71,840 scans | projection and telemetry unchanged |
| real qwen3-embedding:4b ordinary | 60.3 ms | 120.4 ms | 249.6 ms | none | projection and telemetry unchanged |
| real qwen3-embedding:4b concurrent | 89.0 ms | 157.9 ms | 282.2 ms | 50,624 scans | projection and telemetry unchanged |

The ordinary real end-to-end run technically lands below 250 ms, but with only
0.4 ms margin. The concurrent run fails the 250 ms p95 target. No connection
pool or extension rewrite is justified by these measurements; the search phase
is the dominant cached-vector component, and the embedding phase dominates the
end-to-end path.

## Provenance audit

The private mixed-provenance audit covered all 13 previously excluded records.
It found 28 original raw references across 12 files, all hash-matched, and
retained all 16 original wiki references in the audit trail. Relevant raw
evidence is not automatically support for every stored claim:

- 1/13 has a bounded lesson/scope/outcome that can be supported without wiki,
  but its full stored record still has a separate evidence gap;
- 12/13 need additional raw evidence, explicit narrowing, or scope resolution;
- 1 material raw-versus-corrected lesson conflict and 1 direct outcome/scope
  mismatch remain visible;
- 1 supplementary wiki file is stale;
- 0/13 are ready for an unqualified “drop wiki refs” conversion.

The audit is semantic automation, not canonical review. No wiki reference was
deleted and no production record was promoted.

An independent repeat of the existing source/experience regression harness
included 47/60 historical hybrid positives (70% hit@3), 449/449 exact fresh
source references, 0 candidate/raw-content leaks, 126/126 state-label checks,
and 0 unavailable calls. All 22 prohibited/disabled-mode controls passed
(experience and source normal, advisory, automatic, fallback, ranking,
promotion, hook, injection, and disabled checks, plus invalid/stale/missing/
redacted source checks). Frozen inputs were unchanged; the isolated projection
and owner snapshots were unchanged. The historical action replay improved from
19/60 to 43/60, delta +0.40 with bootstrap CI [0.20, 0.5833]. This is useful
regression and safety evidence, not a natural-use outcome and not evidence that
the new applicability policy works.

Private repeat artifact: `task245-source-integrity-repeat-2026-09-10-final/`.
The final repeat used harness SHA-256
`b192e043159cbb23d74638946e36f86e56e8be339cf96f83271f77d098749050`.

## Implementation and test evidence

The feature branch adds a dependency-free applicability runner, strict judge
output validation, pure development-only threshold helpers, local experimental
BGE and qwen judge drivers, and a read-only phase profiler. Focused tests pass:

```text
23 passed
```

The profiler's regression tests include a deliberate injected telemetry write;
that test must be detected as integrity failure. A previous real run also
detected unrelated live maintenance writes to the owner telemetry database;
that run is retained as diagnostic evidence and is not used for the clean
latency claim. Subsequent isolated reruns had no projection or telemetry
change.

## Release implication

TASK-245 should not ship a third automatic memory layer yet. The useful
production shape remains two explicit projections with different jobs:

1. reviewed experience recall answers “what worked before?” and returns the
   bounded lesson plus validation metadata;
2. source recall answers “show me the underlying evidence” on demand and
   reconstructs exact fresh passages from approved raw references.

An applicability gate may be reconsidered only with a larger, independently
labelled and more diverse development/holdout design, or with an explicitly
bounded product interaction that tolerates “candidate suggestions” instead of
claiming answerability. The current data does not justify a production
threshold, an automatic advisory, a cloud fallback, or a new vector store.
