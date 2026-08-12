# A self-correcting memory layer: state replaces, events accumulate — design

Date: 2026-08-12
Status: design, not yet implemented
Related: TASK-142, TASK-143, TASK-144, `docs/research/judge-model-4b-vs-9b-2026-08.md`,
the `second-brain-audit` skill

## The problem, as it presented itself

On 2026-08-12 the user asked which embedding and judge model is optimal. The
recall hook injected, into that same prompt:

> `[[2026-07-02-embedding-model-specificaties]]` — *Gebruik `qwen3-embedding:8b`
> als standaard meertalig model*

The vault has run `qwen3-embedding:4b` since v0.28.0, chosen after measuring nine
models. The system fed the wrong answer at the exact moment the right question
was asked.

An audit following the `second-brain-audit` method found four such memories, all
`status: current` and therefore eligible for injection:

| memory | claims | reality |
| --- | --- | --- |
| `2026-07-02-embedding-model-specificaties` | `qwen3-embedding:8b` is the default | `kennisbank-embed.json` pins `4b` |
| `2026-07-02-gebruik-qwen3-embedding8b-op-gpu` | 8b chosen for latency | 4b is both faster and better |
| `2026-07-02-drempelwaarden-voor-deduplicatie` | 0.85 / 0.62-0.84 | calibrated for 8b; the floors are now 0.50 and 0.45 |
| `2026-07-05-default-model-selection` | always `claude-opus-4-8` | the policy holds, the version does not |

The skill's deterministic script found **none** of these. It compares monetary
values only, and this vault has none. First lesson: an audit that does not report
where it was blind is lying with a number.

## Why it happened: three causes, measured

### 1. 81% of every long session is never read

`run_sweep(max_chunks=6)` hands the extractor only the first six chunks.

| transcript | chunks | read | coverage | the fact sits in chunk |
| --- | --- | --- | --- | --- |
| 2026-08-01-llmwiki-kennisbank | 24 | 6 | 25% | — |
| 2026-08-06-llmwiki-kennisbank | 14 | 6 | 43% | — |
| 2026-08-07-adr-kit | 31 | 6 | 19% | — |
| 2026-08-06-adr-kit | 58 | 6 | 10% | **17** |

24 of 127 chunks. The fact sat in chunk 17 of 58.

Checked across every swept transcript that contains the fact, **none had it within
the first six chunks**:

```
2026-08-06-adr-kit         58 chunks   fact in chunk 17
2026-08-09-wt-otgw-1xx    106 chunks   fact in chunks 36, 81, 86
2026-08-01-llmwiki         24 chunks   not in any chunk
2026-08-04-adr-kit          0 chunks   <- transcript_text() returns NOTHING
2026-08-04-oralhistory      0 chunks   <- same
2026-08-04-rvdb             0 chunks   <- same
2026-08-04-adr-kit          0 chunks   <- same

0 of 10 seen, 10 of 10 out of reach
```

Four of those ten yield **zero chunks** while the raw file demonstrably contains
the text. That is not truncation but total blindness:
`_sweepstate.transcript_text()` extracts nothing from them, most likely a
different message shape (Copilot or Codex transcripts). Raising `max_chunks`
does not fix that half.

Where the fact does live:

```
transcripts containing "qwen3-embedding:4b":  13   (10 swept, 3 pending)
session logs:                                  2
wiki articles:                                 3
memories:                                      0     <- the layer the hook injects
```

Those ten swept transcripts produced 99 memories between them. Not one about the
embedding model. This is not a judgment failure; it is a selection failure caused
by truncation.

`max_chunks=6` existed for cost. With a reasoning model a chunk cost 30-56 s, so
58 chunks meant 30-54 minutes. With `think: false` (TASK-143) a call takes
1.6-4 s and full coverage becomes affordable for the first time.

### 2. The judge answered nothing about a third of the time

`qwen3.5` is a reasoning model, and its chain-of-thought spends the same
`num_ctx` budget of 4096 as the answer. Measured on three real pairs:

