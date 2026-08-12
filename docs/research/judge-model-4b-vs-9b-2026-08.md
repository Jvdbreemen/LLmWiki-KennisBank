# Judge model: qwen3.5:4b against qwen3.5:9b (2026-08-12)

**Verdict: keep `qwen3.5:4b`.** The 9b loses on every criterion the decision rule
named, and by a wide margin on extraction. It is not a close call that VRAM
headroom then breaks — the smaller model is simply better here.

But the measurement's most important result is not the comparison. Setting it up
uncovered that the judge seam was **returning nothing at all about a third of the
time**, on every model, because `qwen3.5` is a reasoning model and its thinking
was spending the answer's budget. That is TASK-143, fixed before these arms ran.
Every number below was produced with `think: false`; without it the comparison
would have measured the fail-safes instead of the models.

Harness: `scripts/judge-model-sweep.py`. Raw responses and metrics are written
alongside the report by the same run.

## What the judge decides

Three seams, all strict-JSON, all fail-safe in a way that hides a weak model:

| seam | on no usable answer | consequence |
| --- | --- | --- |
| `_extract.extract_candidates()` | `[]` | nothing captured from that chunk |
| `_judge.judge()` | `unverified` | the memory lands in quarantine |
| `_reconcile.judge_reconcile()` | `ADD` | a duplicate instead of closing the old one |

A model that never answers is indistinguishable from a model that answered
"nothing to do here". That is the whole reason to score the RAW response.

## Method

Inputs, seed 42, from the live vault (read-only):

- **20 supersede pairs** — memories the vault itself closed, paired with the
  successor its `superseded_by` link names. These are labels the incumbent
  (`gemma4:12b`) produced and the user has lived with. **They are not ground
  truth.** Agreement measures "does this model reproduce the accepted
  behaviour", nothing stronger.
- **20 unrelated pairs** — current memories sharing almost no vocabulary
  (Jaccard ≤ 0.06). **Out of distribution on purpose**: production only asks the
  reconcile question about neighbours above cosine 0.75, so these pairs never
  reach the judge in real use. They are a bias probe, not an error rate.
- **6 transcript chunks** of ≥1500 characters, spread across the archive.
- **8 judge candidates**, existing memory bodies.
- Determinism: 4 items × 3 repeats per arm.

Both arms: num_ctx 4096, temperature 0, `think: false`, local Ollama only (the
harness refuses to run with a cloud provider in the chain).

## Results

| | qwen3.5:4b | qwen3.5:9b |
| --- | --- | --- |
| VRAM (with the embedder resident) | 3.13 GB | 5.49 GB |
| supersede agreement (n=20) | **35%** | 25% |
| unrelated → ADD (n=20, OOD probe) | **65%** | 0% |
| JSON conformance, reconcile | **100%** | 90% |
| JSON conformance, extract / judge | 100% / 100% | 100% / 100% |
| candidates per chunk | **3.17** | 1.67 |
| chunks yielding nothing | **1 of 6** | 5 of 6 |
| determinism (4 items × 3 reps) | 4/4 stable | 4/4 stable |
| latency p50 reconcile / extract / judge | 1861 / 4012 / 1778 ms | 2141 / 2307 / 2150 ms |
| latency p95 reconcile / extract | 2713 / 7460 ms | 15862 / 17970 ms |

The pre-registered rule was: keep the 4b unless the 9b wins on BOTH supersede
agreement and JSON conformance, with the ADD class not worse. It wins neither
and is worse on the third. **Decision: keep `qwen3.5:4b`.**

## What the numbers do and do not support

**Significant.** The extraction gap is the real finding: the 9b returned an
empty list for five of six real transcript chunks where the 4b found candidates
in five of six. Both parsed 100%, so this is the model choosing to extract
nothing, not a formatting failure. For a capture pipeline that is
disqualifying — a judge that never proposes anything cannot be redeemed by
judging well.

The unrelated-pair result is equally lopsided: 18 of 20 NOOP against the 4b's 6.

**Not significant.** 35% against 25% on twenty pairs is inside the noise
(binomial SE ≈ 11 points). Read it as "neither model reproduces the vault's
supersede decisions well", not as "the 4b is better at superseding".

## Both models misread NOOP, and that is the more useful bug

The prompt defines NOOP as "the new adds nothing; the existing already covers
it". Both models used it to mean *unrelated*, in as many words:

> `{"action": "NOOP", "reason": "De nieuwe tekst gaat over lwIP en timing, de bestaande tekst over exit codes; geen overlap."}` — qwen3.5:4b

> `{"action": "NOOP", "reason": "De nieuwe tekst over git-commando's heeft geen enkel verband met ..."}` — qwen3.5:9b

"No overlap" is the definition of ADD in this prompt, and NOOP is the one action
that **discards the new memory**. In production the cosine ≥ 0.75 gate keeps
genuinely unrelated pairs away from this question, so the live blast radius is
smaller than the 18-of-20 suggests — but a seam whose most destructive verdict
is the one both models reach for when confused is worth a prompt rather than a
bigger model. Filed as TASK-144.

Second, smaller finding from the same rows: the 9b's two parse failures were
answers that continued in prose *after* the JSON object. All three seams slice
with `find("{")` … `rfind("}")`, which then spans the trailing text. The 4b
never triggered it in 54 calls; the 9b did twice in 20.

## What stayed unmeasured

- **Quality of what is extracted.** Only yield was scored, not whether the
  captured facts are worth keeping. The 4b's 3.17 candidates per chunk could
  include noise the 9b correctly refused; nothing here rules that out.
- **The judge verdicts** have no labels at all. The arms disagreed (4b: 4
  current / 4 unverified; 9b: 6 / 2) and nothing decides who was right.
- **`gemma4:12b` was not re-run** as a third arm with thinking off. It fits
  beside the embedder only at 8.06 GB and was already rejected on VRAM.
- **n is small.** Twenty pairs per class and six chunks. The conclusions that
  survive that are the large ones, which is why the decision rests on the
  extraction gap rather than the supersede percentages.

## Reproducing

```bash
python3 scripts/judge-model-sweep.py \
    --models qwen3.5:4b,qwen3.5:9b --pairs 20 --chunks 6 --reps 3 \
    --out judge-sweep.json
```

Read-only on the vault; writes one JSON report holding every raw response, so a
claim here can be re-checked without spending the GPU again.
