---
id: TASK-165
title: >-
  A third of memories are Dutch summaries of English sources, and retrieval pays
  for it
status: To Do
assignee: []
created_date: '2026-08-15 12:26'
labels:
  - retrieval
  - memory
  - language
  - measurement
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

Caveats on the evidence, stated so the next reader can weigh it: language is detected by a stopword ratio, not a real classifier; the cross-language bucket is n=87 from four transcripts; and all of this is retrieval-of-source measurement, not the production recall path.

<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The prefilter is skipped on a language mismatch, and the cross-language hit rate is re-measured on the same 255 claims to confirm the 8 points come back
- [ ] #2 Same-language retrieval does not regress: it keeps the prefilter and its 93.2%
- [ ] #3 Any change to the judge prompt is measured before and after, or not made
- [ ] #4 Extraction language is put to the user as a decision with its trade-offs, not implemented on the strength of the retrieval numbers alone
- [ ] #5 python -m pytest tests -q is green
<!-- AC:END -->

## Close-out (2026-08-16) — parked

Nothing shipped: no language-mismatch routing exists anywhere, and the IDF prefilter now lives in scripts/_groundcheck.py:106-126 (created 2026-08-16 for TASK-195's trap 1), whose docstring cites this task's measurement yet keeps the prefilter unconditional. The stakes rose since filing: trap-1 grounded promotion autonomously promotes quarantined memories via select_passage, so the measured 8-point cross-language deficit (nl->en 78.2% with prefilter vs 86.2% without, n=87) now biases which memories exit quarantine — Dutch claims from English sources are systematically less likely to find their supporting passage and earn 'supported'. The evidence lives in this task's table, TASK-163's 255-claim ground truth, and docs/research/llm-trust-verification-2026-08-15.md which filed it. AC#4 (extraction language) remains a user decision; TASK-157's wholesale English migration was deliberately dropped, and this narrower question should not be decided by retrieval numbers alone.

**Evidence:** No language-mismatch routing exists (grep for stopword/prefilter/language across scripts/); scripts/_groundcheck.py:83-126 (SHORTLIST=8, _idf_shortlist unconditional; docstring at :111-113 cites 'TASK-165 measured the split' but implements no skip); created 2026-08-16 in d9e3b45 (TASK-195 trap 1, grounded promotion consumes select_passage); docs/research/llm-trust-verification-2026-08-15.md:354 files this task

**Remaining work (when reopened):** AC#1: a stopword-ratio language check that skips _idf_shortlist when the claim's language differs from the transcript's, re-measured on the same 255 claims (TASK-163 ground truth) to confirm the 8 points return; AC#2: same-language keeps the prefilter and its 93.2%; AC#3: judge prompt only changed with a before/after measurement; AC#4: the extraction-language question (Dutch vs English memories) put to the user as a product decision with the 2389-existing-Dutch-memories trade-off.
