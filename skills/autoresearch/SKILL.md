---
name: autoresearch
description: >
  Autonomous iterative research loop for journalism and general research.
  Given a topic, the skill runs multi-round web searches, synthesizes findings,
  and saves one structured document in ~/Claude/research/. Based on Karpathy's
  autoresearch pattern and adapted for coding agents. Triggers: /autoresearch
  [topic], "research [topic]", "deep dive [topic]", "onderzoek [topic]"
allowed-tools: Read Write Bash WebFetch WebSearch Glob Grep
---

# autoresearch: Autonome Research-Loop

Je bent een research-agent. Je ontvangt een topic, draait iteratieve web searches, synthetiseert bevindingen en slaat het resultaat op als één gestructureerd markdown-bestand.

---

## Stap 0: Lazy Hierarchy Check

Controleer drie lagen voor je begint te zoeken. Stop zodra je genoeg context hebt om de gaps te formuleren.

**Laag 1 — Memory index** (altijd uitvoeren):
```bash
MEMORY=$(ls ~/.claude/projects/*/memory/MEMORY.md 2>/dev/null | head -1)
[ -n "$MEMORY" ] && cat "$MEMORY"
```
Lees relevante memory-bestanden als de index er op wijst.

**Laag 2 — KennisBank wiki** (altijd uitvoeren):
```bash
cat ~/KennisBank/02-wiki/index.md 2>/dev/null | head -100
grep -ril "[kernwoord]" ~/KennisBank/02-wiki/ 2>/dev/null | head -10
```
Lees gevonden wiki-artikelen (max 3) die direct relevant zijn.

**Laag 3 — Eerder research-bestand** (optioneel):
```bash
ls ~/Claude/research/ 2>/dev/null | grep -i "[topic-slug]"
```

Noteer wat al bekend is. In Round 1 zoek je naar wat er NIET instaat.

---

## Topic-selectie

**A. Expliciet topic:** /autoresearch [topic] → gebruik het opgegeven topic direct.
**B. Geen topic opgegeven:** Vraag: "Wat moet ik onderzoeken?"

---

## Research-loop

```
Round 1 — Breed
1. Decomponeer het topic in 3–5 zoekhoeken
2. Per hoek: 2–3 WebSearch queries
3. Per top-3 resultaat: WebFetch de pagina
4. Extraheer per bron: kernbewering, entiteiten, open vragen

Round 2 — Gaps
5. Identificeer wat ontbreekt of tegenstrijdig is
6. Gerichte searches per gap (max 5 queries)
7. Fetch top-resultaten per gap

Round 3 — Synthesecheck (alleen als nodig)
8. Als grote lacunes blijven: één extra gerichte pass
9. Anders: ga naar output

Maximaal 3 rounds.
```

---

## Output aanmaken

```bash
mkdir -p ~/Claude/research
```

Outputpad: ~/Claude/research/YYYY-MM-DD-[slug].md

### Frontmatter
```yaml
---
topic: [topic]
date: YYYY-MM-DD
angles:
  - [zoekhoek 1]
rounds: N
sources_found: N
confidence: hoog | matig | laag
---
```

Confidence: hoog = meerdere onafhankelijke bronnen bevestigen, matig = beperkt of deels tegenstrijdig, laag = weinig bronnen of eenzijdig.

### Documentstructuur
```markdown
# Research: [Topic]

## Bevindingen
[Genummerd. Elke betwistbare bewering: bronvermelding verplicht.]

## Entiteiten & actoren
[Naam — rol/betekenis]

## Bronnen
[Genummerd. Titel — auteur/site — datum — URL — betrouwbaarheid 1–5]

## Kennisgaten
["Niet gevonden: X" of "Tegenstrijdig: bron A zegt X, bron B zegt Y"]

## Reeds bekend
[Alleen invullen als lazy hierarchy iets relevants opleverde]

## Volgende stappen
[Concrete vervolgacties]
```

---

## Rapport aan gebruiker

```
Research afgerond: [Topic]
Rounds: N | Bronnen: N | Confidence: [hoog/matig/laag]
Bestand: ~/Claude/research/YYYY-MM-DD-[slug].md

Kernbevindingen:
- [bevinding 1]
- [bevinding 2]

Kennisgaten: N
Naar KennisBank: voer /sessielog uit om bevindingen als wiki-kandidaat te verwerken.
```

---

## Constraints
- Max 3 rounds, max 15 bronnen
- Elke betwistbare bewering: bronvermelding verplicht
- Geen uitvinding: als iets niet gevonden is, staat het in Kennisgaten
- Taal volgt het topic
- Als web tools niet beschikbaar: zeg dit, confidence = laag
