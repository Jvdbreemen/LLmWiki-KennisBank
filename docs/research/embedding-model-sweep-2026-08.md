# Which embedding model should KennisBank default to?

Status: measured, acted on
Date: 2026-08-03
Scope: the embedding model on the retrieval hot path, measured on one real
vault (1515 documents, Dutch and English) against its owner's own eval sets
Harness: `scripts/embed-sweep.py`, with `scripts/recall-ablation.py` for the
dense-versus-lexical split and `scripts/rerank-eval.py` for the cross-encoder
question
Task: TASK-126, follow-up TASK-128

## Executive conclusion

The default moves from `qwen3-embedding:8b` to `qwen3-embedding:4b`. The 4b is
not a compromise: it scores at least as well as the 8b on both eval sets, is
faster (322 ms versus 347 ms warm p50), and holds 6.2 GB resident instead of
8.4 GB on a 16 GB card. Nothing in nine models beat it on the memory layer.

Two findings matter more than the ranking itself.

**The 47-second p95 in the original baseline was not a property of the model.**
It was VRAM contention: the retrieval hook keeps the embedding model resident
for 30 minutes, so a second model loaded alongside it evicted the first
mid-measurement. Under a protocol that evicts everything, loads one model,
discards a warmup call and only then measures, no model in this sweep exceeded
1017 ms p95.

**Lexical fusion is costing the memory layer about 15 points of recall@5.**
Disabling the FTS5 half raises memory recall@5 from 0.641 to 0.796 on the
current model, and the same shift appears across six of nine models. That is a
retrieval-architecture problem, not a model problem, and it is open as
TASK-128.

## Why measure at all

Public benchmarks rank embedding models on public corpora. The margins between
the serious candidates here are two to four points, and nothing public measures
a bilingual personal vault against the questions its owner actually asks. The
eval sets are the only arbiter with standing, and they are private by design
(`test_eval_privacy.py`), so the measurement has to run locally.

## Method

Nine Ollama models, each measured against a scratch copy of `02-wiki`,
`09-memory` and the eval sets. The live vault is never touched: an interrupted
run cannot leave the working vault half-indexed.

Per model:

1. Evict every resident model (`ollama ps` → `ollama stop`), record free VRAM.
2. Load the candidate with one warmup call. That call is reported separately as
   `load_ms` and **excluded** from the percentiles — folding a one-off load into
   the distribution is what produced the contaminated 47-second p95.
3. Twelve measured embed calls → p50, p95, min, max.
4. Rebuild the index over all 1515 documents.
5. Score recall@1/3/5 and MRR on the wiki and memory eval sets.

Two arms per model: **hybrid**, the production path where `_kbindex.search`
fuses a vector ranking with an FTS5 ranking through RRF; and **vector-only**,
where an empty `query_text` skips the lexical branch because `fts_expr("")`
returns empty. The second arm exists because the first one does not measure the
embedding model. An English-only model scores 0.984 on a Dutch wiki in the
hybrid arm — that is lexical rescue, not comprehension.

Everything ran rank-only (`min_cos = 0.0`, and `MEMORY_MIN_COS = 0.0` inside the
harness process). Recall@k and MRR need no similarity floor, and the production
floor of 0.60 is calibrated for the incumbent model, so applying it would have
silently penalised every challenger.

No production code was modified for the measurement. The harness runs
in-process and patches the two embed entry points for the duration of a run:
`emb.embed()` is the query side, `emb.get_cached()` the document side. Both
`embed_id()` (which gates cross-model cache reuse) and `MEMORY_MIN_COS` (a
default argument in `kb-recall.py`) are load-bearing for the live vault and
were left alone.

## Results

Vector-only, which isolates the embedding from lexical rescue:

| model | warm p50 | wiki MRR | memory MRR | resident |
|---|---|---|---|---|
| nomic-embed-text | 68 ms | 0.987 | 0.333 | 274 MB |
| embeddinggemma:300m | 300 ms | **0.997** | 0.505 | 621 MB |
| **qwen3-embedding:4b** | 322 ms | 0.967 | **0.540** | 6.2 GB |
| qwen3-embedding:8b *(incumbent)* | 347 ms | 0.961 | 0.530 | 8.4 GB |
| qwen3-embedding:0.6b | 371 ms | 0.971 | 0.482 | 3.8 GB |
| granite-embedding:278m | 411 ms | 0.026 | 0.441 | 562 MB |
| e5-large-instruct | 510 ms | 0.021 | 0.472 | 1.1 GB |
| bge-m3 | 518 ms | 0.994 | 0.481 | 1.2 GB |
| snowflake-arctic-embed2 | 659 ms | 0.798 | 0.211 | 1.2 GB |

Every candidate except arctic-embed2 fits the 600 ms hot-path budget.

### Instruction prefixes

