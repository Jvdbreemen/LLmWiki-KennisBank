# Sparse-first source recall: independent development result

Date: 2026-08-31  
Branch: `codex/source-recall-experience-evidence`  
Decision: **reject sparse-first vector reranking before frozen holdout**

## Protocol

The experiment used 30 owner-reviewed development cases outside the
repository: 20 positive source-recall cases over 20 unique documents and 10
hard negatives. The selection code rejects overlap with the frozen source
holdout by id, normalized query, and expected source path. Before model work it
also validates every positive source hash, reviewed character window, and FTS
body snapshot against the live vault.

The grid was committed before execution:

- candidate documents: 20, 50, 100;
- maximum candidate passages: 40, 100;
- minimum cosine: 0.40, 0.55, 0.70;
- chunking: 2,000 characters with 200 overlap;
- top-k: 5;
- model: `ollama:qwen3-embedding:4b` for documents and queries.

Selection required no-hit specificity at least 0.95 and warm p95 below 2,000
ms, then maximized development hit@5. Passage embeddings were cached by exact
content hash and model id in one shared SQLite cache; exact query embeddings
were reused across measured and warm runs. Production usage telemetry was
disabled. The evaluator had no write path to a production index.

## Results

No one of the 18 configurations passed both constraints. The selector recorded
the best available unsafe point rather than silently approving it.

| metric | sparse-first best available | pure BM25 on same dev set |
|---|---:|---:|
| hit@1 | 0.20 | 0.45 |
| hit@5 | 0.25 | 0.75 |
| MRR | 0.2125 | 0.5433 |
| passage hit@5 | 0.15 | not applicable |
| citation precision | 0.40 | not measured at passage level |
| exact provenance precision | 1.00 | source-path only |
| no-hit specificity / precision | 0.90 | 0.00 |
| warm/query p50 | 1,074 ms | 24.2 ms |
| warm/query p95 | 8,332 ms | 50.4 ms |

The selected unsafe configuration used 100 candidate documents, 40 candidate
passages, and cosine 0.70. The content-addressed calibration cache contained
2,731 passage vectors and occupied 33,939,456 bytes, 3.1% of the
1,105,334,272-byte FTS baseline. Cold calibration took roughly 42 minutes on
the local backend. That one-time cost is not the online gate, but it is relevant
maintenance evidence.

## Critical interpretation

The sparse design solves neither side of the proposed bargain. Compared with
BM25 it trades away 0.50 absolute hit@5 and adds orders of magnitude latency,
yet its cosine threshold still abstains incorrectly on one of ten hard
negatives. Candidate coverage was not enough: vector reranking and passage
selection actively degraded document retrieval on this development set.

The small cache is the only favorable operational result. Storage efficiency
does not compensate for missing the evidence, abstention, and latency gates.
A naive full-corpus vector database is even less justified: this bounded
variant already fails before paying full ingest and rebuild costs.

## Decision boundary

The frozen 60-case source holdout was not run. The 50-case paired answer and
citation review was not generated. Both are downstream confirmation steps for
a candidate that first clears independent development constraints; using them
after this pre-reject would spend human labels and risk test-set tuning without
a deployable route.

The explicit decision is:

- reject this sparse-first vector reranker;
- reject naive full-corpus pre-embedding;
- retain full-document lexical search only as a labelled, explicit evidence
  lookup baseline, not as an automatic no-hit-safe fallback;
- preserve the frozen holdout for a materially different future design.

Private aggregate reports bind the development input, frozen input, FTS index,
git revision, and model ids by SHA-256. Queries, passages, expected source
paths, and review windows remain outside the repository. The selection report
hash is `44b6d1d46fa5e572a891b241406dd2174cdbeff59e4522813c31ac3e297956e5`;
the same-dev/same-index lexical report hash is
`a3abc32ba0faacd23a58bc2b5dbc70cbd868448bd1ae0e567afaef2363094460`.

Final regression evidence: 1,886 repository tests passed with 3 skips in
683.99 seconds on Python 3.12, using a writable basetemp outside the Git
worktree.
