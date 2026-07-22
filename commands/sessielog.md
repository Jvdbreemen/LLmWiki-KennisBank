Schrijf een sessie-log voor de huidige agent-sessie naar de KennisBank vault,
en compileer daarna direct de wiki-kandidaten uit deze sessie.

## Uitvoerstijl (VERPLICHT — bepaalt hoeveel je toont)

Werk STIL. Dit command draait veel mechanische stappen; die horen niet als
lopend commentaar in de chat.

- Geen per-stap narratie. Zeg niet "Nu doe ik X" tussen elke tool. Voer de
  stappen uit zonder toelichting ertussen.
- Onderdruk ruis van shell-commando's: leid verbose stdout door
  `2>&1 | tail -n 3`. Lees de volledige output alleen bij een niet-nul exit code.
- Draai de graphify daily-batch (Stap 2 item 5, `/graphify --update`) in een
  subagent als je client dat ondersteunt (bv. de Agent-tool in Claude Code):
  al het interne gepruttel (detect, cache, merge, cluster, cost) blijft dan uit
  het hoofd-transcript, dat alleen de eindsamenvatting terugkrijgt. Ondersteunt
  je client geen subagents, leid de graphify-output dan door `| tail` en toon
  alleen de eindsamenvatting. De extractie-subagents die graphify zelf spawnt
  tellen nog steeds mee voor de cost.json-patch — vraag die tokens op uit het
  subagent-resultaat.
- Breek de stilte alleen bij een fout: meld die meteen met de foutregel, en
  stop niet stil door.
- De stilte geldt voor de TUSSENSTAPPEN. De Bevestiging onderaan blijft
  volledig/verbose zoals gespecificeerd — kort de stappen in, niet de conclusie.

## Vault-root bepalen (VERPLICHT — lees dit eerst)

Bepaal de vault-root ÉÉN keer aan het begin van dit command en gebruik die overal:
`VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`

Gebruik `$VAULT` voor ELK pad hieronder. Gebruik NOOIT een letterlijk `~/KennisBank`- of `C:\...\KennisBank`-pad: dat negeert de `KENNISBANK_VAULT`-env-var en schrijft naar de verkeerde vault (de oorzaak van een eerdere skeleton-misser).


## Stap 1: Sessie-log schrijven

### Locatie en naamconventie
- Map: `$VAULT/01-raw/sessies/`
- Bestandsnaam: `raw-sessie-YYYY-MM-DD-[onderwerp-slug].md`
- Onderwerp-slug: korte kebab-case van het hoofdonderwerp van de sessie. Als er meerdere onderwerpen waren, kies het dominante
- Datum: vandaag in ISO-formaat (lees uit systeem, niet verzinnen)

### Template
Gebruik `$VAULT/04-templates/tpl-sessie-log.md` als basis.

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
Bewaar het absolute pad van het geschreven bestand als `SESSION_LOG`. De
mechanische coördinator aan het einde werkt de Karpathy-index en de andere
afgeleide indexen in één run bij.

De mechanische coördinator start ook `sweep-launch.py`. Die launcher is
single-flight, losgekoppeld en fail-open; voer hier geen tweede sweep uit.

---

## Stap 2: Wiki-kandidaten verwerken

1. Identificeer kandidaten uit de sessie-log (regels gemarkeerd "wiki-kandidaat: [onderwerp]", technische oplossingen, herbruikbare workflows)
2. Scan ~/Claude/research/ voor bestanden aangemaakt of gewijzigd vandaag:
   ```bash
   find ~/Claude/research/ -name "*.md" -mtime -1 2>/dev/null
   ```
   Behandel elk gevonden research-bestand als wiki-kandidaat.
