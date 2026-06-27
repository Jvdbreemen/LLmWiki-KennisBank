---
description: Her-extraheer ALLE geheugen uit gearchiveerde transcripts (zwaar, vraagt bevestiging)
---

# /kennisbank:rebuild-memory

Her-extraheert het ruwe agent-geheugen (`09-memory/`) uit ALLE gearchiveerde
transcripts in `01-raw/transcripts/`, los van de `.swept`-watermark. Dit is een
**zware** operatie: het draait de LLM-extractie + judge over je hele
transcript-backlog. Vrijwel idempotent — semantische dedup (cosine) voorkomt
vrijwel altijd dubbele memories, maar het is geen exacte garantie bij sterk
afwijkende her-extractie.

**Vraag eerst expliciete bevestiging** (dit kan veel LLM-werk zijn). Pas na "ja":

```bash
python3 "$KENNISBANK_VAULT/.claude/scripts/memory-sweep.py" --all
```

Toon daarna de samenvattingsregel (verwerkte transcripts, geschreven memories,
duplicaten, fouten). Bij "model onbereikbaar": meld dat Ollama/het LLM niet
draait; er wordt niets gemarkeerd of geschreven.

Voor alleen de zoekindex herbouwen (niet her-extraheren): gebruik
`/kennisbank:rebuild-index`.
