# Autonomous memory review — no human in the loop

**2026-08-16 — design, on request, before any code. The goal as stated by the
owner: the memory layer must run without human intervention. Safety comes from
evidence and reversibility, not from a person approving things.**

## The problem, measured

The capture judge is fail-safe: anything not explicitly high-certainty lands as
`unverified`. That is the right bias for a writer — but `recall_hits` filters
on `status=current`, so an unverified memory is not "pending", it is
**invisible**. Today that is 993 memories (about a third of the layer), growing
by roughly two for every one the judge promotes. `/kennisbank:review` was the
designated exit, and the review log has one line ever. The queue design assumed
a reviewer who does not exist.

Two consequences fix the design's priorities:

- **Doing nothing is the worst policy.** A wrongly promoted memory is one bad
  hit in a ranked list; a wrongly quarantined one is knowledge that does not
  exist. The status quo wrongly quarantines by the hundreds.
- **Retraction is the only dangerous act**, and it is already reversible:
  `retracted` is a status, `_memory.reopen()` (TASK-150) undoes it losslessly,
  and every closure logs its cause and prompt version.

## Evidence this design stands on (all measured in this vault, 2026-08-15/16)

| finding | number | source |
| --- | --- | --- |
| `supported` verdicts never fabricate their evidence | 0 fabricated quotes / 210, CI 0–1.8% | TASK-163 |
| grounded verification is deterministic | 56/56 same-run, 11/11 cross-run | TASK-163 |
| `unsupported` from one passage was never right when checked | 0 of 20 confirmed on exhaustive adjudication | TASK-163 |
| whole-transcript adjudication by the client LLM survives adversarial review | 0 refuted / 27, and 0 / 40 | TASK-161/163 |
| the extractor does not invent facts | 0 confirmed inventions in every exhaustive check | TASK-163 |
| passage coverage without a stamp | 87.8% (windowed retrieval) | TASK-163 |
| quarantine with an exact `source_chunk` stamp | 571 of 993 (58%), 100% of new captures | TASK-169 sweep |

The asymmetry those numbers describe is the design: **a positive verdict from
a grounded check is trustworthy enough to act on alone; a negative verdict is
only trustworthy after exhaustive, independent confirmation.**

## The pipeline: three traps, each cheaper than the next

### Trap 1 — grounded promotion (local model, every sweep)

For each unverified memory, ask the local model the TASK-163 question — *does
this passage say this?* — against its own source:

- **stamped** (58% now, 100% of new captures): the passage is a lookup,
  `chunk_from_stamp()`, no retrieval involved;
- **unstamped**: windowed retrieval (IDF top-8 → 1500-char windows → best 4 by
  cosine), 87.8% measured coverage.

Verdict `supported` → **promote to current**, logged with prompt version.
Anything else → escalate. Never demote here: of the twenty `unsupported`
verdicts this session adjudicated exhaustively, not one survived — a single
passage cannot distinguish a retrieval miss from a false memory.

Cost: one local LLM call per memory (~6–8s). The backlog is ~2 hours of GPU;
the steady state is ~40 memories per sweep, minutes, off the hot path.

### Trap 2 — client-LLM adjudication (batched, the escalation path)

What trap 1 could not support gets the treatment that proved itself on 67
cases today: a client-LLM reader with the **whole transcript**, searching in
Dutch AND English, on identifiers as well as prose, returning a verbatim quote
as evidence. Verdicts:

- support found (anywhere in the transcript) → **promote**;
- `absent` — the subject appears nowhere after exhaustive search → candidate
  for retraction, which requires trap 3;
- disagreement or low confidence → stays unverified, retried next cycle.

Batched like today's labelling runs: ~15 memories per agent, transcript on
disk, structured output. Estimated backlog cost if trap 1 escalates 30%:
~300 memories ≈ 20 agents ≈ 1.5M tokens.

**Execution vehicle:** a case-bundle generator (`kb-autoreview.py --bundle`)
plus a driver that runs the client LLM headless (`claude -p`, the adr-kit
"host" pattern) or as an in-session workflow. Same bundles either way, so the
interactive and scheduled paths cannot drift apart.

### Trap 3 — retraction, only on double agreement

A memory is retracted only when **two independent readers using different
methods** agree it is unsupported: the local grounded check (trap 1) said not
supported, AND the client-LLM exhaustive search (trap 2) returned `absent`,
AND an adversarial second client reading — instructed to refute, the protocol
that returned 0/27 and 0/40 today — fails to overturn it. Bounded per run
(cap 50), every retraction in the closed-log with both verdicts, reversible
by `reopen()`.

No terminal limbo: a memory that survives two full cycles undecided stays
`unverified` deliberately — it is invisible either way, and an undecidable
case is exactly the one an autonomous system should not force.

## Privacy gate

Trap 2/3 sends memory bodies and transcript excerpts to the client LLM — that
is cloud, and "Lokaal, altijd" requires explicit consent. One settings toggle,
**`auto_review_llm`, default OFF** in the shipped repo; trap 1 is local-only
and can default ON. The owner's request for this design is the consent for
this vault; the default protects every other deployment.

## What happens to `/kennisbank:review`

It stops being a work queue and becomes an audit view: recent promotions with
their evidence quotes, recent retractions with both verdicts, and a one-command
undo per line (`reopen`). The human step disappears; the human *oversight*
surface improves, because today's queue shows no evidence at all.

## Pre-registered gates (to be fixed in numbers before building)

- **G0 — measure first.** A stratified 60-case sample of the quarantine gets
  the full trap-2 treatment before any code ships, yielding the base rates:
  what fraction of the quarantine is supported / elsewhere-supported / absent.
  Every later gate is calibrated on this.
- **G1 — promotion precision ≥ 0.95** on that adjudicated sample, judged
  against the exhaustive verdicts. (The asymmetry is stated: even 0.90 beats a
  status quo of 100% invisible, but 0.95 is the bar because promotion is
  autonomous.)
- **G2 — zero false retractions** on the sample, with the dual-reader
  requirement exercised, before the retraction path is enabled anywhere.
- **G3 — no regression** on the 1224-question memory eval and the freshness
  dev set after the backlog is processed: promotion changes the recall pool's
  composition, and that change must be measured, not assumed benign.

TASK-145 and TASK-162 are the precedent: a gate that fails gets reported and
the change does not ship. The gates go into the research doc with the numbers
blank, committed before the first run.

## Build order

1. G0 sample + adjudication (no product code; reuses today's workflow).
2. Trap 1 as a sweep maintenance pass (`verify_pass`), gated by G1.
3. Backlog run for trap 1 + G3 measurement.
4. Bundle generator + headless driver for trap 2, gated on `auto_review_llm`.
5. Trap 3 retraction, gated by G2, capped.
6. `/kennisbank:review` becomes the audit view; docs updated.

Each step lands separately with its own tests; a failed gate stops the line
exactly where it stands, with everything before it still shipped and useful.
