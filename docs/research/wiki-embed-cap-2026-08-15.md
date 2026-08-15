# Does the 4000-character embedding cap actually cost recall?

**2026-08-15 — TASK-164. Pre-registration, written and committed before any
number exists.**

## What the cap is, and why it is not a lazy default

`_embeddings.doc_text(path, cap=4000)` truncates every document before
embedding, and `build-kb-index.py` stores the same truncated text in
`fts_docs`. So **both retrieval arms are blind past 4000 characters**, not only
the vector one.

I filed this as an oversight. It is not. The cap is load-bearing, and the code
says so:

    OLLAMA_NUM_CTX = 2048
    #: 16384 ctx costs 6.24 GB of VRAM, 2048 costs 4.06 GB … The vault's
    #: longest embedded document is ~1000 tokens (doc_text caps it) …
    #: Raise this if documents ever grow past it: truncation WOULD change
    #: vectors and silently invalidate the index.

The two settings are coupled on purpose: the cap exists so a document fits
inside a context window that was shrunk to free 2.18 GB, which is what lets a
judge model stay resident beside the embedding model. Measured just now:

    2000 chars -> vector    4000 chars -> vector
    6000 chars -> None      8000 chars -> None      13077 chars -> None

Above the cap the call does not truncate, it **fails**. Raising `cap` would not
give longer documents worse vectors; it would drop 72 articles out of the index
entirely, because `get_cached` returns None and the builder skips the document.

That kills the cheap fix before it is measured, and it narrows the options to
one:

| option | consequence |
| --- | --- |
| raise `cap` | 72 articles vanish from the index |
| raise `num_ctx` | +2.18 GB VRAM, evicts the judge model — the thing the setting exists to prevent |
| **chunk the document** | each window ~375 tokens, far inside 2048, no VRAM change |

## What is actually hidden

    206 real articles (index.md and log.md are already skipped by the builder)
     72 over the cap = 35.0%
    133,767 of 803,805 characters unreachable = 16.6%

An earlier note said 23.1%. That counted `index.md` and `log.md`, which the
builder never indexes. And 16.6% is a fraction of *characters*, not of
retrievable facts — a document's tail is not uniformly informative. The number
below is the one that matters.

## The instrument, and why the existing eval set is not it

The 329-question wiki set **cannot see this defect**. Every question comes from
a title, its tags, the FIRST heading, or an LLM paraphrase of `body[:400]`
(`kb-eval-gen.py:150`) — all of it inside the embedded head. Run it against a
cap fix and it reports "no difference", which would mean only that the
instrument is blind.

The mirror-image error is as easy: paraphrase text from beyond the cap, and the
fix wins by construction because the questions are paraphrases of content only
the fixed index can see.

So the questions are neither generated nor paraphrased. They are each article's
own **markdown headings positioned beyond 4000 characters** — human-written,
selected by position rather than content, and phrased the way a terse search
actually looks. **80 questions across 28 articles.**

Stated limits, before the numbers:

- A heading is short and distinctive, so this likely **overstates** what a fix
  buys on natural prose questions. Treat it as an upper bound.
- `expect` is one document; a topically adjacent article ranking first is a miss.
- Only 28 of the 72 over-cap articles have a heading past the cap, so the set
  covers the defect where it is easiest to probe, not everywhere it exists.

## The rule, fixed now

Primary metric: **recall@5 on the 80-question tail set**, wiki layer, against
the live index.

1. **If tail recall@5 is already above 0.60**, the cap costs less than the
   character fraction suggests. Report that and do not build chunked indexing.
2. Otherwise, chunked indexing ships only if it **raises tail recall@5 by at
   least 15 percentage points** *and* **does not lower the existing
   329-question set's recall@5 by more than 1 point**.
3. Whatever happens, both numbers are written down here, including a loss.

Rule 1 exists so the measurement can end the work. TASK-145 pre-registered a
rule that looked obviously right and lost (recall@5 0.778 → 0.768), and the
pre-registration is the only reason that was reported instead of rationalised.

## Results

*(to be filled in by the run — this section is empty at commit time on purpose)*
