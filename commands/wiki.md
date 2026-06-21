Compileer recente raw sessie-logs tot wiki-artikelen in ~/KennisBank/. Optioneel onderwerp: $ARGUMENTS

## Doel
Patroonherkenning over sessies heen — destilleer herbruikbare kennis als wiki-artikelen met backlinks. Dit is compilatie, geen samenvatting.

## Stappen

1. Scan raw logs in ~/KennisBank/01-raw/sessies/
   - Default: logs van de laatste 7 dagen
   - Als $ARGUMENTS is opgegeven: alleen logs die dat onderwerp raken (grep op inhoud of filename)

2. Identificeer wiki-kandidaten:
   - Expliciete markers "wiki-kandidaat: [onderwerp]" in de logs
   - Onderwerpen die in minimaal 2 sessies terugkomen
   - Technische oplossingen, workflows, configs die herbruikbaar zijn
   - Begrippen, methoden of tools die nog geen eigen wiki-artikel hebben

3. Check bestaande wiki in ~/KennisBank/02-wiki/
   - Bestaat er al een artikel? Update het. Zo nee: schrijf nieuw artikel via template.

3.5. Bestaand artikel herschrijven
   - Voer per kandidaat-onderwerp uit:
     ```
     python3 ~/KennisBank/.claude/scripts/find-similar.py "<onderwerp-titel>" --threshold 0.75
     ```
     (of `scripts/find-similar.py` als je al in de repo-root werkt)
   - Parseer de JSON-uitvoer `{path, score, above_threshold}`.

   **Als `above_threshold` true is (match gevonden):**
   - Lees het bestaande artikel op `path`.
   - Stel de verbeterde volledige artikeltekst op: herschrijf/breid de body en kernpunten uit,
     maar **behoud het bestaande frontmatter exact** (`created`, `tags`, `status`) en de
     bestaande backlinks. Pas alleen `updated` aan naar de huidige datum.
   - Pipe de volledige nieuwe inhoud door `safe-edit.py`:
     ```
     echo "<nieuwe-inhoud>" | python3 ~/KennisBank/.claude/scripts/safe-edit.py <path> --new - --message "wiki-rewrite: <onderwerp>"
     ```
   - Als `safe-edit.py` afsluit met code 2 (action `needs-confirm`, grote wijziging):
     - Toon de afgedrukte diff aan de gebruiker.
     - Vraag expliciete bevestiging voordat je opnieuw uitvoert met `--confirm`.
     - Overschrijf **nooit** stil met `--force`.
   - Noteer het resultaat als **herschreven** (pad + score) voor de rapportage.

   **Als `above_threshold` false is (geen match):**
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
