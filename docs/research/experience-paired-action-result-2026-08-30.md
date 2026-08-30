# Experience paired-action evaluation result

Date: 2026-08-30
Branch: `codex/source-recall-experience-evidence`
Status: completed after all blinded owner judgments were frozen

## Result

The experience arm improved correct and actionable next-step selection over
the strongest production baseline.

| metric | result |
|---|---:|
| paired cases | 60 |
| baseline correct | 19/60 (0.317) |
| experience correct | 43/60 (0.717) |
| paired delta | **+0.400** |
| 95% paired bootstrap interval | **+0.200 to +0.5833** |
| A-arm balance | 30 baseline / 30 experience |
| four-way verdicts | 22 only-A / 22 only-B / 9 both / 7 neither |

The deterministic percentile interval uses the preregistered 10,000 paired
resamples and seed 224. The input is bound to SHA-256
`0f5881ee6181fe8d9df94ea2779a1404ab71403dca61c7b29fccd443e36208be`.
The value gate required all 60 pairs and a delta of at least +0.10; it passes.

## Interpretation

Both arms used local `qwen3.5:4b`, temperature zero, the same task, and the same
top-four production wiki/memory context. The experimental arm received only
the actual top-three validated experience hits from the frozen projection.
Candidates were generated once. The owner judged A/B pairs without seeing the
arm mapping; exactly half of each arm appeared as A.

This is evidence that retrieved experience can materially improve action
selection. It is not rollout approval. The separately frozen warning holdout
measured two false warnings in ten unrelated probes, exceeding the maximum
0.10 false-warning rate. A positive value result cannot override that safety
failure. Experience recall remains experimental; advisory routing,
outcome-aware ranking, and automatic skill promotion remain disabled.

Private queries, references, candidates, reviews, the hidden mapping, and
per-case scores remain outside the repository in the configured vault.
