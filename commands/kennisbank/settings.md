Beheer de KennisBank achtergrond-automatiek: zet toggles aan of uit en leg de keuze vast.

## Vault-root bepalen (VERPLICHT: lees dit eerst)

Bepaal de vault-root EEN keer en gebruik die overal:
`VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`

Gebruik NOOIT een letterlijk pad. De helper staat in `$VAULT/.claude/scripts/_settings.py`.

## Doel
De vier achtergrond-automatieken zijn opt-in/opt-out. Dit commando toont de
huidige staat, laat je toggles wijzigen en schrijft de keuze naar
`$VAULT/kennisbank-settings.json` (bron van waarheid, gelezen door de hooks en de
dagelijkse graphify-gate).

## Stap 1: Lees de huidige staat
Lees per toggle de waarde via de helper. Gebruik de canonieke keys en hun default:

```bash
for key in auto_archive distill_notify embed_index daily_graphify memory_capture memory_recall; do
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

Vraag de gebruiker via `AskUserQuestion` (multiSelect) welke toggles AAN moeten
staan. Vink vooraf exact de toggles aan die nu `1` zijn (uit stap 1), zodat de
gebruiker alleen het verschil hoeft te kiezen.

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
```

## Bevestiging
Toon de nieuwe staat (herhaal stap 1) en benoem expliciet welke automatiek nu
aan en welke uit staat. Vermeld dat hook-toggles pas effect hebben vanaf de
volgende sessie (de hooks lezen de store bij hun volgende run).

## Regels
- Schrijf NOOIT direct JSON; gebruik altijd `_settings.py set`, zodat key-namen en formaat consistent blijven.
- Taal: volgt de prompt. Geen em dashes.
