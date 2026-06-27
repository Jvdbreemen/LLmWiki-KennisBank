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

4. Per wiki-artikel:
   - YAML frontmatter: type: wiki, tags, status, created, updated
   - Backlinks naar bron-logs en gerelateerde artikelen
   - Kernpunten met toelichting, geen essay
   - Bronvermelding naar raw-logs onderaan

5. Rapporteer: welke artikelen nieuw/bijgewerkt, welke overgeslagen en waarom

## Regels
- Compilatie, niet kopieer-en-plak
- Bij twijfel: status: concept
- Taal: volgt de bron
- Dagelijkse graphify-batch respecteert de `daily_graphify`-toggle in `kennisbank-settings.json`: staat die uit, werk alleen `$VAULT/graphify-out/.needs-rebuild` bij en draai geen automatische `/graphify --update`. Lezen: `python3 -c "import sys; sys.path.insert(0,'$VAULT/.claude/scripts'); import _settings; print(_settings.get('daily_graphify', True))"`.

## Bronnen: `promote_candidate`-memories

De autonome capture-sweep (`memory-sweep.py`) markeert memories in `09-memory/` met `promote_candidate: true` als ze deel uitmaken van een cluster van minstens twee verwante current-memories (cosine > 0.80). Deze memories zijn bij compilatie van wiki-artikelen bij uitstek bruikbare bronnen: ze vertegenwoordigen onderwerpen die in meerdere sessies terugkomen. Geef ze voorrang als er keuze is tussen vergelijkbare bronnen.
