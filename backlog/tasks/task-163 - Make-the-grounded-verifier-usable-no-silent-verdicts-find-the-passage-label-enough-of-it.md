---
id: TASK-163
title: >-
  Make the grounded verifier usable: no silent verdicts, find the passage, label
  enough of it
status: In Progress
assignee: []
created_date: '2026-08-15 11:25'
labels:
  - memory
  - retrieval
  - llm
  - measurement
dependencies: []
priority: high
ordinal: 156700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The validation in `docs/research/llm-trust-verification-2026-08-15.md` passed all three pre-registered criteria: the verdict varies (42.9% non-supported), it is deterministic (56/56), and it agrees with a careful reader (7 of 11 exact, 9 of 11 same direction) — including three cases where the model was right and the human labeller was wrong.

Three things stand between that and a usable trust signal, and all three are in the harness rather than the idea.

**1. 7% of responses were unparseable.** The model answered without emitting a JSON object at all, so `_llmjson` had nothing to rescue. One memory in fourteen would silently get no verdict — the exact failure shape TASK-143, TASK-148 and TASK-144 were written to remove. A retry with a stricter instruction, a bare-verdict fallback, and an explicit `unparseable` count in the output rather than a shrug.

**2. Passage selection misses about half the time.** Five of eleven were `not_found` by both reader and model. The first selector scored raw token overlap and returned slash-command definitions, because those blocks are long, word-rich and injected into every transcript; IDF weighting plus an embedding rerank over the top-8 helped and did not solve it. The reason it cannot solve it: a memory body is an LLM's rewrite of the source, so lexical overlap with the true chunk is weak, and the true chunk may never reach the shortlist.

The fix is to stop shortlisting. Embed every chunk of the source transcript and pick by cosine — expensive per memory, cheap per *transcript*, because memories cluster by session: 299 transcripts against 2389 memories. Cache chunk embeddings per transcript and every later memory from that session is a lookup.

There is a second, better fix for everything captured from now on: **the sweep knows which chunk produced each candidate and discards it.** Recording the chunk index at capture time makes verification exact rather than retrieved, and it is the same shape of waste as the corroboration signal.

**3. Eleven hand-labelled cases established a direction, not a rate.** Any weight placed on this factor needs a larger set, labelled from the full passage this time.

Scope is the harness and the evidence. Whether the signal enters the ranking is a separate decision, to be made on the numbers this produces.</description>
<parameter name="acceptanceCriteria">["No verdict is silently absent: unparseable responses are retried, counted, and reported separately from a real verdict", "Passage selection is measured before and after, on the same sample, and the not_found rate is reported for both", "Chunk embeddings are cached per transcript so cost scales with sessions rather than memories", "The sweep records which chunk produced a candidate, so future memories need no retrieval to verify", "A labelled set large enough to state a rate, labelled from the full passage", "python -m pytest tests -q is green"]

## Where the acceptance criteria stand

Evidence: `docs/research/llm-trust-verification-2026-08-15.md`. Commits fcf96cb,
4052bca, 12f4357, 4cb0382, a89468e, 88ccc5f on `research/rerank-ceiling` (PR #121).

- **No verdict silently absent** — met, but NOT by a retry. The four unparseable
  answers all contained JSON with broken string delimiters, so the fix was in
  the parser, not a second call. A retry is a no-op here anyway: C3 established
  the model is deterministic at temperature 0, so asking again returns the same
  malformed text. Stating that rather than implementing a retry that could not
  have worked. 4/56 → 1/60, and the survivor is counted and reported.
- **Passage selection measured before and after** — met, and measured better
  than asked. `not_found` is not a retrieval score (it conflates a selector miss
  with a false claim), so retrieval was measured against generative ground truth
  instead: the extractor over every chunk of four transcripts, 255 claims with a
  known originating chunk. 62.7% → 87.8% at the 6000-character budget the judge
  actually receives.
- **Chunk embeddings cached per transcript** — met WITHIN a run and not across
  runs. It is a per-process memo on (kind, text), not a cache file: every memory
  from a session after the first is a lookup, and all of it dies when the
  process exits. That is precisely why the stopped 150-memory run could not be
  resumed. Anyone building on this will look for a cache on disk and not find
  one.
- **The sweep records which chunk produced a candidate** — met and proven at
  runtime, not just in the source. `source_chunk: "N/M"`, M = the whole
  transcript's count.
- **A labelled set large enough to state a rate** — PARTLY MET, and this is the
  gap. Stratified rather than enlarged: all 8 `unsupported` adjudicated against
  the whole transcript (R1 = 4/8, Wilson 22-79%), all 60 verdicts quote-checked
  mechanically (0 fabrications). A 150-memory run that would have tightened the
  bound was stopped at 147 of 150 and its results were lost, because the probe
  wrote only at the end — fixed since, but not re-run. The interval is too wide
  to call a rate. It does not change the decision: both ends of it fail the bar
  for demoting a memory.
- **Suite green** — 1427 passed, 2 skipped.

**The conclusion, which TASK-162 depends on: `supported` raises trust, nothing
lowers it.** `unsupported` cannot distinguish a retrieval miss from a false
memory, and that is structural rather than tunable.

Filed on the way: TASK-164 (the 4000-character embed cap hides 23% of the wiki)
and TASK-165 (34% of claims are Dutch from English sources, and the lexical
prefilter cannot bridge that).
<!-- SECTION:DESCRIPTION:END -->