| config | latency | eval_count | empty |
| --- | --- | --- | --- |
| thinking on (production until 2026-08-12) | 30.2 / 40.3 / 55.7 s | 2106 / 2861 / 3885 | 1 of 3 |
| `think: false` | 1.64 / 1.73 / 1.64 s | 39 / 48 / 40 | 0 of 3 |

Every seam is fail-safe: `extract` → `[]`, `judge` → `unverified`, `reconcile` →
`ADD`, `judge_supersede` → `False`. A model that returns nothing therefore looks
exactly like a model that answered "nothing to do here".

### 3. Four maintenance passes, four silent zeroes

The last sweep's heartbeat: `superseded: 0`, `reconciled_superseded: 0`,
`rechecked_retracted: 0`, `promote_marked: 0`, `exact_duplicates_closed: 0`.

`memory-sweep.py` calls each pass inside `try: ... except Exception: 0`, so a
failure is indistinguishable from an idle run. On top of that,
`_maintenance.current_items()` calls `get_cached(..., recompute=True)` per
memory; on this vault 1506 of 1531 cached vectors carry a different `embed_id`
(`ollama:embeddinggemma...` rather than `ollama:qwen3-embedding:4b`), so every
pass tries to re-embed 1506 memories. A manual call was still running after ten
minutes. The retrieval index itself is clean (`embed_id =
ollama:qwen3-embedding:4b`, dim 2560, 1531 memory docs), so this hits maintenance,
not retrieval.

## Measurement P1: is the bottleneck search, or judgment?

101 of the 107 `superseded_by` pairs are measurable (the successor is in the
index; the closed memory was re-embedded through `doc_text` + `kind="doc"`).

**P1a — cosine between a closed memory and its successor**

```
p10=0.757  p25=0.824  p50=0.897  p75=1.000  p100=1.000

above 0.95:  41/101 =  41%
above 0.85:  71/101 =  70%   <- supersede_pass's window
above 0.75:  94/101 =  93%   <- reconcile's window
```

**P1b — rank of the successor among all 1531 current memories**

```
top-1: 58%   top-2: 95%   top-5: 100%   median 1   worst 5

visible to reconcile      (top-2 AND cos>0.75):  92%
visible to supersede_pass (cos>0.85):            70%
```

**Search is not the problem.** 92% of the real pairs already fall inside
reconcile's window, at a median rank of 1. The mechanism looks straight at the
successor and then decides wrongly.

**But the window is aimed at the wrong band.** The three lowest cosines are the
most interesting cases:

| cos | old → new |
| --- | --- |
| 0.704 | *"The Rescan button lacks visual feedback, making it appear broken. Implement a 'Scanning...' state"* → *"De Rescan-knop toont nu een 'Scanning...' status"* |
| 0.692 | *"Generate every document and write it straight to disk"* → *"Generate release documents (RELEASE_NOTES, BREAKING_CHANGES...)"* |
| 0.675 | *"Ask one question per message"* → *"Ask one question at a time, apply YAGNI strictly, offer 2-3 alternatives"* |

The first is the canonical state change: problem → solved. It sits at 0.704,
below both thresholds. The two highest pairs are byte-identical texts
(cos = 1.000) that `exact_duplicate_pass` should have closed without a model.

So 41% of the historical pairs were duplicates, while the cases that matter fall
outside the window.

## Measurement P1c: precision, which P1a and P1b never measured

P1 asked "are the real pairs visible" and answered 92%. It never asked how many
*visible* pairs are not real pairs. Over all 1,171,215 pairs among the 1531
current memories:

```
pairs above 0.95:      1
pairs above 0.90:      4
pairs above 0.85:     11     <- supersede_pass's entire workload
pairs above 0.80:     51
pairs above 0.75:    163
pairs above 0.70:    448

neighbours per memory above 0.85:  median 0, p95 0, max 1
neighbours per memory above 0.75:  median 0, p95 1, max 3
```

Two consequences, both against what this design first assumed.

**Deduplication before the judge solves a problem that no longer exists.** The
41% above 0.95 sits in the *historical* pairs; the living corpus holds exactly
one pair above 0.95. Superseded memories leave the index, so a closed pair leaves
the candidate space with them. Dropping that proposal.

