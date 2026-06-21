Schrijf een sessie-log voor de huidige Claude-sessie naar de KennisBank vault, en compileer daarna direct de wiki-kandidaten uit deze sessie.

## Stap 1: Sessie-log schrijven

### Locatie en naamconventie
- Map: `~/KennisBank/01-raw/sessies/`
- Bestandsnaam: `raw-sessie-YYYY-MM-DD-[onderwerp-slug].md`
- Onderwerp-slug: korte kebab-case van het hoofdonderwerp van de sessie. Als er meerdere onderwerpen waren, kies het dominante
- Datum: vandaag in ISO-formaat (lees uit systeem, niet verzinnen)

### Template
Gebruik `~/KennisBank/04-templates/tpl-sessie-log.md` als basis.

- **Doel**: wat was de vraag of opdracht aan het begin van de sessie?
- **Samenvatting**: 3-5 zinnen wat er is gedaan. Feitelijk, geen meta-commentaar
- **Output**: lijst van aangemaakte of gewijzigde bestanden, inclusief absolute paden. Als er taken zijn gemaakt of bijgewerkt, noem de task-ids
- **Nieuwe kennis**: wat is er geleerd dat breder toepasbaar is? Expliciete kandidaten voor 02-wiki/ markeren met "wiki-kandidaat: [onderwerp]"
- **Vervolgacties**: openstaande items als checkbox-lijst
- **AI-verantwoording**: welke tools/skills gebruikt, wat was mijn input

### Save-patroon: conversatie → kennis
Schrijf de "Nieuwe kennis"-sectie in declaratieve tegenwoordige tijd. Niet "we hebben ontdekt dat X" maar gewoon de kennis zelf:
- FOUT: "We hebben ontdekt dat Sveltia CMS beter werkt dan Decap CMS voor static sites"
- GOED: "Sveltia CMS is de actief onderhouden opvolger van Decap CMS. Het biedt directe GitHub-integratie zonder serverinfrastructuur."

Elke kennisregel moet leesbaar zijn door een toekomstige sessie zonder context van dit gesprek.

### Regels
- Als er vandaag al een sessie-log bestaat met hetzelfde onderwerp: append een nieuwe sectie ## Vervolg [tijdstip]
- Taal: volgt de prompt
- Geen em dashes

### Karpathy-index updaten
Na het schrijven van het sessie-log:
```bash
python3 ~/KennisBank/.claude/scripts/build-karpathy-index.py
```
Dit voegt de nieuwe sessie toe aan `~/KennisBank/02-wiki/log.md` (het chronologische index-bestand in `## [YYYY-MM-DD] OPERATION | Title` formaat).

---

## Stap 2: Wiki-kandidaten verwerken

1. Identificeer kandidaten uit de sessie-log (regels gemarkeerd "wiki-kandidaat: [onderwerp]", technische oplossingen, herbruikbare workflows)
2. Scan ~/Claude/research/ voor bestanden aangemaakt of gewijzigd vandaag:
   ```bash
   find ~/Claude/research/ -name "*.md" -mtime -1 2>/dev/null
   ```
   Behandel elk gevonden research-bestand als wiki-kandidaat.
3. Check bestaande wiki in ~/KennisBank/02-wiki/: update bestaand artikel of schrijf nieuw via template
4. Per wiki-artikel: YAML frontmatter compleet, backlinks via [[...]], kernpunten met toelichting
5. Graph bijwerken — DAGELIJKSE BATCH (kostenbesparing: LLM-extractie kost tokens per bestand). ALTIJD eerst: voeg de gewijzigde/nieuwe wiki-paden toe aan `~/KennisBank/graphify-out/.needs-rebuild` (goedkoop, geen LLM). DAN de dag-gate op de mtime van `~/KennisBank/graphify-out/graph.json`:
   - graph.json OUDER dan ~20 uur (eerste sessie van de dag) EN .needs-rebuild niet leeg: roep `/graphify ~/KennisBank --update` aan. Graphify's manifest batcht ALLE sinds de vorige run gewijzigde bestanden in een keer (cache slaat ongewijzigde over; subagents doen alleen de nieuwe), herclustert, en legt de ECHTE subagent-tokenkost vast in `graphify-out/cost.json` (graphify Step 9 leest `.graphify_run_cost.json`; nooit 0 voor een subagent-run). Leeg daarna `.needs-rebuild` en ga naar item 6.
   - graph.json JONGER dan ~20u: SLA `--update` deze sessie over en meld "graph ~N bestanden achter (.needs-rebuild), ververst op de eerste sessie na 20u". Zo betaalt alleen de eerste sessie per dag de extractiekost.
   - graphify niet geinstalleerd (`graphify-out/.graphify_python` ontbreekt): alleen `.needs-rebuild` bijwerken en melden dat de graph stale is.
