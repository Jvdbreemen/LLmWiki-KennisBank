---
description: Herbouw de lokale zoekindex kb-index.db uit de vault-markdown (snel, deterministisch)
---

# /kennisbank:rebuild-index

Herbouwt `kb-index.db` (de hybride sqlite-vec + FTS5 zoekindex) volledig opnieuw
uit de markdown-files. Snel en deterministisch; raakt **geen** markdown -- de
index is een wegwerp-cache. Gebruik dit na een modelwissel, na bulk-import, of
als de index achterloopt.

Draai:

```bash
python3 "$KENNISBANK_VAULT/.claude/scripts/build-kb-index.py" --rebuild
```

Toon daarna de samenvattingsregel die het script print (aantal files, (re)indexed,
verwijderd, backend). Bij "embedmodel onbereikbaar": meld dat Ollama niet draait;
de index blijft staan zoals hij was.