3. Check bestaande wiki in $VAULT/02-wiki/: update bestaand artikel of schrijf nieuw via template
4. Per wiki-artikel: YAML frontmatter compleet, backlinks via [[...]], kernpunten met toelichting
5. Graph bijwerken — DAGELIJKSE BATCH (kostenbesparing: LLM-extractie kost tokens per bestand). ALTIJD eerst: voeg de gewijzigde/nieuwe wiki-paden toe aan `$VAULT/graphify-out/.needs-rebuild` (goedkoop, geen LLM).

   Lees daarna de `daily_graphify`-toggle:
   ```bash
   DG=$(python3 -c "import sys; sys.path.insert(0,'$VAULT/.claude/scripts'); import _settings; print('1' if _settings.get('daily_graphify', True) else '0')")
   ```
   - `daily_graphify` UIT (`DG=0`): sla de automatische `--update` deze sessie over. `.needs-rebuild` is al bijgewerkt (gratis). Meld "auto-graph uit via settings; draai handmatig `/graphify $VAULT/02-wiki --update`". Sla ook item 6 (auto-crosslinks) over en ga naar item 7.
   - `daily_graphify` AAN (`DG=1`): volg de bestaande dag-gate hieronder.

   DAN de dag-gate op de mtime van `$VAULT/graphify-out/graph.json`:
   - graph.json OUDER dan ~20 uur (eerste sessie van de dag) EN .needs-rebuild niet leeg: roep `/graphify $VAULT/02-wiki --update` aan (scope is bewust `02-wiki`: alleen gedestilleerde kennis in de graaf, geen tooling/scripts). Graphify's manifest batcht ALLE sinds de vorige run gewijzigde bestanden in een keer (cache slaat ongewijzigde over; subagents doen alleen de nieuwe), herclustert. Leeg daarna `.needs-rebuild`. PATCH DAN de tokenkost in cost.json (graphify logt een subagent-extractie op 0; graphify blijft ongemodificeerd, we corrigeren het hier in sessielog): tel de `usage.subagent_tokens` op van ALLE extractie-subagents die je tijdens deze `--update` dispatchte (de Agent-API geeft een gecombineerd getal, geen in/out-splitsing) en schrijf dat naar de laatste run. Vervang `<SUBAGENT_TOKENS>` door die som:
     ```bash
     python3 - "<SUBAGENT_TOKENS>" <<'PY'
     import json, os, sys
     from pathlib import Path
     sub = int(sys.argv[1])
     vault = os.environ.get('KENNISBANK_VAULT') or str(Path.home() / 'KennisBank')
     p = Path(vault) / 'graphify-out' / 'cost.json'
     c = json.loads(p.read_text(encoding='utf-8'))
     r = c['runs'][-1]                              # de zojuist door graphify toegevoegde run
     r['backend'] = 'claude-subagent'
     r['subagent_tokens'] = sub
     r['total_tokens'] = r.get('input_tokens', 0) + r.get('output_tokens', 0) + sub
     c['total_subagent_tokens'] = sum(x.get('subagent_tokens', 0) for x in c['runs'])
     c['total_tokens'] = sum(x.get('input_tokens', 0) + x.get('output_tokens', 0) + x.get('subagent_tokens', 0) for x in c['runs'])
     p.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding='utf-8')
     print(f'cost.json gepatcht: {sub} subagent-tokens; totaal {c["total_tokens"]}')
     PY
     ```
     Nooit een subagent-run op 0 laten staan. Ga dan naar item 6.
   - graph.json JONGER dan ~20u: SLA `--update` deze sessie over en meld "graph ~N bestanden achter (.needs-rebuild), ververst op de eerste sessie na 20u". Zo betaalt alleen de eerste sessie per dag de extractiekost.
   - graphify niet geinstalleerd (`graphify-out/.graphify_python` ontbreekt): alleen `.needs-rebuild` bijwerken en melden dat de graph stale is.
6. Auto-crosslinks: ALLEEN als item 5 deze sessie `--update` draaide (anders bestaat de node van het nieuwe artikel nog niet in de graph): python3 $VAULT/.claude/scripts/auto-crosslink.py [pad-naar-artikel]. Werd `--update` overgeslagen, sla crosslinks ook over: het nieuwe artikel krijgt zijn graph-backlinks bij de eerstvolgende dagrun; de handmatige [[...]]-links in het artikel werken intussen.
7. Rapporteer wat nieuw, bijgewerkt of overgeslagen is (incl. of de graph deze sessie is ververst of pas bij de volgende dagrun, en de tokenkost als `--update` draaide)

---

## Stap 3: Graphify (afgehandeld in Stap 2, dagelijkse batch)

