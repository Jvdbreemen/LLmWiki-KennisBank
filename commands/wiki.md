Compileer recente raw sessie-logs tot wiki-artikelen in $VAULT/. Optioneel onderwerp: $ARGUMENTS

## Vault-root bepalen (VERPLICHT — lees dit eerst)

Bepaal de vault-root ÉÉN keer aan het begin van dit command en gebruik die overal:
`VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`

Gebruik `$VAULT` voor ELK pad hieronder. Gebruik NOOIT een letterlijk `~/KennisBank`- of `C:\...\KennisBank`-pad: dat negeert de `KENNISBANK_VAULT`-env-var en schrijft naar de verkeerde vault (de oorzaak van een eerdere skeleton-misser).


## Doel
Patroonherkenning over sessies heen — destilleer herbruikbare kennis als wiki-artikelen met backlinks. Dit is compilatie, geen samenvatting.

## Stappen

1. Scan raw logs in $VAULT/01-raw/sessies/
   - Default: logs van de laatste 7 dagen
   - Als $ARGUMENTS is opgegeven: alleen logs die dat onderwerp raken (grep op inhoud of filename)

2. Identificeer wiki-kandidaten:
   - Expliciete markers "wiki-kandidaat: [onderwerp]" in de logs
   - Onderwerpen die in minimaal 2 sessies terugkomen
   - Technische oplossingen, workflows, configs die herbruikbaar zijn
   - Begrippen, methoden of tools die nog geen eigen wiki-artikel hebben

3. Check bestaande wiki in $VAULT/02-wiki/
   - Bestaat er al een artikel? Update het. Zo nee: schrijf nieuw artikel via template.

3.5. Bestaand artikel herschrijven
   - Voer per kandidaat-onderwerp uit:
     ```
     python3 $VAULT/.claude/scripts/find-similar.py "<onderwerp-titel>"
     ```
     (of `scripts/find-similar.py` als je al in de repo-root werkt)
   - Parseer de JSON-uitvoer `{path, score, above_threshold}`.

   **Als `above_threshold` true is (match gevonden):**
   - Lees het bestaande artikel op `path`.
   - Stel de verbeterde volledige artikeltekst op: herschrijf/breid de body en kernpunten uit.
     - **Frontmatter:** kopieer het frontmatter-blok LETTERLIJK (knip-plak, niet overtypen)
       uit het gelezen bestand. Behoud `type`, `created`, `tags`, `status` ongewijzigd.
       Wijzig uitsluitend `updated` naar de huidige datum.
     - **Backlinks** (in de body): behoud alle bestaande backlinks ongewijzigd.
   - Schrijf de volledige nieuwe inhoud naar een tijdelijk bestand via het file-write tool:
     ```
     /tmp/wiki-rewrite-<slug>.md
     ```
     Gebruik daarna `safe-edit.py` met dat pad als invoer:
     ```
     python3 $VAULT/.claude/scripts/safe-edit.py <path> --new /tmp/wiki-rewrite-<slug>.md --message "wiki-rewrite: <onderwerp>"
     ```
     > **GEEN `echo "..." | ...` gebruiken.** De body bevat aanhalingstekens, backticks en
     > `$`/`\` die de shell corrumpeert. Schrijf altijd eerst naar een temp-bestand.
   - Als `safe-edit.py` afsluit met code 2 (action `needs-confirm`, grote wijziging):
     - Toon de afgedrukte diff aan de gebruiker.
     - Vraag expliciete bevestiging voordat je opnieuw uitvoert met `--confirm`.
     - Overschrijf **nooit** stil met `--force`.
   - Noteer het resultaat als **herschreven** (pad + score) voor de rapportage.

   **Als `above_threshold` false is (geen match):**
   > **Let op:** een leeg resultaat kan ook betekenen dat de embed-index nog niet gebouwd is. Herstel met `python3 $VAULT/.claude/scripts/build-embed-index.py` en probeer opnieuw.
   - Val door naar stap 4 (nieuw artikel aanmaken via template).

4. Per wiki-artikel:
   - YAML frontmatter: type: wiki, tags, status, created, updated
   - Backlinks naar bron-logs en gerelateerde artikelen
   - Kernpunten met toelichting, geen essay
   - Bronvermelding naar raw-logs onderaan

5. Rapporteer per artikel één van de drie uitkomsten:
   - **herschreven** — bestaand artikel bijgewerkt via safe-edit; vermeld pad en similarity-score
   - **nieuw** — nieuw artikel aangemaakt via template
   - **overgeslagen** — kandidaat voldeed niet aan criteria; vermeld reden

## Regels
- Compilatie, niet kopieer-en-plak
- Bij twijfel: status: concept
- Taal: volgt de bron
- Dagelijkse graphify-batch respecteert de `daily_graphify`-toggle in `kennisbank-settings.json`: staat die uit, werk alleen `$VAULT/graphify-out/.needs-rebuild` bij en draai geen automatische `/graphify --update`. Lezen: `python3 -c "import sys; sys.path.insert(0,'$VAULT/.claude/scripts'); import _settings; print(_settings.get('daily_graphify', True))"`.

## Bronnen: `promote_candidate`-memories

De autonome capture-sweep (`memory-sweep.py`) markeert memories in `09-memory/` met `promote_candidate: true` als ze deel uitmaken van een cluster van minstens twee verwante current-memories (cosine > 0.80). Deze memories zijn bij compilatie van wiki-artikelen bij uitstek bruikbare bronnen: ze vertegenwoordigen onderwerpen die in meerdere sessies terugkomen. Geef ze voorrang als er keuze is tussen vergelijkbare bronnen.
