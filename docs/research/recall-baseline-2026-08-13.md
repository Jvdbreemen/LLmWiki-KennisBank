# Recall baseline before the capture caps were raised (2026-08-13)

This is the "before" half of P5 in
`docs/superpowers/specs/2026-08-12-self-correcting-memory-layer-design.md`.

TASK-145 raised what capture reads from a session: `max_chunks` 6 → 40,
`max_memories_per_transcript` 20 → 60, with a new per-run budget of 150 chunks.
That will grow the memory corpus. `retrieve_top_n` is 3, so a bigger corpus can
push the right memory out of the window — a fact that is captured but ranks
fourth is exactly as invisible as one never captured.

The comparison only works if the starting point is written down before the
corpus moves. That is what this file is. Repeat the same command after the
background sweeps have run for a while and compare.

## Method

```bash
python3 scripts/kb-eval.py --json --latency
```

Run on 2026-08-13 against the live vault, before any sweep with the new caps.
No arguments beyond the defaults, so both stock question sets are used. The
eval reads `kb-index.db` and issues one query embedding per question.

Corpus at the time of measurement:

```
memories in 09-memory : 1661   (1531 current, 107 superseded, 23 unverified)
docs in kb-index.db   : 1737   (1531 memory + 206 wiki; the index holds current only)
embed_id              : ollama:qwen3-embedding:4b, dim 2560
transcripts           : 299, of which 97 pending
```

## Wiki layer — 329 questions

| metric | value |
| --- | --- |
| recall@1 | 0.842 |
| recall@3 | 0.997 |
| **recall@5** | **1.000** |
| MRR | 0.917 |
| latency p50 / p95 | 520 / 899 ms |

By type: single-hop 0.873@1 (n=166), keyword 0.819@1 (n=149), paraphrase
0.857@1 (n=7), oblique 0.500@1 (n=4), multi-hop 0.500@1 (n=2), temporal
1.000@1 (n=1).

The wiki layer is saturated at k=5. There is no headroom here, only the risk of
losing it.

## Memory layer — 1224 questions

| metric | value |
| --- | --- |
| recall@1 | 0.322 |
| recall@3 | 0.662 |
| **recall@5** | **0.778** |
| MRR | 0.498 |
| latency p50 / p95 | 460 / 523 ms |

By memory type:

| type | n | @1 | @3 | @5 |
| --- | --- | --- | --- | --- |
| beslissing | 289 | 0.460 | 0.723 | 0.775 |
| feit | 493 | 0.288 | 0.665 | 0.819 |
| procedure | 411 | 0.277 | 0.637 | 0.737 |
| voorkeur | 31 | 0.161 | 0.355 | 0.677 |

## The rule, fixed before the numbers move

Memory recall@5 must not fall below 0.778. Wiki recall@5 must stay at 1.000.
recall@1 may give up a little if @5 holds, because the hook injects three
memories rather than one.

If recall@5 drops after the corpus grows, the cap goes back down. The knob is
merged, but a release is what carries it into a vault, so that is the moment to
decide.

## Why the "after" is not in this document

The measurement needs a corpus that has actually grown, and growing it means
running sweeps over the pending backlog — 97 transcripts at the time of writing.
Rather than force that in one 30-50 minute run, the background sweep is left to
drain the backlog across sessions, which is what the per-run chunk budget exists
for. The "after" is measured on what grew organically, against this file.
