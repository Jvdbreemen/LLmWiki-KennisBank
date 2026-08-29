---
description: Herbouw de opt-in provenance-first index van lokale raw sources
---

# /kennisbank:rebuild-source-index

Bouwt de geïsoleerde `kb-source.db` opnieuw op uit goedgekeurde lokale
tekstbronnen (`01-raw`, `05-bronnen`, `08-archive`). De database is afgeleid en
de builder gebruikt staging plus een atomische swap; raw files en memory-status
worden niet gewijzigd.

Deze index is geen bewijs dat source recall nuttig is. Draai hem alleen voor
een expliciete evaluatie of wanneer `source_recall` bewust opt-in staat. De
embeddingroute moet lokaal blijven; een fout laat de vorige index staan.

```bash
python3 "$KENNISBANK_VAULT/.claude/scripts/build-source-index.py" --rebuild
```

Rapporteer daarna het JSON-resultaat, inclusief `sources`, `indexed_chunks`,
`failed_sources` en `redacted_sources`. Bij failures geen bestaande index
verwijderen; eerst de oorzaak onderzoeken.
