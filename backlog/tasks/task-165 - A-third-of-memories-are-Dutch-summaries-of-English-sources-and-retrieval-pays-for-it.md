---
id: TASK-165
title: >-
  A third of memories are Dutch summaries of English sources, and retrieval pays
  for it
status: To Do
assignee: []
created_date: '2026-08-15 12:26'
labels: []
dependencies: []
priority: high
ordinal: 158700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Memories are written in Dutch. Transcripts are largely English. Measured on 255 claims with a known originating chunk (TASK-163's extractor ground truth), **87 of 255 — 34% — are a Dutch claim whose source passage is English.**

That gap is not free, and where it lands depends entirely on which stage does the work:

    claim -> source     n     one chunk   windows      IDF prefilter + windows
    nl -> nl          133        62.4%      91.7%                        93.2%
    nl -> en           87        59.8%      86.2%                        78.2%
    en -> en           25        64.0%      96.0%                        96.0%

The multilingual embedding model bridges languages well. Lexical overlap cannot bridge them at all — by construction, not by tuning. So the IDF prefilter that TASK-163 kept for cost (87.8% vs 90.2% overall, a twentyfold reduction in embeddings on a long transcript) turns out to **help same-language retrieval by 1.5 points and cost cross-language retrieval 8**. The average hid a group.

Three distinct questions, deliberately not merged:

**1. Retrieval (cheap, decided by the numbers above).** Skip the lexical prefilter when the claim's language differs from the transcript's. A stopword-ratio check is enough to route it; the prefilter stays as the cost cap on long same-language transcripts where it is actually better.

**2. The judge prompt (probably nothing to do).** No evidence it suffers. It quoted English passages for Dutch claims correctly, with zero fabricated quotes across 60 verdicts. Adding "the passage may be in another language than the claim" is one harmless sentence, but it should not be sold as a fix — measure before and after or leave it.

**3. Extraction language (the root fix, and the one with consequences).** If the extractor wrote each memory in its source's language — or always in English, which is what this repo's language policy says for everything else — the cross-language case would stop existing. It also cuts the other way: the user reads these memories, recall injects them into Dutch conversations, and 2389 existing Dutch memories would not be retroactively consistent with new English ones. TASK-157 tried a wholesale English migration and was deliberately dropped; this is narrower but adjacent, and it is a product decision before it is a technical one.

Do 1 first — it is measured, local, and reversible. Treat 3 as a proposal that needs the user's call and a kb-eval A/B, not as a follow-on.

Caveats on the evidence, stated so the next reader can weigh it: language is detected by a stopword ratio, not a real classifier; the cross-language bucket is n=87 from four transcripts; and all of this is retrieval-of-source measurement, not the production recall path.</description>
<parameter name="acceptanceCriteria">["The prefilter is skipped on a language mismatch, and the cross-language hit rate is re-measured on the same 255 claims to confirm the 8 points come back", "Same-language retrieval does not regress: it keeps the prefilter and its 93.2%", "Any change to the judge prompt is measured before and after, or not made", "Extraction language is put to the user as a decision with its trade-offs, not implemented on the strength of the retrieval numbers alone", "python -m pytest tests -q is green"]</parameter>
<parameter name="labels">["retrieval", "memory", "language", "measurement"]
<!-- SECTION:DESCRIPTION:END -->
