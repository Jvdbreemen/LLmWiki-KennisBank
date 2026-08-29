---
description: Raadpleeg expliciet raw-source evidence met provenance
---

# /kennisbank:source-recall

Gebruik source recall alleen voor een expliciete reconstructie, verificatie of
lage-confidence fallback. Raw evidence blijft apart van wiki en memory; citeer
altijd pad, hash en passage-offsets. Een resultaat is geen geconsolideerde
waarheid en mag geen memory automatisch promoveren.

De technische gateway accepteert `explicit`, `verify`, `reconstruct` en
`fallback`. De route blijft standaard uitgeschakeld totdat de source-holdout de
rollout-gates haalt.

Een succesvolle response heeft de vorm:

```json
{
  "status": "ok|no_hit",
  "mode": "explicit|verify|reconstruct|fallback",
  "flags": ["stale|superseded|conflict|low_confidence|no_hit"],
  "hits": [{
    "source_path": "...",
    "source_hash": "sha256:...",
    "chunk_index": 0,
    "start": 0,
    "end": 100,
    "retrieval_mode": "verify",
    "confidence": {
      "cosine": 0.81,
      "lexical_match": true,
      "fresh": true
    }
  }]
}
```

`disabled`, `unavailable` en `not_routed` zijn fail-open responses met een
lege `hits`-lijst. Een bronhit is evidence, geen memory-write-opdracht.

```bash
printf '%s\n' '{"mode":"explicit","prompt":"<vraag>","k":5}' |
  python3 "$KENNISBANK_VAULT/.claude/scripts/kb-source-recall.py"
```

Bij `disabled`, `unavailable` of `not_routed` moet de assistent geen passage
verzinnen en terugvallen op normaal antwoordgedrag.
