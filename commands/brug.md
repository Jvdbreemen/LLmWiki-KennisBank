Zoek niet-voor-de-hand-liggende verbindingen tussen twee onderwerpen in de vault. Onderwerpen: $ARGUMENTS

## Vault-root bepalen (VERPLICHT — lees dit eerst)

Bepaal de vault-root ÉÉN keer aan het begin van dit command en gebruik die overal:
`VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`

Gebruik `$VAULT` voor ELK pad hieronder. Gebruik NOOIT een letterlijk `~/KennisBank`- of `C:\...\KennisBank`-pad: dat negeert de `KENNISBANK_VAULT`-env-var en schrijft naar de verkeerde vault.

Verwacht formaat: `/brug onderwerp A & onderwerp B`
Gebruik `&`, `vs`, `en` of een komma als scheidingsteken tussen de twee onderwerpen.

## Doel

Lateraal denken via de vault. Geen vrije associatie, geen buiten-vault kennis. Alleen verbindingen die in de vault aantoonbaar aanwezig zijn, via artikelen of het kennisgraaf.

## Stappen

### 1. Parseer de twee onderwerpen

Neem $ARGUMENTS en splits op `&`, ` vs `, ` en ` of `,`. Resultaat: **onderwerp A** en **onderwerp B**.
Als er geen of maar één onderwerp in $ARGUMENTS staat, stop dan en vraag: "Geef twee onderwerpen, gescheiden door & — bijv. `/brug onderwerp A & onderwerp B`."

### 2. Zoek vault-artikelen per onderwerp

Voer voor elk onderwerp de zoekopdracht uit:

```
python3 $VAULT/.claude/scripts/kb-search.py "<onderwerp A>" --top 5
python3 $VAULT/.claude/scripts/kb-search.py "<onderwerp B>" --top 5
```

> Geef elk onderwerp als ÉÉN geciteerd argument en ontsnap interne aanhalingstekens (anders breekt de shell).

Parseer de JSON-uitvoer: elke query geeft een lijst van `{path, score, snippet}`.
Bewaar de resultatensets als **cluster A** en **cluster B**.

### 3. Graph-first: zoek brugpaden via de kennisgraaf

Controleer of `graphify-out/graph.json` bestaat in de vault (standaard `$VAULT/graphify-out/graph.json`).

**Als graph.json aanwezig is:**

Lees de graaf. Structuur:
- `nodes`: een lijst van entiteiten, elk met een `id` (entiteitslug, bijv. `wiki_sd_kaart_malware_scan_protocol_protocol`) en een `source_file` (het artikelpad, bijv. `02-wiki/wiki-sd-kaart-malware-scan-protocol.md`). Meerdere nodes kunnen naar hetzelfde artikel verwijzen.
- `links`: een lijst van relaties in de vorm `{source, target, relation}` waarbij `source` en `target` entiteitslugs zijn (de `id`-waarden van nodes).
- `hyperedges` (indien aanwezig): groepen co-voorkomende entiteiten in de vorm `{id, label, nodes:[...], relation}`.

Koppel een cluster-artikel (een pad uit kb-search) aan graph-nodes door het pad te vergelijken met het `source_file`-veld van elke node. Beschouw **alle** nodes waarvan `source_file` overeenkomt met dat artikel als behorend tot het cluster.

Traverseer de graaf om **brugpaden** te vinden:
- Zoek de nodes die overeenkomen met de gevonden artikelen in cluster A en cluster B (via `source_file`-match).
- Zoek tussenliggende nodes (afstand 1-2 stappen via `links`) die zowel verbonden zijn met een node uit cluster A als een node uit cluster B.
- Noteer elk brugnodepad: `A-artikel -> tussenknoop -> B-artikel`, inclusief de `relation`-waarden op de links. Los intermediate node-ids op naar hun `source_file` voor de `[[wikilink]]`.
- Als `hyperedges` aanwezig zijn: behandel elke hyperedge waarvan `nodes` zowel een cluster-A- als een cluster-B-entiteit raakt als een sterk brugssignaal.

Gebruik deze graaf-bruggen als primaire bron voor de verbindingen in stap 5.

**Als graph.json niet aanwezig is of geen pad gevonden:**

Ga verder naar de terugval (stap 4).

### 4. Terugval: embedding-space bruggen

**Terugval-strategie** (gebruik dit als graph.json ontbreekt, onleesbaar is, of geen brugpad oplevert):

Zoek artikelen die matig scoren op BEIDE onderwerpen tegelijk — dat zijn potentiële brugartikelen die in beide domeinen voorkomen:

```
python3 $VAULT/.claude/scripts/kb-search.py "<onderwerp A> <onderwerp B>" --top 10
```

Vergelijk de uitvoer met cluster A en cluster B:
- Artikelen die voorkomen in zowel cluster A als cluster B zijn sterke brugkandidaten.
- Artikelen die in de gecombineerde query hoog scoren maar niet in de top-5 van A of B staan, zijn ook relevante tussenpunten.

Lees de meest veelbelovende brugartikelen volledig voor gebruik in stap 5.

### 5. Formuleer de verbindingen

Produceer **2 tot 4 concrete, niet-voor-de-hand-liggende verbindingen**. Per verbinding:

- Beschrijf de brug in 1-3 zinnen: waarom hangen deze onderwerpen samen?
- Geef de betrokken bronartikelen als wikilinks: `[[artikel-naam]]`
- Maak onderscheid tussen graaf-gebaseerde en terugval-gebaseerde verbindingen als beide zijn gebruikt.

Geef voorkeur aan onverwachte koppelingen. Sla voor de hand liggende overlappingen over.

### 6. Eerlijkheidsregel

Als er na stap 3 en stap 4 geen zinvolle brug te vinden is (artikelen bestaan nauwelijks of overlappen niet), zeg dat dan direct:
"Geen betekenisvolle brug gevonden tussen [A] en [B] op basis van de huidige vault-inhoud."
> **Let op:** een leeg resultaat kan ook betekenen dat de embed-index nog niet gebouwd is. Herstel met `python3 $VAULT/.claude/scripts/build-embed-index.py` en probeer opnieuw.
Stop hier. Verzin niets.

## Regels

- Alle verbindingen zijn vault-intern. Geen buitenvault-kennis.
- Elke verbinding citeert zijn bronnen als `[[artikel-naam]]`.
- Compact en direct. Geen essays.
- Graph-first is de voorkeursmethode; terugval is expliciet de tweede keuze.
- Bij lege of onduidelijke $ARGUMENTS: vraag eerst om verduidelijking.