6. Auto-crosslinks: ALLEEN als item 5 deze sessie `--update` draaide (anders bestaat de node van het nieuwe artikel nog niet in de graph): python3 ~/KennisBank/.claude/scripts/auto-crosslink.py [pad-naar-artikel]. Werd `--update` overgeslagen, sla crosslinks ook over: het nieuwe artikel krijgt zijn graph-backlinks bij de eerstvolgende dagrun; de handmatige [[...]]-links in het artikel werken intussen.
7. Rapporteer wat nieuw, bijgewerkt of overgeslagen is (incl. of de graph deze sessie is ververst of pas bij de volgende dagrun, en de tokenkost als `--update` draaide)

---

## Stap 3: Graphify (afgehandeld in Stap 2, dagelijkse batch)

De graph-update zit in Stap 2 item 5 als DAGELIJKSE BATCH om tokens te sparen: elke sessie schrijft naar `.needs-rebuild` (gratis), maar `/graphify --update` draait alleen op de eerste sessie waarop `graph.json` ouder is dan ~20u. Graphify's eigen manifest bepaalt welke bestanden sinds de vorige run wijzigden en batcht ze in een keer; de cache zorgt dat elk bestand maar een keer wordt geextraheerd. Reden voor dagelijks i.p.v. per-sessie: de LLM-kost is per-bestand-extractie, dus meerdere sessies per dag samenvoegen scheelt de subagent-spawn- en clusteroverhead en her-extractie van bestanden die meerdere keren per dag wijzigen. Wil je de graph tussendoor forceren: draai handmatig `/graphify ~/KennisBank --update`. `.needs-rebuild` is het "er staat werk klaar"-signaal plus fallback wanneer graphify niet beschikbaar is.

---

## Stap 4: Semantische deduplicatie (tiling)

Check of het embedding-model beschikbaar is (default `qwen3-embedding:8b`, meertalig; `nomic-embed-text` is de lichtere Engels-only fallback):
```bash
ollama list 2>/dev/null | grep -E 'qwen3-embedding|nomic-embed-text'
```
Als niet beschikbaar: sla over, rapporteer installatie-instructie (`ollama pull qwen3-embedding:8b`).
Als beschikbaar: python3 ~/KennisBank/.claude/scripts/semantic-tiling.py [pad-naar-artikel]
- >= 0.85: mogelijke duplicaat (error)  ← drempels voor default `qwen3-embedding:8b`
- 0.62–0.84: verwant (review)
(nomic-embed-text spreidt hoger: gebruik dan 0.90 / 0.80, zie CONFIGURATION.md)

---

## Stap 5: Key learnings bijwerken (optioneel)

Als je een centraal "key learnings"-bestand bijhoudt, scan de sessie-log op:
- Do-Not-Repeat: fouten, crashes, mislukte aanpakken
- Key Learnings: technische patronen, herbruikbare werkwijzen
- Decision Log: significante architectuur- of toolingkeuzes

Configureer het pad in ~/KennisBank/CLAUDE.md (zie `LEARNINGS_FILE`). Als het pad niet geconfigureerd is: sla over.

---

## Bevestiging
- Pad naar het geschreven sessie-log
- Welke wiki-artikelen nieuw of bijgewerkt zijn
- Tiling-resultaten (of "overgeslagen — installeer qwen3-embedding:8b")
- Welke learnings-entries toegevoegd zijn (of "overgeslagen — geen learnings-bestand geconfigureerd")
- Als Decision Log entries aanwezig: overweeg of deze beslissingen een ADR (Architecture Decision Record) verdienen in het betreffende project. Als je een /adr workflow gebruikt: draai die nu.
