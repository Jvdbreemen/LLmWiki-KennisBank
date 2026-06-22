Los tegenstrijdigheden op tussen wiki-artikelen in $VAULT/ en leg de beslissingen vast in een auditlog. Optioneel onderwerp: $ARGUMENTS

## Vault-root bepalen (VERPLICHT — lees dit eerst)

Bepaal de vault-root ÉÉN keer aan het begin van dit command en gebruik die overal:
`VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`

Gebruik `$VAULT` voor ELK pad hieronder. Gebruik NOOIT een letterlijk `~/KennisBank`- of `C:\...\KennisBank`-pad: dat negeert de `KENNISBANK_VAULT`-env-var en schrijft naar de verkeerde vault.

## Doel
Detecteer semantisch overlappende artikelen die elkaars claims tegenspreken, laat de gebruiker besluiten welke claim survives, pas het verliezende artikel aan en log elke beslissing.

## Stappen

1. Scan de wiki op kandidaat-tegenstrijdige paren:
   ```
   python3 $VAULT/.claude/scripts/conflict-scan.py --json
   ```
   - De uitvoer is een JSON-array van objecten met: `path_a`, `path_b`, `updated_a`, `updated_b`, `cosine`, `signal`, `excerpt_a`, `excerpt_b`.
   - Als $ARGUMENTS is opgegeven: filter paren waarvan minstens één pad of excerpt het opgegeven onderwerp bevat.
   - Als de array leeg is: rapporteer "Geen tegenstrijdige kandidaatparen gevonden." en stop.

2. Presenteer elk paar aan de gebruiker. Voor elk paar:
   - Toon de bestandsnamen, bijwerkdatums en de excerpts naast elkaar.
   - Lees beide volledige artikelen (zodat de gebruiker de volledige context ziet) en toon de relevante passages.
   - Vraag welke claim survives:
     - **A wint** — artikel B wordt gecorrigeerd
     - **B wint** — artikel A wordt gecorrigeerd
     - **Overslaan** — sla dit paar over zonder wijziging
   - Hint bij twijfel: de meer recente of beter-onderbouwde claim wint doorgaans, maar de **gebruiker beslist**.

3. Op een beslissing (A wint of B wint):

   a. Bepaal het **winnaar-artikel** en het **verliezer-artikel**.

   b. Lees het verliezer-artikel volledig. Stel de gecorrigeerde volledige tekst op:
      - **Frontmatter:** kopieer het frontmatter-blok LETTERLIJK (knip-plak, niet overtypen) uit het verliezer-artikel. Behoud `type`, `created`, `tags`, `status` ongewijzigd. Wijzig uitsluitend `updated` naar de huidige datum.
      - **Body:** herstel of verwijder uitsluitend de tegenstrijdige claim. Behoud alle overige inhoud, backlinks en structuur van het verliezer-artikel.

   c. Schrijf de gecorrigeerde volledige inhoud naar een tijdelijk bestand:
      ```
      /tmp/reconcile-<slug>.md
      ```
      waarbij `<slug>` de bestandsnaam van het verliezer-artikel is zonder extensie.

      > **NOOIT `echo "..." | safe-edit --new -` gebruiken.** De body bevat aanhalingstekens, backticks en `$`/`\` die de shell corrumpeert. Schrijf altijd eerst naar een temp-bestand via het file-write tool.

   d. Pas de wijziging toe:
      ```
      python3 $VAULT/.claude/scripts/safe-edit.py <verliezer-pad> --new /tmp/reconcile-<slug>.md --message "reconcile: <onderwerp>"
      ```
      - Als `safe-edit.py` afsluit met exitcode 2 (action `needs-confirm`, grote wijziging):
        - Toon de afgedrukte diff aan de gebruiker.
        - Vraag expliciete bevestiging voordat je opnieuw uitvoert met `--confirm`.
        - Overschrijf **nooit** stil met `--force`.
      - Verwijder **nooit** automatisch een artikel.

4. Voeg een auditlog-regel toe aan `$VAULT/02-wiki/reconciliation-log.md` (maak het bestand aan als het niet bestaat):
   ```
   - YYYY-MM-DD [[winnaar-stem]] over [[verliezer-stem]] — reden: <korte motivatie>
   ```
   Gebruik als wikilink-doel de **bestandsstam** (filename zonder extensie en zonder mappad) van het winnaar- resp. verliezer-pad. Het verliezer-pad komt rechtstreeks uit de JSON-velden `path_a` of `path_b` van conflict-scan; reconstrueer het niet zelf.
   Gebruik de datum van vandaag. De motivatie is een zin die de gebruiker formuleerde of die je uit de beslissing afleidt.

5. Rapporteer na alle paren:
   - Hoeveel paren bekeken
   - Hoeveel opgelost (gewijzigd artikel + auditlog-regel)
   - Hoeveel overgeslagen

## Regels
- De gebruiker beslist altijd. Neem geen beslissing zonder expliciete keuze (A/B/overslaan).
- Pas het verliezer-artikel minimaal aan: alleen de tegenstrijdige claim, niks meer.
- Bij twijfel over welke passage de tegenstrijdigheid vormt: vraag de gebruiker.
- Taal: volgt de bron
