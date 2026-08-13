---
id: TASK-145
title: 'Intake truncation: the extractor reads 6 chunks of a 58-chunk session'
status: In Progress
assignee: []
created_date: '2026-08-12 20:31'
updated_date: '2026-08-13 22:26'
labels:
  - memory
  - capture
  - bug
dependencies: []
references:
  - scripts/memory-sweep.py
  - scripts/_extract.py
  - scripts/_sweeputil.py
  - docs/superpowers/specs/2026-08-12-self-correcting-memory-layer-design.md
priority: high
ordinal: 139700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`run_sweep(max_chunks=6)` hands `_extract` only the first six chunks of a transcript. Measured on four transcripts that contain the fact "the vault defaults to qwen3-embedding:4b":

| transcript | chunks | read | coverage | fact in chunk |
| --- | --- | --- | --- | --- |
| 2026-08-01-llmwiki-kennisbank | 24 | 6 | 25% | — |
| 2026-08-06-llmwiki-kennisbank | 14 | 6 | 43% | — |
| 2026-08-07-adr-kit | 31 | 6 | 19% | — |
| 2026-08-06-adr-kit | 58 | 6 | 10% | **17** |

24 of 127 chunks read. The fact sat in chunk 17 of 58 and was therefore never shown to the extractor.

Consequence, verified across the whole vault:

```
transcripts containing "qwen3-embedding:4b":  13   (10 swept, 3 pending)
session logs:                                  2
wiki articles:                                 3
memories:                                      0     <- the layer the recall hook injects
```

Those ten swept transcripts produced 99 memories between them, none about the embedding model. The four stale memories asserting `qwen3-embedding:8b` were never superseded because nothing exists to supersede them WITH. No judge and no structure repairs a fact that was never captured.

The cap exists for cost: with a reasoning model a chunk took 30-56 s, so 58 chunks meant 30-54 minutes per transcript. After TASK-143 (`think: false`) a call takes 1.6-4 s, so the same transcript costs 2-4 minutes in a detached background sweep. Full coverage is affordable for the first time.

Do not simply remove the cap. Measure first: what does each extra chunk yield in new (non-duplicate) memories, and what does the corpus size do? Going from 19% to 100% could multiply the memory count several times over, and dedup, judge and reconcile have to carry it — reconcile being the weak link (TASK-144).

Design context: `docs/superpowers/specs/2026-08-12-self-correcting-memory-layer-design.md`, step 1. This is the step that fixes the observed problem; everything else in that spec keeps case five from happening.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Yield per chunk position is measured on a sample of long transcripts: new memories, duplicates, and cost per extra chunk
- [x] #2 max_chunks is raised or removed on the basis of that measurement, with the chosen value and its reason recorded
- [x] #3 A full sweep over a long transcript completes within the detached background budget, with the wall-clock time recorded before and after
- [ ] #4 P2 holds: after a re-sweep a memory asserting qwen3-embedding:4b exists in 09-memory
- [x] #5 python -m pytest tests -q is green
- [x] #6 transcript_text() returns content for every transcript format in 01-raw/transcripts, or reports which formats it cannot read; today four of ten sampled transcripts yield zero chunks
- [ ] #7 P5 holds: kb-eval on the existing question sets shows recall is no worse after the corpus grows than before
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Adversarial review, 2026-08-12. Two changes to this task.

1. The cause is bigger than max_chunks. Checked across every swept transcript containing the fact: 0 of 10 had it within the first six chunks, and FOUR of those ten yield zero chunks at all while the raw file demonstrably contains the text.

  2026-08-06-adr-kit         58 chunks   fact in chunk 17
  2026-08-09-wt-otgw-1xx    106 chunks   fact in chunks 36, 81, 86
  2026-08-04-adr-kit          0 chunks   <- transcript_text() returns NOTHING
  2026-08-04-oralhistoryagent 0 chunks   <- same
  2026-08-04-rvdb             0 chunks   <- same
  2026-08-04-adr-kit          0 chunks   <- same

