---
description: Raadpleeg expliciet raw-source evidence met provenance
---

# /kennisbank:source-recall

Gebruik source recall alleen voor een expliciete reconstructie, verificatie of
best-effort evidence search. Raw evidence blijft apart van wiki en memory; citeer
altijd pad, hash en passage-offsets. Een resultaat is geen geconsolideerde
waarheid en mag geen memory automatisch promoveren.

De technische gateway accepteert `explicit`, `verify` en `reconstruct`.
`fallback` is bewust `policy_disabled` en kan normale recall niet beïnvloeden.
De route blijft standaard uitgeschakeld via `source_explicit_recall`.

Een succesvolle response heeft de vorm:

```json
{
  "status": "ok|no_hit",
  "mode": "explicit|verify|reconstruct",
  "flags": ["stale|missing|redacted|conflict|no_hit"],
  "retrieval_route": "lexical_fts",
  "best_effort": true,
  "hits": [{
    "source_path": "...",
    "source_sha256": "sha256:...",
    "passage_sha256": "sha256:...",
    "chunk_index": 0,
    "start": 0,
    "end": 100,
    "retrieval_mode": "explicit",
    "confidence": {
      "basis": "bm25",
      "best_effort": true,
      "fresh": true
    },
    "source_ref": {"source_ref_id": "sr_..."}
  }]
}
```

`disabled`, `unavailable`, `policy_disabled` en `not_routed` zijn fail-open responses met een
lege `hits`-lijst. Een bronhit is evidence, geen memory-write-opdracht.

```bash
printf '%s\n' '{"mode":"explicit","prompt":"<vraag>","k":5}' |
  python3 "$KENNISBANK_VAULT/.claude/scripts/kb-source-recall.py"
```

Bij `disabled`, `unavailable` of `not_routed` moet de assistent geen passage
verzinnen en terugvallen op normaal antwoordgedrag.
