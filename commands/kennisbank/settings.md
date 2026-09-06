Beheer de KennisBank achtergrond-automatiek: zet toggles aan of uit en leg de keuze vast.

## Vault-root bepalen (VERPLICHT: lees dit eerst)

Bepaal de vault-root EEN keer en gebruik die overal:
`VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`

Gebruik NOOIT een letterlijk pad. De helper staat in `$VAULT/.claude/scripts/_settings.py`.

## Doel
De achtergrond-automatieken zijn opt-in/opt-out. Dit commando toont de
huidige staat, laat je toggles wijzigen en schrijft de keuze naar
`$VAULT/kennisbank-settings.json` (bron van waarheid, gelezen door de hooks en de
dagelijkse graphify-gate).

## Stap 1: Lees de huidige staat
Lees per toggle de waarde via de helper. Gebruik de canonieke keys en hun default:

```bash
for key in auto_archive distill_notify embed_index daily_graphify memory_capture memory_recall experience_capture experience_projection experience_explicit_recall source_explicit_recall usage_telemetry activity_llm_fallback checkpoints orientation graph_retrieval; do
  val=$(python3 "$VAULT/.claude/scripts/_settings.py" get "$key")
  echo "$key=$val"
done
```

`1` = aan, `0` = uit. Bestaat het bestand nog niet, dan geeft de helper de
defaults (auto_archive uit, de rest aan).

## Stap 2: Toon de toggles en vraag de gewenste staat
Toon een nette tabel met per toggle de naam, huidige staat (aan/uit) en wat hij
doet:

- **auto_archive** - archiveer elk transcript bij sessie-einde naar `01-raw/transcripts/` (voer hierna `/destilleer` uit). Uit = geen archief; gebruik `/sessielog` handmatig.
- **distill_notify** - meld bij sessiestart hoeveel transcripts op `/destilleer` wachten.
- **embed_index** - ververs de wiki-embeddingcache bij sessiestart (voor prompt-time retrieval). Uit = retrieval draait op een oudere cache.
- **daily_graphify** - draai 1x/dag automatisch `/graphify --update` (kost-gated op 20u). Uit = alleen `.needs-rebuild` bijhouden; draai de graph handmatig.
- **memory_capture** - extractie+judge van memories naar `09-memory/` + onderhoud. Uit = geen memory-opslag.
- **memory_recall** - injecteer memories in de context via hook + lokale MCP. Uit = geen memory-retrieval bij sessiestart.
- **experience_capture** (default UIT) - verzamel typed events en outcomes in het append-only experience-ledger. Dit bouwt geen zoekindex en activeert geen recall.
- **experience_projection** (default UIT) - bouw de afgeleide, gevalideerde experience-projectie. Dit activeert de publieke recall-tool niet.
- **experience_explicit_recall** (default UIT) - sta alleen expliciet gevraagde recall van maximaal drie gevalideerde lessen toe. Automatische advisories blijven verboden.
- **source_explicit_recall** (default UIT) - sta expliciete FTS-bronsearch en exacte SourceRef-hydration toe. Automatische fallback of promptinjectie blijft verboden.
- **usage_telemetry** - registreer welke geinjecteerde kennis daadwerkelijk gebruikt wordt (kb-usage.db; voedt ranking-boost en stale-warm-skip). Uit = geen gebruiksmeting.
- **activity_llm_fallback** (default UIT) - laat een lokale LLM een datum/periode duiden die de deterministische lagen niet herkennen (laag 3 van de temporele parser). Aan = tragere maar bredere taaldekking; uit = alleen de locale-tabellen en dateparser.
- **checkpoints** (default UIT) - schrijf bij context-compaction (Claude PreCompact) automatisch een werkstand-stub en meld die bij de volgende sessiestart. Uit = alleen handmatige checkpoints via `/checkpoint`.
- **orientation** (default UIT) - toon bij sessiestart een compacte vault-orientatie: documentcounts, recent gewijzigde artikelen, veelgebruikte kennis en open backlog-taken. Uit = alleen on-demand via `/sessiestart`.
- **graph_retrieval** (default AAN sinds de A/B-poort van 2026-07-29, TASK-87) - haal de (buur)-entry in de hook-injectie uit de gewogen graafindex (kb-graph.db) in plaats van de legacy wikilink-scan. Aanzetten alleen na een kb-eval A/B op sets van >=100 vragen (bewijsregel TASK-86).

Vraag de gewenste staat tekstueel uit (NIET via `AskUserQuestion`: die tool
staat maximaal 4 opties per vraag toe, en er zijn 11 toggles; een enkele
multiSelect-vraag met 10 opties faalt met een `InputValidationError`).

Toon de 15 toggles genummerd met hun huidige staat (aan/uit uit stap 1) en vraag
de gebruiker welke moeten wijzigen, bijvoorbeeld: "Noem de toggles die je wilt
omzetten (bv. `auto_archive uit, memory_recall aan`), of antwoord `niets` om de
huidige staat te behouden." Neem voor elke niet-genoemde toggle de huidige
waarde ongewijzigd over.

Wil je toch de klik-UI van `AskUserQuestion` gebruiken, splits dan over
meerdere vragen van maximaal 4 opties elk.

## Stap 3: Schrijf de keuze terug
Voor ELKE canonieke toggle: aangevinkt -> `true`, niet-aangevinkt -> `false`.
Schrijf via de helper (maakt het bestand aan als het nog niet bestaat):

```bash
python3 "$VAULT/.claude/scripts/_settings.py" set auto_archive   <true|false>
python3 "$VAULT/.claude/scripts/_settings.py" set distill_notify <true|false>
python3 "$VAULT/.claude/scripts/_settings.py" set embed_index    <true|false>
python3 "$VAULT/.claude/scripts/_settings.py" set daily_graphify <true|false>
python3 "$VAULT/.claude/scripts/_settings.py" set memory_capture  <true|false>
python3 "$VAULT/.claude/scripts/_settings.py" set memory_recall   <true|false>
python3 "$VAULT/.claude/scripts/_settings.py" set experience_capture <true|false>
python3 "$VAULT/.claude/scripts/_settings.py" set experience_projection <true|false>
python3 "$VAULT/.claude/scripts/_settings.py" set experience_explicit_recall <true|false>
python3 "$VAULT/.claude/scripts/_settings.py" set source_explicit_recall <true|false>
python3 "$VAULT/.claude/scripts/_settings.py" set usage_telemetry <true|false>
python3 "$VAULT/.claude/scripts/_settings.py" set activity_llm_fallback <true|false>
python3 "$VAULT/.claude/scripts/_settings.py" set checkpoints <true|false>
python3 "$VAULT/.claude/scripts/_settings.py" set orientation <true|false>
python3 "$VAULT/.claude/scripts/_settings.py" set graph_retrieval <true|false>
```

## Bevestiging
Toon de nieuwe staat (herhaal stap 1) en benoem expliciet welke automatiek nu
aan en welke uit staat. Vermeld dat hook-toggles pas effect hebben vanaf de
volgende sessie (de hooks lezen de store bij hun volgende run).

## Regels
- Schrijf NOOIT direct JSON; gebruik altijd `_settings.py set`, zodat key-namen en formaat consistent blijven.
- De legacy keys `source_recall` en `experience_recall` verlenen geen nieuwe
  capability. Draai `_settings.py migrate`, lees de waarschuwing en zet elke
  gewenste vervangende capability afzonderlijk aan.
- Taal: volgt de prompt. Geen em dashes.