Most likely a different message shape (Copilot or Codex transcripts). Raising max_chunks does not fix that half, and it should be fixed first: reading more of a transcript the parser cannot read at all buys nothing. Until it is understood, the true size of the intake gap is unknown -- it may be much larger than 19%.

2. Yield and cost are not enough. retrieve_top_n is 3, so multiplying the corpus multiplies the competition for three slots. A fact that is captured but ranks fourth is exactly as invisible as one never captured. This task is now gated on an eval run (P5) over the existing question sets, before and after.

First half done (commit a729ff9): transcript_text() now reads three formats instead of one.

The cause turned out to be a whole missing client, not a subtlety. transcript_text() looked for `message.role`, which is Claude Code's shape alone. Codex writes `{timestamp, type, payload}` with the conversation under `type=response_item` + `payload.type=message` and content blocks typed `input_text`/`output_text`. Copilot writes a flat hook-event log where `message` is a STRING beside `role`.

Measured on the live archive:

  before:  39 of 299 transcripts read as empty, together 94 MB
  after:    7 of 299 read as empty, together 0.07 MB
  archive now offers 22.6 million characters of readable text

Single sessions recovered: 26.33 MB -> 171k chars, 21.47 MB -> 97k chars, 12.15 MB -> 240k chars.

Deliberate exclusions, each with a reason in the code: Codex `reasoning`/`custom_tool_call`/`function_call`/`token_count` are tool noise (the Claude branch already skipped the equivalent); `event_msg`/`agent_message` repeats the assistant text and would double-count; `developer` is the injected instruction block -- including KennisBank's own -- so capturing it would have the extractor summarise its own instructions.

Honest limitation: the Copilot format contains no assistant replies at all, only user prompts and tool events. It yields half a conversation.

tests/test_transcript_formats.py pins all three shapes plus a mixed file, because an unreadable transcript is swept, written to the watermark, and produces zero memories -- indistinguishable from a session where nothing happened.

Still open on this task: max_chunks=6 still truncates what the parser can now read, and AC #7 (the eval gate on corpus growth) is untouched.

Second half measured and applied.

Yield per chunk position, four long transcripts (198, 171, 154 and 33 chunks), 120 chunks through the real extractor:

  transcript                     chunks   uniek 1-6   uniek 7+   %na6   dup
  2026-07-15-oralhistoryagent       198          29         95    77%     2
  2026-07-26-llmwiki-kennisbank     171          21         71    77%     0
  2026-07-17-oralhistoryagent       154          22         86    80%     2
  2026-07-12-otgw-firmware           33          29        109    79%     0

  TOTAAL   uniek 1-6: 101 | uniek 7+: 361 = 78% van alle unieke kennis
  duplicaten: 4 van 466 kandidaten = 0,9%
  opbrengst: 4,2 (chunk 1-5) 4,2 (6-10) 4,3 (11-15) 3,7 (16-20) 3,9 (21-25) 2,9 (26-30)
  kosten: 6,0 s per chunk

Geen knik binnen 30 chunks. De premisse onder de cap -- later in een sessie is herhaling -- is weerlegd met 0,9% duplicaten.

Vondst tijdens het meten: max_chunks was NIET de bindende rem. max_memories_per_transcript=20 stopte de schrijflus al na ~5 chunks bij ~4 kandidaten per chunk. Beide knoppen moesten dus samen omhoog, anders had het verhogen van max_chunks vrijwel niets gedaan.

Gekozen waarden, met reden:
  MAX_CHUNKS               6 -> 40   (opbrengst blijft vlak tot 25; 40 x 6 s = 4 min per transcript)
  MAX_MEMORIES_PER_TRANSCRIPT 20 -> 60   (anders blijft dit de bindende rem)
  CHUNK_BUDGET             nieuw, 150   (~15 min per run)

De budget-rem is nieuw en het punt is niet zuinigheid maar de hot path: de sweep is losgekoppeld maar deelt de GPU met het embedding-model dat retrieval bedient. Tien transcripts van 40 chunks zou 40 minuten aaneengesloten modelwerk zijn. Het budget kapt TUSSEN transcripts af, nooit erbinnen -- een half verwerkt transcript zou als gedaan in de append-only watermark landen en de rest voorgoed kwijtraken. Wat afvalt blijft pending.

