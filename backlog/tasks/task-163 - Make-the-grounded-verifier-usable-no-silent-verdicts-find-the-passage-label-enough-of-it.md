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
<!-- SECTION:DESCRIPTION:END -->
