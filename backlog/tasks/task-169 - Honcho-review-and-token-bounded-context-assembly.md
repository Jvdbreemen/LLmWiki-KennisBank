---
id: TASK-169
title: Honcho review and token-bounded context assembly
status: Done
assignee: []
created_date: '2026-08-15 10:00'
updated_date: '2026-08-15 10:00'
labels: []
dependencies: []
ordinal: 102100
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Review plastic-labs/honcho (AGPL-3.0 memory infrastructure for stateful agents)
against KennisBank's architecture, record the findings as a research document,
and adopt the one idea that closes a real gap: a hard size bound on assembled
context.

`scripts/context-budget.py` is named for a budget it does not enforce. L0-L3 are
nesting layers, not sizes, and L3 inlines full article bodies with no ceiling —
a three-article L3 answer can be an order of magnitude larger than a one-article
answer with no signal to the caller. Honcho's `/context` endpoint treats the
token bound as a first-class request parameter and packs to fit; that shape is
portable to a local, dependency-free implementation.

Licence boundary: Honcho is AGPL-3.0, KennisBank is MIT. API shapes and ideas
transfer; no code may be copied.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Research document in docs/research/ covering Honcho's architecture, the convergences with KennisBank, the ideas worth adopting and the ones deliberately rejected, with the AGPL/MIT boundary stated
- [x] #2 context-budget.py accepts a token ceiling (--max-tokens plus KB_CONTEXT_MAX_TOKENS) and never emits output above it, except when identity alone exceeds it
- [x] #3 Trimming is deterministic and rank-respecting: bodies before relevant before active, lowest-ranked entry first; identity is never dropped
- [x] #4 No silent truncation — output reports the ceiling, the estimate and what was dropped
- [x] #5 Default behaviour is unchanged: without a ceiling the output is byte-identical to before
- [x] #6 Unit tests for the pure budget functions, no vault, no network
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Review in docs/research/honcho-memory-architecture.md. Adoption is
`estimate_tokens()` + `fit_to_budget()` in context-budget.py, both pure and
state-injected in the style of the existing `select_layers()`, plus `--max-tokens`
and `KB_CONTEXT_MAX_TOKENS` on the CLI. 24 new tests; suite green at 1123.

Three decisions worth carrying forward.

TRIM ORDER IS ARGUED FROM RECOVERABILITY, not from a weight table. `bodies` goes
first because `relevant` still carries path and snippet, so the content is one
read away; `relevant` goes next because a search reproduces it; `active` is a
convenience summary. `identity` is not in the trim order at all — it is the
contract the rest of the answer is read against, and a half-truncated contract is
a worse failure than an honest overrun. When identity alone exceeds the ceiling
the output reports `within_budget: false` and leaves the text whole.

THE ESTIMATE IS DELIBERATELY NOT A TOKENIZER. ~4 chars/token, stdlib only.
Importing a real tokenizer would put a model load on the one path whose purpose
is to be cheap — the self-defeating trade. Documented as approximate at the flag,
in CONFIGURATION.md and in the module docstring; callers should leave headroom.
The `_budget` block itself (a few dozen tokens) sits outside the ceiling.

REPORTING IS UNCONDITIONAL ONCE A CEILING IS ASKED FOR, including when nothing
was dropped. A trim that reports only on trimming teaches the reader to treat
silence as "everything was included", which is exactly the cruft this repo's
principles reject.

Correction carried into the review document: the first-pass reading claimed
KennisBank lacks a stated-versus-inferred axis outright. Reading _memory.py
showed `status`, `evidence_basis` and `memory_type` each cover part of it, so the
gap is real but narrower — hence TASK-171 gates the schema change behind a
measurement rather than assuming it.

One pre-existing fragility fixed in passing: TestEnvIntFailSoft._run inherits the
developer's environment, so a set KB_CONTEXT_MAX_TOKENS would have added a
_budget key and failed an unrelated key assertion. Pinned to "0" in the helper.
<!-- SECTION:NOTES:END -->
