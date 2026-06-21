Voer een sessie-check uit en geef een compact overzicht om de sessie mee te starten.

## Doel
Tegenhanger van `/sessielog`. Lees vault-context, memory, wiki-status en recente activiteit voordat je begint met werken. Read-only, snel, geen mutaties.

## Context-lagen (L0-L3)

Laad vault-context progressief op basis van wat de sessie nodig heeft. Standaard L1 (identity + actieve status):

```bash
python3 ~/KennisBank/.claude/scripts/context-budget.py --level 1
```

Diepere niveaus op verzoek:
- `--level 2 --query "<onderwerp>"` voegt relevante wiki-artikelen toe (L2).
- `--level 3 --query "<onderwerp>"` voegt ook de volledige artikelteksten toe (L3).

Dit vult de cozempic-context-hygiëne aan, het vervangt die niet.

## Stap 1: Lees vault-context
```bash
cat ~/KennisBank/CLAUDE.md
```
Vat in één zin samen: vault-eigenaar en actieve projecten.

## Stap 2: Lees memory-index
```bash
MEMORY=$(ls ~/.claude/projects/*/memory/MEMORY.md 2>/dev/null | head -1)
[ -n "$MEMORY" ] && cat "$MEMORY"
```
Toon aantal memory-entries en hun titels. Geen memory gevonden: meld "geen memory gevonden, eerste sessie".

## Stap 3: Wiki-overzicht
Lees de index als die bestaat:
```bash
[ -f ~/KennisBank/02-wiki/index.md ] && head -50 ~/KennisBank/02-wiki/index.md
```
Tel artikelen per status:
```bash
grep -l "status: actief" ~/KennisBank/02-wiki/*.md 2>/dev/null | wc -l
grep -l "status: concept" ~/KennisBank/02-wiki/*.md 2>/dev/null | wc -l
grep -l "status: stabiel" ~/KennisBank/02-wiki/*.md 2>/dev/null | wc -l
grep -l "status: archief" ~/KennisBank/02-wiki/*.md 2>/dev/null | wc -l
```

## Stap 4: Recente sessies
Laatste 5 sessielogs, alleen filenames:
```bash
ls -1t ~/KennisBank/01-raw/sessies/*.md 2>/dev/null | head -5
```

## Stap 5: Recente wiki-updates
Artikelen gewijzigd in de laatste 7 dagen:
```bash
find ~/KennisBank/02-wiki/ -name "*.md" -mtime -7 -type f 2>/dev/null
```

## Stap 6: Inbox-status
```bash
ls -1 ~/KennisBank/00-inbox/ 2>/dev/null | grep -v '^\.' | wc -l
```
Als > 0: suggereer `/intake`.

## Stap 7: Graphify-flag
```bash
[ -f ~/KennisBank/graphify-out/.needs-rebuild ] && echo "stale" || echo "ok"
```
Als stale: meld "wiki-graph is stale, overweeg `/graphify` rebuild".

## Stap 8: Stale-status
Quick check, geen volledige `stale-check.py` run (te traag voor sessiestart):
```bash
find ~/KennisBank/02-wiki/ -name "*.md" -mtime +60 -type f 2>/dev/null | wc -l
```
Als > 5: suggereer `/stale` om te reviewen.

## Stap 9: Research-overzicht (optioneel)
Recente research-bestanden in de laatste 7 dagen:
```bash
find ~/Claude/research/ -name "*.md" -mtime -7 2>/dev/null | head -3
```

## Stap 10: Briefing samenvatten
Lever een compact rapport in dit format:

```
Sessiestart-briefing
====================
Vault: <eigenaar>
Actieve projecten: <lijst>
Memory: N entries geladen
Wiki: A actief / C concept / S stabiel / X archief
Recente sessies (laatste 5): <bullets>
Wiki-updates (7d): N artikelen
Inbox: N items <(suggestie indien >0)>
Stale: N artikelen >60d <(suggestie indien >5)>
Graphify: <up-to-date | needs rebuild>
Research (7d): N bestanden
```

## Stap 11: Vraag aan gebruiker
Sluit af met: "Wat staat er op de agenda voor deze sessie?"

## Regels
- Alle commando's read-only. Geen schrijfacties, geen mutaties.
- Snel: streef naar < 2 seconden runtime. Alleen filesystem-checks, geen LLM-calls per file.
- Taal: volgt de prompt. Default Nederlands.
- Geen em dashes, geen emoji.
