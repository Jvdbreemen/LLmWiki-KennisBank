---
description: Herbouw de opt-in provenance-first index van lokale raw sources
---

# /kennisbank:rebuild-source-index

Bouwt de geïsoleerde `kb-source.db` opnieuw op uit goedgekeurde lokale
tekstbronnen (`01-raw`, `05-bronnen`, `08-archive`). De database is afgeleid en
de builder gebruikt staging plus een atomische swap; raw files en memory-status
worden niet gewijzigd.

Deze index is geen bewijs dat source recall nuttig is. Draai hem alleen voor
een expliciete evaluatie of wanneer `source_explicit_recall` bewust opt-in
staat. De builder maakt uitsluitend een lokale FTS5-projectie en roept geen
embeddingbackend aan; een fout laat de vorige index staan.

```bash
python3 "$KENNISBANK_VAULT/.claude/scripts/build-source-index.py" --rebuild
```

Rapporteer daarna het JSON-resultaat, inclusief `sources`, `indexed_chunks`,
`failed_sources` en `redacted_sources`. Bij failures geen bestaande index
verwijderen; eerst de oorzaak onderzoeken.

Meet na een grote rebuild desgewenst de warme productbudgetten:

```bash
python3 "$KENNISBANK_VAULT/.claude/scripts/benchmark-source-recall.py" \
  "<gerichte bronquery>" --iterations 30
```