**`supersede_pass` has 11 pairs to work with in the entire vault.** A perfect
judge would close at most eleven things. The mechanism meant to correct the
memory layer after the fact has almost nothing to chew on — not because it
chooses badly, but because contradicting facts are not there. That is the intake
finding confirmed from the other side.

It follows that self-correction will arrive almost entirely through `reconcile`
at write time, not through `supersede_pass` afterwards. The earlier draft of this
design put its weight on the wrong half.

Lowering the threshold is cheaper than feared: 0.85 → 0.75 moves the workload
from 11 to 163 pairs, roughly three minutes of judge time for the whole corpus.

## Measurement: does a better model help?

The same 20 in-distribution pairs plus 20 unrelated pairs (seed 42):

| model | supersede pairs | unrelated pairs |
| --- | --- | --- |
| local `qwen3.5:4b` | 7/20 | 13/20 |
| local `qwen3.5:9b` | 5/20 | 0/20 |
| `claude -p --model haiku` | **4/20** | **18/20** |

Haiku is clearly better at the definitional error (NOOP means "the existing
already covers it", not "no overlap") and worse at reproducing what the old
gemma4 judge decided.

That becomes coherent next to P1a: 41% of those labels are near-identical texts,
and both local models and Haiku answered that the texts are identical and chose
NOOP. That is a defensible answer.

**So 7/20 measures label noise as much as model error.** For future measurement:
evaluate on the 0.70-0.90 band only. Above 0.95 the question is deduplication,
not a fact that changed.

## What the skill contributes

The useful part of `second-brain-audit` is not code but a claim:

> *Structure carries this rule, not an instruction. Asking a model, or a person,
> to remember to update the old entry fails quietly and constantly.*

KennisBank is built on the opposite assumption: four LLM seams maintain the truth
(`judge`, `judge_reconcile`, `judge_supersede`, `judge_recheck`). All four sat at
zero, and the only one measured scored 7/20.

Its second contribution is the distinction itself:

| | meaning | correct update |
| --- | --- | --- |
| **state** | one current value, and it changes | **replace** |
| **event** | a timestamped thing that happened | **append** |

`memory_type` (`feit` / `voorkeur` / `procedure` / `beslissing`) is a subject
axis, not an update axis. None of those four says "replace me when the value
changes".

What KennisBank already has and most second brains do not: `status: current`
which recall filters on, `superseded_by` + `valid_until` without ever deleting,
100% dated frontmatter, and a review queue. Exactly two things are missing: the
update axis, and an invariant that something checks.

## Design

### Artifact 1: `volatility: state | event` in the frontmatter

`_extract` stamps it per candidate, `_memory.render` persists it, `_reconcile`
and `_maintenance.supersede_pass` obey it:

```
event     -> is NEVER superseded and NEVER supersedes
state     -> may replace and be replaced
absent    -> event, and the audit lists it
uncertain -> event, and the audit lists it
```

An absent field must degrade to `event`, because destroying history is the
irreversible error and because existing memories then need no migration.

**But the default silently opts out of the feature this design exists for.** A
weak local model that hesitates labels everything "never correct me", and the
layer goes on rotting with a clean conscience. The safe default and the goal pull
in opposite directions, so the default alone is not an answer. Three mitigations,
in order of confidence:

1. `kb-state-audit` (artifact 2) reports every memory that looks state-shaped —
   it carries a model tag, a threshold, a version, a path — but is labelled or
   defaulted to `event`. Uncertainty becomes visible instead of permanent.
2. Config-shaped claims are classified deterministically as `state`, without a
   model, because their shape is recognisable by pattern.
3. Volatility is re-derivable: a later pass may relabel, since the field is
   metadata rather than history. Nothing is lost by getting it wrong at first.

This removes the destructive decision from the model for half the corpus. Today
`supersede_pass` at 0.85 can pit two events against each other and close one.
That becomes structurally impossible.

### Artifact 2: `kb-state-audit.py`, deterministic

The skill's script, but for this vault's value types: model tags, thresholds,
version numbers, paths, toggle states. With one advantage the skill does not
have: there is an **authority** to compare against — `kennisbank-embed.json`,
`kennisbank-llm.json`, `kennisbank-settings.json`.

Output follows the skill's three piles, plus a mandatory coverage line:

```
CONTRADICTED  4    memory says qwen3-embedding:8b, config says qwen3-embedding:4b
UNSUPPORTED   n    a claim whose value appears nowhere
CONFIRMED     n
COVERAGE      n    current memories with no checkable value -- here I was blind
```

No LLM. Reports, never mutates.

### Artifact 3: one invariant, checked but not enforced

> At most one `current` **state** memory per subject.

The skill's `## Current State` section, translated to a vault without pages. A
violation is a line in a report, not an intervention; the review queue decides.

"Subject" is **not** hand-assigned. The skill warns against exactly that (*"a
wrong merge destroys information"*). Subject = a cluster above a measured cosine
threshold, and P1 supplies it: the real pairs sit at p25 = 0.824, median 0.897.

### What P1 changes about the design

| assumed earlier | what the measurements say |
| --- | --- |
| widen the candidate set | unnecessary: 95% in top-2, 100% in top-5 |
| 0.85 is a fine threshold | lower it to ~0.75; the valuable band is 0.67-0.85, and the cost is 163 pairs |
| dedup before the judge saves 41% of calls | **dropped**: the living corpus holds one pair above 0.95 |
| supersede_pass is the self-correcting mechanism | **wrong**: it has 11 pairs; the weight belongs on `reconcile` at write time |
| a better model fixes the judge | partly: it fixes the definitional error, not dedup-vs-update |
| the 107 labels are usable | only within the 0.70-0.90 band |
| raising max_chunks fixes intake | **half**: four of ten transcripts yield zero chunks regardless |

Three concrete changes follow:

1. `_maintenance.supersede_pass`: threshold 0.85 → 0.75 (11 → 163 candidate
   pairs, about three minutes of judge time for the whole corpus)
2. `_reconcile.TOP_K`: 2 → 3 (95% → 97%, negligible cost)
3. per-seam provider routing (below)

### Per-seam provider routing

`_llm.providers()` is one chain for every seam. That makes it impossible to send
reconcile to a stronger model without dragging extraction along — and extraction
is the seam that would ship raw transcript chunks.

| seam | calls | payload | proposal |
| --- | --- | --- | --- |
| extract | ~32 per transcript, ~8000 per rebuild | raw chunk, 6000 chars | local |
| judge | ~3 per chunk | candidate text | local |
| reconcile | ≤2 per written memory | two distilled bodies | chain, cloud allowed |
| supersede_pass | only pairs above the threshold | same | chain, cloud allowed |

The seam that could go to the cloud also carries by far the smallest and cleanest
payload. That is not a coincidence, but it is a welcome property.

Two blockers in the code:

- `_llm._call` invokes `claude -p` **without `--model`**, so
  `models: {"claude-cli": "haiku"}` does nothing today and you silently get the
  session default.
- One chain for all seams (above).

Cost and latency, measured: `claude -p` takes 16-25 s per call, almost
independent of the model — that is agent startup, not inference. Fine for the
small seams (~10 calls per sweep, detached). Unusable for a full rebuild
(8000 calls × 20 s ≈ 44 hours). Batching (N pairs per call) is the optimisation
that closes that gap.

**This reverses a recorded decision.** `CLAUDE.md` says "Lokaal, altijd", and a
memory from 2026-07-02 records: *"Gebruik een lokaal generatie-model via Ollama
in plaats van headless Claude om cloud-leaks te voorkomen."* Cloud per seam is
therefore an explicit user choice, with the existing loud stderr warning and the
`is_local` heartbeat flag left intact.

## Sequence

```
0. merge think:false            <- without it every measurement is noise
1. intake: parse every transcript, then read all of it, gated on P5
2. volatility field             <- makes replacement safe
3. thresholds: 0.85 -> 0.75, TOP_K 2 -> 3
4. kb-state-audit               <- proves it, and keeps proving it
5. per-seam routing + --model   <- optional, an explicit choice
```

Step 1 has two halves, and the smaller one comes first: four of ten transcripts
yield zero chunks, so `transcript_text()` is fixed before `max_chunks` is touched.
Reading more of a transcript the parser cannot read at all buys nothing.

Step 1 before step 2, for the reason the skill states and this vault measured: no
structure and no judge repairs a fact that was never written down. And because
P1c showed the after-the-fact mechanism has eleven pairs to work with, the weight
of this design sits on `reconcile` at write time — which only ever sees what
intake delivered.

## Proof

| # | measurement | LLM | what it decides |
| --- | --- | --- | --- |
| P1 | cosine + rank of the 107 pairs | no | **done**: search is not the bottleneck |
| P1c | candidate pairs per threshold over the whole corpus | no | **done**: 0.75 is affordable; supersede_pass has almost no work |
| P2 | capture rate against a labelled set of facts known to sit in transcripts, per chunk position | yes | replaces the single-anecdote check; measures intake, not one lucky fact |
| P3 | dry run over the corpus: how many statuses would change, and how many of those are `event`? | yes | the safety line: one superseded event is a bug, not a trade-off |
| P4 | monthly: `kb-state-audit` plus the audit method | no | whether the count falls |
| P5 | kb-eval on the existing question sets, before and after the corpus grows | no | **the gate on step 1**: more memories must not push the right one out of `retrieve_top_n` |

P2 as originally written — "does a memory asserting `qwen3-embedding:4b` exist
afterwards" — proves that one fact the author already knew about got picked up.
That is an anecdote with a checkbox. It stays as a smoke test, not as evidence.

## Risks and honest expectations

**Full coverage makes the layer bigger, and may make recall worse.**
`retrieve_top_n` is 3. Multiplying the corpus means multiplying the competition
for three slots, and a fact that is captured but ranks fourth is exactly as
invisible as a fact that was never captured. Yield and cost are not enough:
step 1 is gated on P5, an eval run on the existing question sets before and
after. Dedup, judge and reconcile also have to carry the volume, and reconcile is
the weak link.

**A wrong SUPERSEDE is reversible on disk and invisible in practice.** KennisBank
never deletes: the file stays, with `superseded_by` and `valid_until`. But recall
filters on `current`, and `/kennisbank:review` walks the **unverified** queue
only — a wrongly closed memory surfaces nowhere. An earlier draft of this design
called the review queue the safety net for superseding. It is not, and no
aggressive threshold is justified until there is an entry point for closed
memories. Either the review command gains a superseded queue, or the audit
reports recent supersessions for a human to glance at.

**Steps 2 and 4 do not fix the four cases found.** Step 1 does. Steps 2 and 4
keep case five from happening.

**The silent fail-safes are a risk in themselves.** `except Exception: 0` in
`memory-sweep.py` makes a failure indistinguishable from an idle run. Part of
step 4: the passes report why they did nothing.

## Open questions

1. What is the right `max_chunks` after step 1: unlimited, or a higher ceiling
   with a measurement of what each extra chunk yields?
2. Should the embeddings cache with foreign `embed_id` entries be cleaned out, or
   is a clean index enough? This drives the runtime of every maintenance pass.
3. Does the user want cloud routing per seam, given that it reverses a recorded
   local-always decision?
4. Where does a wrongly superseded memory surface? Without an answer, no
   threshold below 0.85 should be enabled: today nothing shows a closed memory to
   a human, and recall filters it out.
5. Why does `transcript_text()` return nothing for four of ten transcripts? Until
   that is understood, the size of the intake gap is unknown — it may be far
   larger than the 19% coverage figure suggests.

## Revision history

- 2026-08-12, first draft.
- 2026-08-12, revised after an adversarial review of this document. Four claims
  did not survive: deduplication before the judge (the living corpus holds one
  pair above 0.95), `supersede_pass` as the self-correcting mechanism (eleven
  pairs total), the review queue as a safety net for superseding (it covers
  unverified only), and P2 as evidence (it tests one known fact). Two findings
  were added: four of ten transcripts parse to zero chunks, and corpus growth may
  push the right memory out of `retrieve_top_n`.
