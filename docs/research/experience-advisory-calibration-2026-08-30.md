# Experience-advisory development calibration

Date: 2026-08-30  
Branch: `codex/source-recall-experience-evidence`  
Status: development threshold selected; frozen holdout not rerun yet.

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

The frozen reviewed holdout remains untouched after this selection. Its next
run is one-shot: no further threshold or routing tuning may follow from those
scores. A pass still does not satisfy the separate requirement for 60 paired
baseline-versus-experience action judgments.
