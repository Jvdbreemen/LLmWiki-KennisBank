# Experience paired-action evaluation protocol

Date: 2026-08-30
Branch: `codex/source-recall-experience-evidence`
Status: completed; protocol preregistered before candidate generation or human
action review.

## Question

Does adding the experience-recall output improve the correctness of the next
action over the strongest currently available non-experimental baseline?

This is a downstream value test, not another retrieval test. The final
experience holdout already failed its false-warning safety gate. A positive
action result cannot reverse that rollout rejection; it can only establish
whether the underlying experience context has measurable value worth studying
with a fresh future safety design.

## Population

Use all 60 positive cases from the frozen 70-case experience set. The input is
bound to SHA-256
`0f5881ee6181fe8d9df94ea2779a1404ab71403dca61c7b29fccd443e36208be`.
The ten unrelated warning probes are excluded because they are factual
source-recall questions, not action-selection episodes.

Each pair has the reviewed task query plus a private reference containing the
observed result, lesson, applicability, and exact source references. Those
fields define the human correctness criterion; they are never given to the
baseline arm merely as an answer key.

## Arms

Both arms use local `qwen3.5:4b`, temperature zero, the same fixed system
instruction, the same task, and the same top-four production wiki/memory
context.

- **baseline**: current production wiki/memory context only;
- **experience**: the identical baseline prompt plus the actual top-three
  validated hits returned by the frozen experience projection.

The experiment uses actual retrieval, including misses and wrong ordering. It
does not inject the gold experience directly. Candidate text is generated once
per arm. A completed case cannot be regenerated.

## Blinding and review

The 60 case IDs are deterministically ordered by a salted SHA-256 using seed
224. Exactly 30 baseline candidates and 30 experience candidates appear as
option A; the other arm appears as B. The blind packet contains no arm names.
The hidden mapping is stored only in the private master packet and is not read
by the `show` or `record` steps.

The owner judges each pair against the reviewed reference using exactly one of:

- `a_only`: only A is correct and actionable;
- `b_only`: only B is correct and actionable;
- `both`: both are correct and actionable;
- `neither`: neither is correct and actionable.

This four-way label yields separate binary correctness for both paired arms;
“tie” is not allowed because it would conflate both-correct with both-wrong.

## Statistic and gate

After all 60 judgments are frozen, reveal the key and compute:

- baseline and experience correctness counts;
- paired correctness delta, experience minus baseline;
- a deterministic paired percentile bootstrap 95% interval with 10,000
  resamples and seed 224;
- counts for all four human verdicts and the A-arm balance.

The preregistered value gate requires all 60 pairs and a correctness delta of
at least +0.10. The confidence interval is reported even if it crosses zero.
No prompt, retrieval, threshold, or label rule may be changed based on the
result.

## Privacy and audit boundary

Queries, references, candidates, reviews, the hidden key, and per-case scores
stay under the configured vault evaluation directory. The repository receives
only this protocol, tests, tooling, and the final aggregate report. Generation
is local-only and usage telemetry is disabled.

Implementation: `scripts/dev/experience-action-review.py` and
`scripts/dev/_paired_action_eval.py`.

## Completed aggregate result

After all 60 judgments were recorded, the hidden mapping was revealed once by
the scorer. Baseline correctness was 19/60 and experience correctness was
43/60, for a paired delta of +0.40. The deterministic 10,000-resample 95%
bootstrap interval is +0.20 to +0.5833. Arm A contained 30 baseline and 30
experience candidates; verdicts were 22 only-A, 22 only-B, 9 both, and 7
neither. The preregistered value gate passes.

The aggregate result is documented in
`docs/research/experience-paired-action-result-2026-08-30.md`. It establishes
downstream value but does not reverse the already measured false-warning safety
failure or authorize rollout.
