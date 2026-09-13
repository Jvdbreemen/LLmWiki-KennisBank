# Experience-advisory development calibration

Date: 2026-08-30  
Branch: `codex/source-recall-experience-evidence`  
Status: development threshold selected; frozen holdout spent; rollout rejected.

## Decision

Keep the failure-advisory cosine floor at **0.50** and make that value an
explicit calibrated constant. The incumbent happened to use the same numeric
default, so the development evidence justifies no threshold change. The
gateway now resolves its default from the versioned constant instead of a
second literal.

This is not a rollout approval. The selected development point sits exactly
on the preregistered false-warning boundary and still misses one positive.

## Development set

The private set contains 21 owner-reviewed cases:

- 11 queries that should retrieve one specific failed approach;
- 10 factual source-recall queries for which experience recall must abstain;
- 21 unique evidence sources;
- no case ID, exact query, or evidence-source overlap with the 60-case frozen
  source holdout.

Prompts, expected answers, source coordinates, the disposable SQLite database,
and per-case observations remain under
`06-claude/evaluations/source-experience-2026-08-27` in the configured vault.
The repository records aggregate results only.

## Measured result

Model: `ollama:qwen3-embedding:4b`.

| arm / threshold | positive recall | precision | false-warning rate |
|---|---:|---:|---:|
| lexical only | 8/11 = 0.727 | 8/21 = 0.381 | 10/10 = 1.00 |
| hybrid, 0.45 | 10/11 = 0.909 | 10/12 = 0.833 | 2/10 = 0.20 |
| **hybrid, 0.50** | **10/11 = 0.909** | **10/11 = 0.909** | **1/10 = 0.10** |
| hybrid, 0.55 | 7/11 = 0.636 | 7/7 = 1.00 | 0/10 = 0.00 |

The selected hybrid point improves positive recall over lexical by 2/11, or
18.2 percentage points. Threshold 0.45 violates both safety gates. Threshold
0.55 removes the remaining false warning but loses three correct warnings, so
it is not the maximum-recall point subject to precision >= 0.90 and
false-warning rate <= 0.10.

## Reproducibility and boundaries

`scripts/calibrate-experience-advisory.py` builds a private dev-only experience
projection, runs hybrid and pure lexical retrieval, verifies split
independence, and writes only an aggregate report outside the repository.
Usage telemetry is disabled for the run. The runner and threshold contracts
have focused tests.

The threshold selection was committed as `91ffea4`; the one-shot evaluator and
its atomic spent-attempt lock were committed as `364034e`. Only then was the
frozen reviewed holdout run.

## Final one-shot holdout

The private set contained 60 positive cases, 10 unrelated probes, and 29
failure-attempt episodes. Its SHA-256 was
`0f5881ee6181fe8d9df94ea2779a1404ab71403dca61c7b29fccd443e36208be`.

| final metric | hybrid | lexical | gate |
|---|---:|---:|---|
| hit@1 | 0.817 | 0.750 | context |
| hit@3 | 0.900 | 0.800 | hybrid must win: pass |
| MRR | 0.858 | 0.775 | context |
| failure-attempt hit@3 | 27/29 = 0.931 | 24/29 = 0.828 | >= 0.70: pass |
| evidence precision | 1.00 | 1.00 | 1.00: pass |
| candidate leakage | 0 | 0 | zero: pass |
| advisory precision | 27/29 = 0.931 | n/a | >= 0.90: pass |
| false-warning rate | **2/10 = 0.20** | 10/10 = 1.00 | <= 0.10: **fail** |

Explicit-route latency was 99.0 ms p50 and 129.3 ms p95. The hybrid arm has
real value over lexical retrieval, but it fails the preregistered abstention
safety gate. The aggregate decision is therefore **reject for rollout**.

This holdout is spent. Its cases, observations, database, and report remain
private; the repository records aggregates only. No threshold or routing
change may be selected from these scores, and this set may not be rerun. The
separate requirement for 60 paired baseline-versus-experience action judgments
remains open, but cannot reverse this rollout's failed safety gate.