e5, embeddinggemma, arctic-embed and nomic expect a task prefix, and a
different one on each side. Measuring them bare understates them; using the
query prefix on documents understates them differently. The harness applies
each side's prefix separately, which is why the two embed entry points are
patched independently rather than through one wrapper.

### Why granite and e5 collapse on wiki but not on memory

Both have a 512-token context. Memory fragments fit; whole wiki articles do
not. 160 and 161 of 1515 documents failed to embed at all, and the rest were
truncated. Their memory scores (0.441 and 0.472) are unremarkable. This is a
fitness verdict for whole-article embedding, not a quality verdict on the
models.

### Why nomic-embed-text is a trap

68 ms is four times faster than anything else, and its hybrid wiki score of
0.984 looks competitive. Vector-only it holds 0.987 on wiki but drops to 0.333
on memory — last among the usable models. An earlier backlinks-based head-to-
head on this vault reached the same conclusion from a different angle (AUC
0.779 against qwen3's 0.945). Short Dutch memory fragments are where an
English-trained model is exposed.

### The lexical fusion finding

| memory recall@5 | hybrid | vector-only |
|---|---|---|
| qwen3-embedding:8b | 0.641 | 0.796 |
| qwen3-embedding:4b | 0.642 | 0.794 |
| embeddinggemma:300m | 0.625 | 0.760 |
| qwen3-embedding:0.6b | 0.629 | 0.746 |
| e5-large-instruct | 0.628 | 0.743 |
| bge-m3 | 0.637 | 0.723 |

The two exceptions point the same way rather than against it: nomic is flat and
arctic gets worse, and those are precisely the models whose vectors are weakest
here, so lexical matching is the only thing holding them up.

The wiki layer does not behave this way. Plausible reading, untested: RRF gives
the lexical ranking equal standing with the vector ranking, and on a short
memory fragment a term match is a far weaker relevance signal than it is on an
article. Open as TASK-128, with the caveats that the memory layer is also
reweighted by recency and importance, and that this is one eval set on one
vault.

## Reproducibility and known noise

Quality numbers repeated within ±0.002 MRR across two independent runs, so the
ranking is stable. Latency mostly improved slightly in the second run as the
card was cleaner. One outlier resists explanation: `qwen3-embedding:0.6b`
measured 656 ms and then 371 ms with a clean card both times. That model should
not be chosen without a third measurement.

## Thresholds: measured, not inherited

Comparing models rank-only was the right call, and it is explicitly not
evidence that the incumbent's similarity floor transfers. It does not.

`kb-calibrate.py` on the 42-pair labelled set reports OVERLAP for the 4b on
both boundaries and proposes a related-boundary of 0.311 against the standing
0.60. That proposal should not be taken at face value: kb-calibrate measures
text-against-text pair similarity, while `retrieve_threshold` gates
query-against-document similarity. Different distributions, different answer.

Measured directly instead, one pass per layer over the live index, keeping the
cosine of the expected document per question so the whole curve falls out of a
single pass:

| floor | wiki recall@5 (329 questions) | memory recall@5 (1224 questions, 806 retrievable) |
|---|---|---|
| 0.35 | 1.000 | 0.658 |
| 0.40 | 0.997 | 0.654 |
| 0.45 | 0.997 | **0.624** |
| 0.50 | **0.994** | 0.568 |
| 0.55 | 0.988 | 0.481 |
| 0.60 | 0.960 | 0.359 |

True-match cosines: wiki min 0.387, p10 0.648, p50 0.761; memory min 0.340,
p10 0.484, p50 0.615. Memories sit structurally lower, which is what the
comment above `MEMORY_MIN_COS` predicted years before anyone measured it.

New defaults: `retrieve_threshold` 0.50 (loses 2 of 329 instead of 13) and
`MEMORY_MIN_COS` 0.45 (loses 42 of 806 instead of 366). Both stay above the
noise band of 0.51 documented for the 8b.

The other half of the trade-off is unmeasured: lowering a floor admits weaker
matches, and there is no labelled precision set to quantify that. The damage is
bounded by `retrieve_top_n` (3), so the floor mainly decides whether anything is
injected at all rather than how much.

The semantic-tiling thresholds (0.85 / 0.62) are still calibrated for the 8b and
were not touched here. They run off the hot path, so they can be recalibrated
when someone next works on dedup.

## Reproducing

```bash
python3 scripts/embed-sweep.py --list-prefixes
python3 scripts/embed-sweep.py --models qwen3-embedding:4b,bge-m3 \
    --vector-only --warm-calls 12 --json results.json
```

Close anything else holding VRAM first. On this machine the biggest competitor
was KennisBank itself: the UserPromptSubmit hook embeds every prompt and keeps
the model resident for 30 minutes, so typing during a sweep reloads the old
model beside the candidate. The harness records free VRAM per model so a
contaminated row is identifiable rather than silently averaged in.