Ook toegevoegd aan de heartbeat: chunks_read, chunks_skipped, budget_reached. Zonder die drie is '5 memories geschreven' niet te onderscheiden van '5 memories geschreven en 300 chunks genegeerd' -- precies hoe dit defect onzichtbaar bleef.

Alle drie de env-overrides bestaan: KB_SWEEP_MAX_CHUNKS, KB_SWEEP_MAX_MEMORIES, KB_SWEEP_CHUNK_BUDGET.

Nog open: AC #4 (P2, vereist een echte re-sweep) en AC #7 (P5, de eval-run). Die twee gaan over de gevolgen van de grotere corpus en horen niet in dezelfde commit als de knop zelf.

P5 baseline recorded 2026-08-13 in [docs/research/recall-baseline-2026-08-13.md](../../docs/research/recall-baseline-2026-08-13.md), before any sweep with the new caps:

  memory  recall@1 0.322  @3 0.662  @5 0.778  MRR 0.498  (1224 questions)
  wiki    recall@1 0.842  @3 0.997  @5 1.000  MRR 0.917  (329 questions)
  corpus  1661 memories, 1737 index docs, 97 transcripts pending

Rule fixed before the numbers move: memory recall@5 must not fall below 0.778 and wiki recall@5 must stay at 1.000. recall@1 may give a little if @5 holds, because the hook injects three memories rather than one.

AC #4 (P2) and AC #7 (P5) are deliberately deferred rather than forced. Measuring them needs a grown corpus, and growing it means sweeping a 97-transcript backlog -- 30-50 minutes in one run, because every candidate costs an extract, a judge and a reconcile call. Two attempts at that were interrupted, and forcing a third would measure a run nobody wants to sit through.

Instead the background sweep drains the backlog across sessions, which is exactly what the per-run chunk budget was added for, and the after-measurement runs on what grew organically. That also makes it a better measurement: it reflects production behaviour rather than a forced batch.

The vault was left untouched by both interrupted attempts -- 1661 memories, watermark at 202, heartbeat still from the previous day. Verified, not assumed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
The intake fix works and is measured. The two remaining criteria are answered — one negatively, one not at all — and both for reasons the fix itself exposed rather than for reasons in the fix.

**What the fix delivers.** First sweep under the raised caps, on the live vault: 617 memories from 7 transcripts. Before it, ten swept transcripts produced 99 memories between them. The truncation was real and it is gone.

**AC#7 does NOT hold. Report: docs/research/recall-after-growth-2026-08-14.md.**

    memory recall@5   0.778 -> 0.768   floor was 0.778   FAILS
    memory recall@1   0.322 -> 0.266
    wiki   recall@5   1.000 -> 1.000   holds

The rule was fixed before the numbers moved, which is exactly why it is worth
something now. Growing the recall set from 1531 to 1740 current memories cost
one point of recall@5 and nearly six of recall@1 — 69 questions.

The mechanism is the one this task was gated on: `retrieve_top_n` is 3, so more
candidates compete for the same slots. The measurement is one-sided by
construction — the eval set asks about memories that existed before the sweep,
so it prices the cost of a bigger corpus and none of its benefit — but that does
not rescue the number. Deciding the metric is imperfect after seeing the result
is choosing the interpretation to fit.

**AC#4 is not met, and not for a reason in this task.** No memory asserting
`qwen3-embedding:4b` exists yet: the two pending transcripts carrying that fact
sit near the back of an 89-deep queue, and the sweep works oldest-first. It needs
roughly eighty more transcripts to reach them.

**Consequence: do not drain the rest yet.** Every further transcript enlarges the
haystack at the current ranking quality. TASK-138 (rerank the top-20 memory
candidates) moves from "worth doing" to blocking, because it is the only
direction that lets capture and recall both improve. TASK-158 was opened
separately: the chunk budget bounds chunks while GPU time is spent on model
calls, so it does not bound what it was built to bound.
<!-- SECTION:FINAL_SUMMARY:END -->