De graph-update zit in Stap 2 item 5 als DAGELIJKSE BATCH om tokens te sparen: elke sessie schrijft naar `.needs-rebuild` (gratis), maar `/graphify --update` draait alleen op de eerste sessie waarop `graph.json` ouder is dan ~20u. Graphify's eigen manifest bepaalt welke bestanden sinds de vorige run wijzigden en batcht ze in een keer; de cache zorgt dat elk bestand maar een keer wordt geextraheerd. Reden voor dagelijks i.p.v. per-sessie: de LLM-kost is per-bestand-extractie, dus meerdere sessies per dag samenvoegen scheelt de subagent-spawn- en clusteroverhead en her-extractie van bestanden die meerdere keren per dag wijzigen. Wil je de graph tussendoor forceren: draai handmatig `/graphify $VAULT/02-wiki --update`. `.needs-rebuild` is het "er staat werk klaar"-signaal plus fallback wanneer graphify niet beschikbaar is.

---

## Stap 4: Semantische deduplicatie (tiling)

Check of het embedding-model beschikbaar is (default `qwen3-embedding:8b`, meertalig; `nomic-embed-text` is de lichtere Engels-only fallback):
```bash
ollama list 2>/dev/null | grep -E 'qwen3-embedding|nomic-embed-text'
```
Als niet beschikbaar: sla over, rapporteer installatie-instructie (`ollama pull qwen3-embedding:8b`).
Als beschikbaar: python3 $VAULT/.claude/scripts/semantic-tiling.py [pad-naar-artikel]
- >= 0.85: mogelijke duplicaat (error)  ← drempels voor default `qwen3-embedding:8b`
- 0.62–0.84: verwant (review)
(nomic-embed-text spreidt hoger: gebruik dan 0.90 / 0.80, zie CONFIGURATION.md)

---

## Stap 5: Key learnings bijwerken (optioneel)

Lees het learnings-pad deterministisch uit `$VAULT/CLAUDE.md` — grep de EERSTE
ongecommente `LEARNINGS_FILE=`-regel (een regel die met `#` begint telt als
uitgeschakeld), en expandeer een leidende `~` naar `$HOME`:

```bash
LEARN=$(grep -E '^[[:space:]]*LEARNINGS_FILE=' "$VAULT/CLAUDE.md" | head -1 | sed -E 's/^[[:space:]]*LEARNINGS_FILE=//' | tr -d '"' | sed "s#^~#$HOME#")
```

- Leeg (geen ongecommente regel): sla deze stap over en meld "geen learnings-bestand geconfigureerd".
- Anders: dit is het learnings-bestand. Maak het aan als het nog niet bestaat (`mkdir -p "$(dirname "$LEARN")"` + touch). Scan de sessie-log en append één sessie-blok `## YYYY-MM-DD sessie (onderwerp)` met de subsecties die van toepassing zijn:
  - `### Do-Not-Repeat`: fouten, crashes, mislukte aanpakken
  - `### Key Learnings`: technische patronen, herbruikbare werkwijzen
  - `### Decision Log`: significante architectuur- of toolingkeuzes

Sla alleen over als er niets configureerds gevonden is — niet als het bestand nog niet bestaat (maak het dan aan). Het learnings-bestand vult de automatische `09-memory/`-laag aan met een mens-gecureerd record.

---

## Stap 6: Mechanische sessielog-coördinator (VERPLICHT)

Voer na alle semantische schrijfwerk precies één helper uit. Gebruik `python3`
op macOS/Linux of `py -3` op Windows:

```bash
python3 "$VAULT/.claude/scripts/kb-session-log.py" --session-log "$SESSION_LOG"
```

De helper valideert dat het sessielog onder
`$VAULT/01-raw/sessies/` staat, draait de Karpathy-, embedding-, kennis- en
activiteitsindexen plus de sweep-launcher parallel, en voert geheugen- en
destillatiemeldingen pas daarna uit. Hij is fail-open en geeft één samengevoegd
resultaat terug. Voer de losse child-scripts niet daarnaast uit.

---

## Bevestiging
- Pad naar het geschreven sessie-log
- Welke wiki-artikelen nieuw of bijgewerkt zijn
- Tiling-resultaten (of "overgeslagen — installeer qwen3-embedding:8b")
- Welke learnings-entries toegevoegd zijn (of "overgeslagen — geen learnings-bestand geconfigureerd")
- Het ene resultaat van `kb-session-log.py` (alleen wijzigingen of acties)
- Als Decision Log entries aanwezig: overweeg of deze beslissingen een ADR (Architecture Decision Record) verdienen in het betreffende project. Als je een /adr workflow gebruikt: draai die nu.
