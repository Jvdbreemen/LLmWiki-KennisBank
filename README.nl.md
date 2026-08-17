# LLmWiki-KennisBank

[English](README.md) · **Nederlands**

> **Installeren met een AI-agent?** (Claude Code, Claude Cowork, Codex,
> Copilot CLI, OpenCode) → volg de
> **[Agent install guide](docs/AGENT-INSTALL.md)** (Engels). Eén commando per
> platform; `AGENTS.md` is het onderliggende deploy-contract.

**Een soevereine geheugenlaag voor serieus AI-werk.**

Elke agent-sessie creëert waardevolle context: beslissingen, fixes, voorkeuren,
architectuur-afwegingen, doodlopende wegen, en lessen die je volgende week niet
opnieuw wilt ontdekken. Dan vergeet het model. KennisBank verandert die
tijdelijke context in een duurzaam lokaal kennissysteem voor Claude Code, Codex,
OpenCode, de GitHub Copilot CLI, en andere ontwikkelaars-agents.

Het legt vast wat er gebeurde, destilleert het tot een wiki met bronvermelding,
extraheert tijdsbewuste herinneringen, haalt de juiste kennis op vóór het
volgende antwoord, en meet of die kennis daadwerkelijk hielp. Het resultaat is
een AI-werkplek die na verloop van tijd scherper wordt zonder je privéwerk uit
handen te geven aan een gehoste geheugenleverancier.

Platte markdown. Lokale SQLite. Standaard lokale Ollama. Je eigen machine. Jij
blijft hoofdredacteur: het systeem stelt voor, plaatst in quarantaine, en
markeert, maar een mens voegt samen, vervangt, en beslist. Open de kluis in
Obsidian en het zijn gewoon notities. Zeer goed geordende notities die toevallig
een AI-geheugen aandrijven.

## Eersteklas integraties voor codeeragents

Eén `setup.sh`-flow installeert en upgradet KennisBank voor **Claude Code**,
**OpenAI Codex** en de standalone **GitHub Copilot CLI** op Windows, macOS en
Linux. OpenCode blijft ondersteund als extra lokale client.

- Skill- en promptbeschrijvingen zijn in het Engels, zodat elke client ze
  consistent kan ontdekken.
- Elke client registreert één fail-open coördinator bij sessiestart en één bij
  afsluiten. Onafhankelijke jobs draaien parallel en afhankelijk werk volgt in
  expliciete fasen. Geen-wijziging-uitvoer blijft stil.
- Een client kan nog één generieke regel per lifecycle-event tonen; die
  client-eigen UI-regels zijn niet portabel te onderdrukken met behoud van
  automatisering.
- Setup vervangt alleen oude KennisBank start/exit-hooks en bewaart andere
  hooks van gebruikers plus prompt- en presearch-gedrag.
- Dezelfde lokale stdio MCP-server en expliciet ingestelde
  `KENNISBANK_VAULT` bedienen alle geïnstalleerde clients.

Installeer of upgrade de drie eersteklas clients:

```bash
KENNISBANK_VAULT="/absoluut/pad/naar/kluis" bash setup.sh --yes --agents claude,codex,copilot
```

Gebruik na het herstarten `$sessiestart` en `$sessielog` in Codex
(`/prompts:sessiestart` blijft als compatibiliteitsalias), of `/sessiestart` en
`/sessielog` in Copilot.

Gebaseerd op [Andrej Karpathy's LLM Wiki-patroon](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): ruwe sessies gaan erin, gestructureerde kennis komt eruit. KennisBank breidt het patroon uit tot een gesloten lus:

```
capture ──> consolidate ──> retrieve ──> measure
   ^                                        │
   └────────────── learn <─────────────────┘
```

- **Capture**: sessie-logs, transcript-archivering, en een autonome geheugen-sweep die kandidaat-herinneringen extraheert, typeert, en beoordeelt na elke sessie.
- **Consolidate**: `/wiki` compileert sessies tot wiki-artikelen met herkomst per bewering; nieuwe feiten verzoenen zich met oude op schrijftijd (add, supersede, of drop) met een bi-temporeel geldigheidsmodel.
- **Retrieve**: hooks injecteren relevante wiki-artikelen en herinneringen in elke prompt, in elk project: hybride semantisch + trefwoord-zoeken, gerangschikt op relevantie x recentheid x belang, uitgebreid met de best-verbonden graaf-buur.
- **Measure**: een recall@k eval-harnas en een drempel-kalibratie-harnas maken elke retrieval-wijziging testbaar in plaats van op-gevoel.
- **Learn**: gebruikstelemetrie volgt welke geïnjecteerde kennis daadwerkelijk werd gebruikt, geeft warme documenten een boost en houdt recent gebruikte artikelen uit de stale-lijst.

## Waarom dit bestaat

Geheugensystemen van leveranciers (Mem0, Zep, Letta, Cognee) zijn krachtig maar cloud-gevormd: jouw kennis leeft in hun opslag, achter hun API, op hun prijsniveau. KennisBank neemt de twee mechanismen die er echt toe doen uit die literatuur - temporele geldigheid van feiten en invalidatie-op-schrijven - en herbouwt ze in platte markdown-frontmatter plus SQLite. Wat jij bezit blijft portable; wat de agent nodig heeft blijft snel.

De ontwerpvoorkeur is overal dezelfde: **deterministisch waar mogelijk, LLM alleen waar het oordeelsvermogen toevoegt, fail-open overal**. Een dood model blokkeert nooit een sessie, verliest nooit een transcript, en verwijdert nooit geverifieerde kennis.

## Functie-highlights (v0.34.0)

### Nieuw in v0.34.0

De autonome review onthoudt wat hij al gevraagd heeft.

**Een oordeel dat nooit verandert bezet niet langer de begroting.** v0.33.0
liet gequarantineerde memories zichzelf reviewen, maar niets onthield de
antwoorden, dus stelde de grounded check elke sweep dezelfde vraag over
dezelfde passage en kreeg hetzelfde antwoord. Op de vault die dit blootlegde
gingen 40 van de 40 plaatsen naar memories die een hele-transcript-lezing al
`partial` had genoemd, terwijl 49 nieuwere memories nooit beoordeeld werden.
Vangnet 1 legt zijn eigen uitkomsten nu vast en kiest kandidaten in twee
lagen — eerst nooit beoordeeld, dan wat zijn venster voorbij is, zodat
herbeoordelingen roteren. Het ordent, het sluit nooit uit: vangnet 1 leest
een geselecteerde passage waar de client het hele transcript leest, dus het
promoveert nog steeds memories die de client `partial` noemde, en juist die
promoties trekken de wachtrij leeg.

**De sessiestart-melding zegt iets waar je wat mee kunt.** Hij rapporteerde
één getal en wees naar de instellingen of Ollama; op een vault waar beide in
orde waren en elke memory al beoordeeld was, waren dat drie foute antwoorden
in één zin. Hij rapporteert nu twee tellingen — wachtend op een oordeel
versus beoordeeld en onbeslisbaar — en noemt per geval het pad dat
daadwerkelijk iets verplaatst, inclusief `memory-doctor.py decide` voor de
helft die alleen een mens kan afhandelen.

**Boekhouding die veilig faalt.** Een inconclusieve uitkomst verloopt in uren
in plaats van genegeerd te worden, want `no_transcript` is deterministisch en
zou een kapotte bron anders eeuwig aan de kop van de wachtrij parkeren. Een
geweigerde schrijfactie koopt geen cooldown meer. Een onleesbaar
statusbestand wordt opzijgezet in plaats van overschreven. Geen migratie: de
eerste sweep na de upgrade beoordeelt de oudste memories nog één keer, en de
sweep daarna besteedt zijn begroting al aan nieuwe kennis.

### Nieuw in v0.33.0

De mens verlaat de geheugenlus.

**Gequarantineerde memories reviewen zichzelf.** Drie vangnetten, elk
gepoort door vooraf geregistreerde metingen: het lokale model promoveert wat
het eigen brontranscript van een memory ondersteunt (nooit gefabuleerd in
210 controles); de client-LLM beoordeelt hele transcripts voor de rest —
achter een expliciete `auto_review_llm`-toggle, standaard UIT, want dat is
cloud; intrekken vergt dubbele overeenstemming plus een mislukte
weerlegging, begrensd en omkeerbaar. Eerste echte run: 993 gequarantineerde
memories teruggebracht tot 42, recall@1 +0.035.

**`/kennisbank:review` is nu een audit-view**, geen werkwachtrij: wat het
systeem besloot, op welk bewijs, met terugdraaien per regel (`demote` /
`reopen`). Geen stap wacht op een mens.

**Een golf stil-falende defecten is weg**, elk adversarieel geverifieerd
vóór de fix: een checkout die de vault naar `$HOME` resolvede, één
env-var-typfout die retrieval voor elke sessie uitschakelde, een
sweep-fallback die nul memories schreef, een default-modelflip waarvan de
doctor-check valse geruststelling gaf, een lock-race die twee indexbouwers
tegelijk draaide, FTS-rijen die een cap-fix nooit bereikte, en memories
beoordeeld met de embedding van hun vorige inhoud. De open backlog ging
naar nul, elke taak met zijn bewijs of zijn parkeer-reden.

### Nieuw in v0.32.0

De geheugenlaag behandelt "nieuwere uitspraak over hetzelfde onderwerp" niet
langer als "volledige vervanging".

**Elke supersessie die deze vault ooit maakte is handgelabeld** (237 paren,
twaalf parallelle lezers, adversariële verificatie): 61% duplicaat-opruiming,
11% echte vervanging — en **27% versmalling**: de opvolger liet feiten vallen
waarvan het gesloten memory de enige drager was. Het recall-pad filtert op
`status=current`, dus die feiten stonden niet lager — ze waren weg.

**Sluiten vereist voortaan dekking.** Beide sluitende judges eisen dat een
opvolger alles van blijvende waarde meeneemt voordat het oude memory sluit;
gedeeltelijke dekking houdt beide open. Nagespeeld op alle geadjudiceerde
paren: kennisverliezende sluitingen dalen van 57,8% naar 37,5%, de
duplicaat-afhandeling blijft gelijk.

**De 64 ten onrechte gesloten memories zijn terug.** Vragen die alleen zij
konden beantwoorden gingen van recall@5 0,000 naar 0,333–0,600; de volledige
eval van 1224 vragen bewoog hooguit +0,002.

Ook nieuw: een versheids-bewuste eval-set (89 vragen, holdout bewust
ongebruikt) die de derde onafhankelijke meting tegen de recency-weging
opleverde — die verslaat ruwe cosine zelfs op eigen terrein niet.

### Nieuw in v0.31.1

Een patch met een fix die twee dagen geleden al geschreven, gereviewd en
goedgekeurd was en daarna nooit gemerged — de commit die de Copilot-review op
PR #114 verwerkte bleef op zijn branch achter.

**De C4-referentie schreef de bug voor waar zijn eigen skill voor waarschuwt.**
Hij documenteerde de upgrade-stempel als `git rev-parse --short $LATEST`, zonder
`^{}`. Tags zijn hier annotated, dus dat legt het tag-object vast in plaats van
de commit — precies hoe v0.28.0 en v0.29.0 allebei een SHA kregen die in geen
enkele branch voorkomt.

Een tekstuele verduidelijking in stap 10 van `kennisbank-upgrade` rijdt mee. Die
leest prettiger maar verandert niets aan het gedrag; beide vormen zijn getest om
dat vast te stellen.

### Nieuw in v0.31.0

Een release over meten: drie dingen die deze repository geloofde bleken bij
controle niet te kloppen, en de nuttigste verandering is één regel.

**Lange wiki-artikelen zijn weer vindbaar.** De full-text-index bewaarde alleen
de eerste 4000 tekens van een document — de afkapping die het *embedding*-model
nodig heeft, omdat dat op een contextgrootte draait die VRAM vrijhoudt. FTS5
kent die limiet niet en betaalde hem toch, waardoor 72 van de 206 artikelen
deels onzichtbaar waren voor beide helften van de hybride zoekactie. Vragen over
tekst voorbij dat punt gaan van **recall@5 0,450 naar 0,725**, terwijl de
bestaande set van 329 vragen onveranderd blijft.

**Draai na de upgrade één keer `build-kb-index.py --rebuild`.** De opgeslagen
tekst veranderde, de bestands-hashes niet, dus de incrementele build ziet geen
aanleiding en je houdt anders de oude index.

**Memories leggen vast waar ze vandaan komen.** Een gesweepte memory draagt nu
`source_chunk: "N/M"`: de chunk van het bron-transcript waaruit hij is
geëxtraheerd — bekend op het moment van vastleggen en tot nu toe weggegooid.

**Een net-niet-geldig JSON-antwoord verdwijnt niet meer.** Vier van de 56
verifier-antwoorden telden als onleesbaar; alle vier bevatten een correct
gevormd object met kapotte string-delimiters. De reparatie draait alleen nadat
een eerlijke parse is mislukt, en telt alleen als het resultaat dan parseert.

**De trust-factor is gemeten en afgewezen.** Een lokaal model vragen of een
memory door zijn eigen bron wordt gedragen werkt beter dan verwacht en is toch
het verkeerde om op te ranken: het antwoordt `supported` voor 88,7% van de
memories, en van 20 `unsupported`-oordelen die tegen hele transcripts zijn
nagetrokken klopte er nul. `supported` mag vertrouwen verhogen; niets mag het
verlagen. Zie `docs/research/llm-trust-verification-2026-08-15.md`.

### Nieuw in v0.30.0

v0.29.0 repareerde een geheugenlaag die stil was gestopt met vastleggen. Deze
release gaat over de beslissingen die hij neemt nu hij weer vastlegt — en over
het feit dat je daar tot nu toe niets van zag.

- **Een gesloten memory is weer zichtbaar, en werkelijk omkeerbaar.** Het
  ontwerp leunde erop dat superseden veilig is omdat er niets verdwijnt. Waar op
  schijf en onwaar in elk ander opzicht: recall filtert op `current` en
  `/kennisbank:review` loopt alleen de `unverified`-wachtrij, dus een gesloten
  memory verscheen nergens waar een mens kijkt. Elke sluiting staat nu in een
  logboek met opvolger en reden, en `memory-doctor.py closed` / `reopen <stem>`
  is de weg terug.
- **`volatility: state | event` legt de updateregel in de structuur.** Een state
  wordt vervangen als de waarde verandert; een event wordt nooit gesloten. Dat
  uit proza afleiden scoorde 7/20, 5/20 en 4/20 bij drie modellen, dus het wordt
  nu één keer beslist, op schrijfmoment. Op de levende vault beschermt de guard
  drie paren die alleen maar op elkaar lijken — waaronder de locaties van twee
  *verschillende* skills op cosinus 0.867.
- **`kb-state-audit.py` vergelijkt memories met een gezag**, niet met elkaar: 4
  tegenstrijdigheden gevonden op deze vault, stuk voor stuk een verouderde
  `qwen3-embedding:8b`, zonder één modelaanroep — plus een dekkingsregel die
  zegt waar hij blind was.
- **Supersede-paren vinden is 11x sneller met identieke uitkomst.** 1.271.215
  paarsgewijze vergelijkingen (1171,86 s) worden een indexquery (106,94 s) die
  dezelfde 163 paren teruggeeft. Exact, geen benadering, met het oude pad als
  terugval.
- **Twee prompts herordend en hermeten.** Reconcile: NOOP op ongerelateerde
  paren 25% → **0%**. Supersede: herkenning van echte vervangingen 30% → **55%**.
- **Voortgang en een schatting op elk langlopend script**, want een sweep die
  tien minuten draait zonder iets te schrijven is niet te onderscheiden van een
  hang. `KB_NO_PROGRESS=1` zet het uit.

Twee metingen spraken de taak tegen die erom vroeg, en allebei staan ze in de
changelog in plaats van stilletjes te verdwijnen: de supersede-judge blijkt
**niet** te voorzichtig (86% van zijn weigeringen is terecht; de vastgelegde
geschiedenis zit vol opgeruimde duplicaten), en de corpus laten groeien kostte
`recall@5` op memory 0,778 → 0,768, onder een ondergrens die een dag eerder was
vastgelegd.

### Nieuw in v0.29.0

> **Upgraden:** draai `ollama pull qwen3.5:4b` en zet daarna `"model"` in
> `<vault>/.claude/kennisbank-llm.json` op dezelfde waarde. `setup.sh` kopieert
> dat bestand bij de installatie en overschrijft het nooit, dus elke bestaande
> vault draagt een pin die het wint van de code-default — laat je hem staan, dan
> blijven je hooks het oude model laden.

De geheugenlaag was stilgevallen zonder dat iets dat meldde. Drie onafhankelijke
oorzaken, alle drie onzichtbaar om dezelfde reden: elke seam is fail-safe, dus
een onderdeel dat nooit antwoordt ziet eruit als een onderdeel dat niets te
melden had.

- **De judge dacht zijn eigen antwoord weg.** `qwen3.5` is een reasoning-model
  en zijn gedachtegang verbruikte hetzelfde contextbudget als het antwoord.
  Gemeten op drie echte paren: 30-56 s per call, en **één op de drie kwam leeg
  terug** — waarna `extract` `[]` geeft, `judge` `unverified` en `reconcile`
  `ADD`, alle drie geruisloos. Met `think: false`: 1,6 s, geen enkele leeg.
- **Capture kon maar één client lezen.** De parser kende alleen de vorm van
  Claude Code, dus Codex- en Copilot-sessies leverden niets op: **39 van de 299
  gearchiveerde transcripts, 94 MB**, waaronder sessies van 21 en 26 MB. Een
  onleesbaar transcript wordt wél gesweept en wél afgevinkt, en dat ziet eruit
  als een sessie waarin niets gebeurde. Nu 7 van de 299, samen 0,07 MB.
- **Capture las zes chunks van een sessie.** Gemeten over vier lange transcripts
  en 120 extractie-calls: **78% van alle unieke kennis zit voorbij chunk 6**, met
  0,9% duplicaten. De cap ging ervan uit dat het vervolg herhaling is; dat is
  niet zo. Nu 40 chunks en 60 memories per transcript, met een budget van 150
  chunks per run zodat een sweep de GPU niet bezet houdt die retrieval nodig
  heeft.
- **Eén judge-model, passend naast de embedder.** Acht plekken schreven een
  modelnaam en spreken elkaar niet meer tegen. `qwen3.5:4b` kost 3,13 GB en past
  naast `qwen3-embedding:4b` (4,06 GB) op een kaart van 16 GB; het oude
  `gemma4:12b` vroeg 8,06 GB, verdrong de embedder, en daarna liep elke recall
  tegen een koude load van 30-60 s aan met een budget van 2 s.

### Nieuw in v0.28.0

> **Upgraden:** draai eerst `ollama pull qwen3-embedding:4b`. `setup.sh`
> valideert met `ollama show` en pullt niet, dus een vault zonder het model
> laat de installatie luid vallen. De eerste index-build daarna embedt de hele
> vault opnieuw, omdat de modelidentiteit bepaalt of de cache herbruikbaar is.

- **Een gemeten default in plaats van een geërfde.** Negen embedding-modellen
  zijn tegen de eigen eval-sets van dit project gedraaid, omdat publieke
  benchmarks op publieke corpora ranken en de marges hier twee tot vier punten
  zijn. `qwen3-embedding:4b` wint op beide lagen én is sneller (322 ms tegen
  347 ms warme p50) bij 2,2 GB minder beslag op de kaart.
- **De memory-laag gooide een derde van zijn eigen index weg.** Zijn
  gelijkenisdrempel van 0,60 was geijkt op tekst van artikellengte;
  memory-fragmenten scoren structureel lager. Ook op het vorige model
  nagemeten, dus dit was een staande fout en geen migratiegevolg. De drempel
  staat nu op 0,45.
- **Lexicaal zoeken trekt de memory-laag niet langer omlaag.** RRF weegt zijn
  twee ranglijsten gelijk, en dat loont alleen als ze vergelijkbaar sterk zijn.
  Op wiki zijn ze dat en verslaat de fusie beide armen. Op memory verslaat hij
  er geen, dus de lexicale helft is daar weg: recall@5 gaat van 0,658 naar
  0,794.
- **Instructieprefixen per zijde**, zodat e5, embeddinggemma, arctic-embed en
  nomic draaien zoals ze getraind zijn. Standaard uit; de documentprefix hoort
  bij de cache-identiteit.
- **Drie meetharnassen** — `embed-sweep.py` (modellen tegen een scratch-vault),
  `recall-ablation.py` (dens versus lexicaal), `rerank-eval.py` (wat een
  cross-encoder toevoegt). Methode en volledige resultaten in
  `docs/research/embedding-model-sweep-2026-08.md`.

### Nieuw in v0.27.0

- **Het embedding-endpoint kan niet meer buiten je machine wijzen zonder dat je
  dat zegt.** Het werd letterlijk uit `kennisbank-embed.json` overgenomen en
  gebruikt vóór de API-sleutelcontrole, dus één configwijziging stuurde elke
  prompt — en bij de volgende rebuild de hele vault — naar een willekeurige
  host, terwijl de no-cloud-waarschuwing niets meldde. Localiteit wordt nu
  afgedwongen op het punt waar de aanvraag vertrekt. Draai je Ollama op een
  andere machine, zet dan `KB_EMBED_ALLOW_REMOTE=1`.
- **Capture kan geen memory meer wissen die jij hebt goedgekeurd.** Twee titels
  die naar dezelfde bestandsnaam sluggen landden op hetzelfde bestand, dus een
  tweede capture overschreef een goedgekeurde memory — status teruggezet, tekst
  weg, geen backup, en een succesmelding. Botsende titels landen nu naast
  elkaar.
- **Een ontbrekende index kost geen zeven seconden per prompt meer.** Tijdens
  een index-rebuild viel elke prompt terug op het parsen van een JSON-cache van
  170 MB in pure Python (6766 ms, 186 MB). Die fallback is verwijderd; je krijgt
  dezelfde zichtbare melding die de hook al toont bij een koud model, en de hot
  path blijft op ~1,2 s.
- **`setup.sh --skip-doctor`** voor tests en CI die `doctor.sh` zelf draaien.
  Een gewone installatie draait de afsluitende gate nog steeds.

### Nieuw in v0.26.1

- **De C4-documentatieset klopt weer met de code die hij beschrijft.** De
  specificatie voor de architectuurplaat noemde vijf vaultmappen terwijl er tien
  zijn, beweerde dat alle vier de SQLite-databases uit de markdown herbouwen
  terwijl `kb-usage.db` dat niet kan, en noemde een Atlas-lens die al een tijd
  verwijderd is.
- **`claude-cli` staat weer in de gedocumenteerde consent-grens.** Het is een
  cloud-provider naast OpenRouter, en juist degene die geen van beide
  installers aanbiedt, dus degene waar een lezer het meest over ingelicht moet
  worden. De waarschuwing per aanroep, en hoe de dekking daarvan verschilt van
  die bij setup, staat nu beschreven in plaats van als open vraag.

### Nieuw in v0.26.0

- **MCP-tools vertellen nu wat ze zijn.** Elke tool draagt annotaties, dus een
  client weet welke aanroepen read-only zijn en parallel mogen draaien. Zes
  retrieval-tools presenteerden zich eerder als mogelijk destructief, wat
  bevestigingsprompts en serialisatie op de interactieve weg kostte.
- **Een kapotte `mcp`-installatie ziet er niet meer gezond uit.** `pip install
  mcp` landt nu op 2.x, waar de oude server-API weg is; dat gaf eerder een stil
  dode MCP-server die met exit 0 eindigde. Hij faalt nu luid en zegt waarom.
- **C4-architectuurdocumentatie** onder `C4-Documentation/`: code-, component-,
  container- en contextniveau, plus een gedimensioneerde specificatie voor één
  hoog-over architectuurplaat.
- **De `mcp>=2`-bump zit er bewust niet in.** Een modern-only server breekt
  vandaag elke client in gebruik; de upgrade is gated op een meting. Zie
  `docs/superpowers/plans/mcp-2026-07-28-migration.md`.

### Nieuw in v0.25.0

- **Een eval telt nooit als gebruik.** De recall-ranking wordt gevoed door
  usage-telemetrie, dus een eval die zijn eigen recall-aanroepen wegschreef,
  mat een signaal dat hij zelf net had verschoven. `kb-eval` zet de
  usage-telemetrie nu uit voor de duur van elke run — onvoorwaardelijk, geen
  vlag om te onthouden — en herstelt de vorige staat daarna, zodat het leren
  gewoon doorgaat. De run meldt dat op stderr, vóór en na de resultaten.
- **`doctor.sh` betrapt een verdwaalde `KB_USAGE_DISABLE`.** Blijft die in je
  shell-profiel staan, dan leert de KennisBank stil niets meer van gebruik.
  Dat wordt nu gemeld in plaats van onzichtbaar.

### Nieuw in v0.24.1

- **Geen console-popups meer op Windows.** De losgekoppelde
  indexonderhouds-worker opende bij elke sessiestart per achtergrondjob een
  zichtbaar console-venster. Jobs draaien nu met `CREATE_NO_WINDOW`, dus
  achtergrondonderhoud is weer onzichtbaar.
- **Privacy-guard voor eval-sets.** Persoonlijke eval-sets kunnen nooit in
  de repository of een release belanden (`.gitignore` +
  `test_eval_privacy.py`); de meegeleverde voorbeeldsets zijn volledig
  gefingeerd.

### Nieuw in v0.24.0

- **Graafretrieval, bewezen en standaard aan.** De `(buur)`-entry komt nu
  uit de gewogen graafindex (`kb-graph.db`, submilliseconde) in plaats van
  een regex over artikelteksten. Gemeten op een eval-set van 329 vragen:
  recall@1 0.745 -> 0.790, recall@5 -> 1.000, MRR 0.836 -> 0.882 — óók
  single-hop. Toggle `graph_retrieval` zet hem terug uit.
- **Evidence-first eval-harnas.** `kb-eval` meet nu exact wat de hook
  draait (drempel- en expansie-pariteit), rapporteert `--latency` p50/p95
  en A/B't varianten met `--expand/--no-expand`; `kb-eval-gen.py` stelt
  kandidaat-vragen voor als drafts zodat eval-sets groeien zonder handwerk.
  Dezelfde poort WEES llm_wiki's source-overlap-boost af op echte data —
  de knop bestaat maar blijft uit, met de cijfers vastgelegd.
- **Menselijke memory-review overal.** `/kennisbank:review`,
  `memory-doctor.py pending/decide` en MCP `review_pending/review_decide`
  delen één crash-veilig beslispad met de Atlas-GUI: approve, reject of
  skip voor unverified memories; een gefaalde write meldt zich nooit als
  beslist.
- **Deterministische poorten.** `wiki-scan.py` sluit het laatste vrije
  LLM-beslispunt van /wiki; een weigering-poort houdt "ik kan dit niet
  beantwoorden" uit het archief; kb-lint weigert conclusies als bewijs
  (`self-source`) en toont index-drift; `kb-normalize.py` herstelt link- en
  tagvorm na elke LLM-write; sweep-memories dragen `model_id`+`prompt_version`.
- **Atlas: heatmap, Cmd+K, facetten — en CI.** De Overzicht-lens toont een
  365-dagen-activiteitsheatmap en freshness-buckets; Cmd/Ctrl+K springt naar
  elke lens of elk document; de Recall Inspector filtert op laag en
  exporteert de waterfall als JSON. Atlas-sidecar+frontend-tests draaien nu
  in CI.
- **OKF v0.2-export.** `kb-okf-export.py` rendert de vault als Open
  Knowledge Format-bundle — trust-tiers mappen 1-op-1 op de
  memory-levenscyclus; deterministisch en byte-idempotent.

### Nieuw in v0.23.0

- **Vault-orientatie bij sessiestart.** `kb-orientation.py` vat de vault in
  een paar regels samen: documentcounts, recent gewijzigde artikelen,
  veelgebruikte kennis, open backlog-taken. Puur SQL, sub-seconde.
  `/sessiestart` draait hem standaard; de opt-in toggle `orientation`
  injecteert hem bij elke sessiestart.
- **Agent install guide.** `docs/AGENT-INSTALL.md` geeft AI-agents de kortste
  correcte installatieroute per platform (Claude Code, Codex, Copilot CLI,
  OpenCode, Claude Cowork), gelinkt bovenaan beide README's.

### Nieuw in v0.22.0

- **Een checkpoint-primitief dat context-compaction overleeft.** `/checkpoint`
  legt een vooruitkijkend werkstand-snapshot vast (actieve taak, open
  beslissingen, volgende stap) in de vault; een opt-in toggle `checkpoints`
  laat Claude's PreCompact-hook vlak vóór compaction automatisch een stub
  schrijven, en de sessiestart-coordinator meldt open checkpoints *vóór* zijn
  freshness-gate — precies het moment waarop een compact-event de melding
  anders zou opslokken. Codex en Copilot krijgen hetzelfde herstel-pad en een
  handmatig `$checkpoint` / `/checkpoint` command.
- **De kennisgraaf is een queryable laag geworden.** `graph.json` laadt nu in
  een eigen `kb-graph.db` (fingerprint-gated, herbouwd door de
  achtergrondworker), met een deterministische edge-laag uit wikilinks en
  frontmatter, een link-only provenance-ring voor sessielogs, en scope via
  `.graphifyignore`. Een volledige herbouw van `kb-index.db` sleurt de graaf
  niet meer mee.
- **Sessiestart werd een orde van grootte sneller.** Koude start van 35,7 s
  naar 1,3 s: de notificatietier is losgekoppeld, de rot-telling verhuisde
  naar de achtergrondworker en de statusregel leest alleen nog voorberekende
  state. De testsuite draait `setup.sh` ook niet meer achttien keer.
- **Geheugen ontdubbelt bij het schrijven**, een koud embedding-model meldt
  zichzelf in plaats van stil te falen, en elke settings-toggle is nu via een
  test gekoppeld aan de oppervlakken die hem beheren.

### Nieuw in v0.21.0

- **Retrieval heeft een relevantiedrempel.** De hook injecteerde onvoorwaardelijk
  de top-k, dus een prompt zonder iets relevants kreeg alsnog de drie
  minst-slechte documenten, en het geheugenblok had helemaal geen poort. De
  drempel ligt nu op de cosinus, gratis afgeleid uit de afstand die de
  vectorindex toch al teruggeeft. Je index wordt bij de eerste sessie na de
  upgrade eenmalig herbouwd.
- **SessionStart blokkeert niet meer.** De drie indexbouwers draaiden inline —
  ruwweg 210 s worst case, en 300 s voor Copilot, boven de timeout die die client
  zelf declareert. Onderhoud draait nu in een losgekoppelde worker achter een
  lock, wat meteen een einde maakt aan twee processen die tegelijk dezelfde index
  schreven.
- **De embedding-cache is van de hot path af.** Elke niet-triviale prompt parste
  tientallen megabytes JSON en scoorde de hele corpus in pure Python, om iets te
  bepalen wat de index allang weet. Hij is nu alleen nog de terugvalweg voor een
  kapotte index.
- **`/kennisbank-release`.** Releasen ging sinds v0.16.0 met de hand. De skill
  legt de procedure vast, inclusief de twee stappen die vorige keer handmatig
  misgingen, en een test koppelt nu de changelog-versie aan beide README-koppen,
  zodat een halve bump rood wordt in plaats van geshipt.

### Nieuw in v0.20.0

- **Drie stille faalmodi op kernpaden.** Memory-recall gaf een lege lijst zodra
  een kluis boven ~1024 documenten kwam (sqlite-vec weigert een KNN met
  `k > 4096`, en die fout viel buiten het afgeschermde blok). Elke temporele
  vraag kwam op hetzelfde foute bereik uit met hoge confidence, doordat een lege
  regex-alternatie de lege string matcht. En `activity-locales.json` werd
  helemaal nooit naar een kluis gedeployed, dus een schone installatie draaide
  met een lege vocabulaire. Geen van de drie logde iets.
- **`safe-edit` kan het wiki-schrijfpad niet meer blokkeren.** Hij schrijft vóór
  de git-stap, dus een mislukte commit liet het artikel overschreven en de boom
  vuil achter — waarna elke volgende aanroep weigerde, terwijl `/wiki` en
  `/reconcile` `--force` verbieden. De oorspronkelijke bytes worden nu
  teruggezet.
- **CI draait de volledige suite.** `unittest discover` sloeg 19 tests over die
  als module-level functies geschreven zijn, waaronder de documentatie-guard die
  nog nooit had gedraaid — de reden dat verouderde doc-claims bleven staan. Een
  nieuwe lint bewaakt tweetalige feitpariteit en code-afgeleide claims, en vond
  meteen twee echte gaten.
- **Goedkoper indexonderhoud.** Vier write-only tabellen weg (~23,7 MB en een
  full scan per event), bron-hashing lui gemaakt, en de rollup-cache verwijderd
  nadat gemeten was dat hij antwoorden voor de verkeerde query teruggaf.

### Nieuw in v0.19.0

- **Grote sessies destilleren zonder de context te verzuipen.** `/destilleer`
  kan nu een groot transcript reduceren tot platte conversatietekst met de
  nieuwe `strip-transcript.py` (thinking, tool-calls en subagent-turns eruit,
  ~10-25x kleiner) en het werk over subagents verdelen. De command-docs maken
  het onderscheid stub-versus-transcript expliciet en benoemen de overlap met
  `/sessielog`, en `/wiki` krijgt een `kb-lint --json`-recept om de herkomst van
  een nieuw artikel schoon te bewijzen.

### Nieuw in v0.18.1

- **Deterministisch runtimebudget voor de prompt-hook.** Interactieve retrieval
  heeft nu een apart hard plafond van 2 seconden, zodat een oude of per ongeluk
  hoge `KB_RETRIEVE_TIMEOUT` de UserPromptSubmit-hook niet kan vasthouden tot de
  client hem afbreekt. Langere wachttijden vereisen dat zowel de gevraagde
  timeout als `KB_PROMPT_HOOK_MAX_EMBED_TIMEOUT` expliciet wordt verhoogd.

### Nieuw in v0.18.0

- **Geen cold-model-timeout op de eerste prompt.** De `kb-retrieve`-hook timet niet
  meer af op een cold embedmodel: hij embed één keer per prompt, begrenst de
  hot-path-embed met een expliciete timeout (2,0s), en self-healt door het model bij session-start
  voor te warmen en bij een miss een detached warm te vuren. Volledig lokaal en
  fail-open.
- **Upstream-drift-waarschuwing.** Een session-start-notificatie waarschuwt als
  je git-repo achter zijn upstream loopt (huidige branch en/of `main`).
  cwd-aware en stil als alles up-to-date is; alle clients krijgen 'm uit de ene
  coordinator.

### Nieuw in v0.17.1

- **Eén gecoördineerde start- en exit-hook per client.** Startonderhoud is
  gefaseerd en parallel. Bij afsluiten wordt eerst vastgelegd; daarna draaien
  gebruikstoekenning en Copilot-import parallel. Beide paden zijn tijdbegrensd,
  stil bij routinesucces en fail-open.
- **Native gecoördineerde sessieworkflows.** Copilot biedt `/sessiestart` en
  `/sessielog`; Codex biedt `$sessiestart` en `$sessielog` plus
  `/prompts:*`-compatibiliteit. De semantische `/sessielog`-workflow roept één
  deterministische helper aan voor indexen, sweep-launch en meldingen.
- **Niet-destructieve upgrade.** Setup herkent oude scriptnamen, verwijdert
  alleen verouderde KennisBank start/exit-entries, dedupliceert coördinatoren
  en bewaart andere hooks plus prompt/presearch.

### Nieuw in v0.15
- **Meertalige temporele recall.** `/watdeedik`, `/timeline`, en `/weeklog`
  begrijpen nu kant-en-klaar data en periodes in **Nederlands, Engels, Duits,
  Frans, Spaans, en Italiaans** (`vorige week`, `letzte Woche`,
  `la semaine dernière`, `la semana pasada`, `begin april`, `vor zwei Wochen`),
  met exacte kalenderbereiken. Een optionele `dateparser`-fallback breidt de
  dekking uit naar 200+ talen, en een standaard-uitgeschakeld lokaal-LLM-laatste
  redmiddel handelt samengestelde formuleringen af zoals "het weekend voor
  afgelopen maandag".
- **Rijkere relatieve formuleringen.** Relatieve weekdagen, weekdelen
  (`begin/midden/eind vorige week`), weekenden, "N eenheden geleden" in beide
  woordvolgorden, en maandnamen met jaar-inferentie worden allemaal
  deterministisch opgelost. 138 vastgepinde testcases bewaken het gedrag.

### Nieuw in v0.14
- **Lokale LiteParse-documentintake.** `/intake` en `/import documents <path>`
  parsen PDF's, Office-bestanden, spreadsheets, presentaties, en documentachtige
  afbeeldingen tot citeerbare markdown onder `<vault>/05-bronnen/liteparse/`.
- **Bronmateriaal blijft gescheiden.** Geparste binaire documenten worden
  `type: bron`-markdown met frontmatter die terugwijst naar het oorspronkelijke
  lokale bestand, zodat wiki-artikelen ze kunnen citeren met expliciete
  `[[05-bronnen/...]]`-links in plaats van te doen alsof het sessie-logs waren.
- **OCR is expliciet.** Documenten met native tekst parsen standaard zonder OCR;
  gebruik `--ocr` alleen voor scans en alleen wanneer lokale Tesseract/tessdata
  beschikbaar is.

### Nieuw in v0.13
- **Temporele activiteit-recall.** Vraag wat er gebeurde op een datum, tijdens
  een week, of rond een onderwerp met `/watdeedik`, `/timeline`, en `/weeklog`.
  De functie bouwt een lokale `<vault>/.claude/kb-activity.db` op uit ruwe
  sessies, transcripts, herinneringen, wiki-updates, en gebruikstelemetrie.
- **Strikte tijdsbewuste retrieval.** Data en periodes worden deterministisch
  geparst in het Nederlands en Engels (`vorige week`, `2026-07-03`, `3 juli 2026`,
  `between 2026-07-01 and 2026-07-07`). Bereikfiltering is hard: gebeurtenissen
  buiten de gevraagde periode worden er niet stilletjes doorheen gemengd.
- **Onderwerptijdlijnen met bewijs.** Volg onderwerpen zoals "Codex MCP" of
  "OpenRouter" door de tijd heen met behulp van entiteiten, tags, aliassen, FTS
  en bronverwijzingen. Lokale aliassen kunnen worden geconfigureerd in
  `<vault>/.claude/activity-topic-aliases.json`.
- **MCP temporele tools.** De lokale `kennisbank` MCP-server stelt nu
  `what_did_i_do`, `timeline`, `weeklog`, en `topic_timeline` beschikbaar naast
  `recall` en `capture`, zodat Codex, OpenCode en andere lokale agents dezelfde
  API gebruiken als de slash-commando's.
- **Gemeten recall.** `kb-activity-eval.py` biedt een temporeel eval-harnas voor
  datumrecall, perioderecall, onderwerptijdlijnen, negatieve controles en
  herkomstdekking. De repo levert een niet-persoonlijke voorbeeld-evalset mee.

### Nieuw in v0.12
- **Eén setup voor installatie en upgrade.** `setup.sh` is nu het gezaghebbende
  pad voor eerste installatie, reparatie, en upgrade: het ververst tooling,
  behoudt gebruikersdata, voert migraties uit, installeert geselecteerde
  agent-integraties, en blokkeert voltooiing wanneer validatie faalt.
- **Multi-agent van opzet.** Kies `claude`, `codex`, `opencode`, of `all`.
  Claude Code krijgt native commando's en hooks; Codex krijgt gedeelde skills,
  `/prompts:*`-aliassen, hooks, MCP, en `AGENTS.md`; OpenCode krijgt commando's,
  gedeelde skills, MCP, globale regels, en een lokale plugin.
- **Geverifieerde local-first modellen.** Setup valideert de geselecteerde
  backend voordat het terugkeert. Ollama blijft de standaard voor lokale
  geheugen-extractie en -beoordeling, inclusief smoke-tests voor de
  geconfigureerde embedding- en chatmodellen.
- **OpenRouter als expliciete cloud-opt-in.** Als je een externe LLM wilt voor de
  beoordelings-/extractiestap, kan setup OpenRouter configureren met een
  model-slug en API-sleutel-omgevingsvariabele. Secrets worden nooit
  weggeschreven naar de repo of kluis.
- **Agent-vriendelijk operationeel contract.** `AGENTS.md`, `CONFIGURATION.md`, en
  de agent-integratiedocumentatie beschrijven nu het actieve kluispad,
  setup-validatie, Codex/OpenCode-gedrag, hooks, MCP, en privacygrenzen.
- **v0.12.1 Codex-hotfix.** Setup opnieuw draaien repareert nu het Codex MCP
  TOML-blok zonder `[mcp_servers.kennisbank.env]` te dupliceren, en validatie
  vangt misvormde Codex-TOML op voordat setup succes meldt.
- **v0.12.2 MCP-runtime-hotfix.** Setup installeert nu de Python MCP SDK voor
  Codex/OpenCode-targets en valideert de stdio-server met een echte
  initialize/list-tools-handshake, zodat een geconfigureerde `kennisbank`
  MCP-server niet langer pas faalt wanneer de agent start.

### Kennis (de wiki-laag)
- `/wiki` compileert ruwe sessie-logs tot onderling gelinkte wiki-artikelen, en werkt bestaande artikelen bij via een bewaakte herschrijf-engine (`safe-edit.py`) in plaats van ze te overschrijven.
- **Provenance-lint** (`kb-lint.py`): elk artikel moet herleidbaar zijn naar zijn bronnen via oplosbare wikilinks naar een ruwe sessie of een geïmporteerde bron; `/wiki` schrijft die herkomst per kernpunt weg op destillatietijd. Een hallucinatie tijdens destillatie kan niet langer een permanent "feit" worden dat niemand kan controleren.
- `/stale` vindt verouderde artikelen, en gebruikstelemetrie houdt warme artikelen uit de lijst: een artikel dat je vorige week gebruikte is niet stale, hoe oud de `updated`-datum ook is.
- Denkgereedschap: `/reconcile` brengt tegenstrijdigheden tussen artikelen naar boven, `/uitdaag` daagt een stelling adversarieel uit, `/brug` vindt conceptuele bruggen tussen twee onderwerpen.

### Geheugen (de agent-laag)
- Een autonome **capture-sweep** draait losgekoppeld op de achtergrond (gestart bij sessiestart, over transcripts die bij sessie-einde zijn gearchiveerd): kandidaten extraheren, ze typeren (`feit`, `voorkeur`, `procedure`, `beslissing`), dedupliceren, en een onafhankelijke beoordelaar laten beslissen tussen `current` en quarantaine (`unverified`) met een belangscore (1-5).
- **Bi-temporele geldigheid**: elke herinnering draagt `valid_from` (gebeurtenistijd, van de sessiedatum) los van `created` (vastlegtijd); het vervangen of laten verlopen van een feit stempelt `valid_until`. Het systeem weet niet alleen wat waar is, maar ook sinds wanneer en tot wanneer.
- **Invalidatie op schrijftijd** (Mem0-patroon, lokaal): een nieuw feit verzoent zich met de meest gelijkende bestaande herinneringen op schrijftijd: ADD, SUPERSEDE (het oude feit wordt afgesloten en gelinkt), of NOOP. Een deterministische temporele bewaker zorgt dat een ouder feit nooit een nieuwer feit kan invalideren, zodat bulk-herimports veilig zijn.
- Onderhoud over herinneringen heen: supersede-pass, ruis-hercontrole, en clusterpromotie (terugkerende thema's worden gemarkeerd als wiki-kandidaten).

### Retrieval (de hooks-laag)
- **Elke prompt, elk project**: een UserPromptSubmit-hook embedt je prompt en injecteert de best-matchende wiki-artikelen en herinneringen als context. Een PreToolUse-hook controleert de kluis voordat Claude het web doorzoekt.
- Hybride index (`kb-index.db`): semantische vectoren (sqlite-vec) gefuseerd met FTS5-trefwoordzoeken, zodat exacte termen worden gevonden zelfs wanneer embeddings ze missen.
- Rangschikking: relevantie x recentheid (halveringstijd per geheugentype) x belang, plus een gebruiksboost voor documenten die recent nuttig bleken.
- **Graaf-buur-uitbreiding**: de meest-gerefereerde wikilink-buur van je treffers lift mee als één extra vermelding, wat losse treffers omzet in een samenhangende kennisbuurt.

### Meting (de vertrouwenslaag)
- `kb-eval.py`: recall@1/3/5 en MRR tegen je persoonlijke evalset van vragen. Draai het vóór en na elke retrieval-wijziging; een daling is een regressie, geen mening.
- `kb-activity-eval.py`: temporele recall-evals voor datumvragen, periodevragen, onderwerptijdlijnen, negatieve controles en bronverwijzingsdekking.
- `kb-calibrate.py`: controleert alle cosinus-drempels (dedup, rewrite, reconcile, conflict, retrieve) tegen het actieve embedding-model met behulp van een handmatig gelabelde paren-set, en stelt grenzen voor met scheidingsmarges. Het schrijft niets weg: jij beslist. Wissel van embedding-model zonder stilletjes te degraderen.
- `doctor.sh`: één commando verifieert de hele installatie, van kluisindeling en hook-registratie tot herkomstdekking.

### Soevereiniteit (waar het om draait)
- Lokale Ollama-modellen voor zowel embeddings als beoordeling, verwisselbaar via config (`kennisbank-embed.json`, `kennisbank-llm.json`); OpenAI-compatibele endpoints ondersteund wanneer je daarvoor kiest.
- LiteParse 2.x voor lokaal parsen van PDF-/Office-/afbeeldingsdocumenten tijdens intake.
- Alles is markdown + SQLite in een map die jij bezit. Obsidian-compatibel. MIT-gelicentieerd.
- Menselijke updateautoriteit: agents verwijderen nooit stilletjes; vervangen kennis wordt afgesloten en gelinkt, in quarantaine geplaatste kennis kan geverifieerde kennis niet verdringen, en grote herschrijvingen vereisen jouw bevestiging.

## Vereisten

- Minimaal één lokale agent-client: [Claude Code](https://claude.ai/code), Codex, OpenCode, of de [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)
- Python 3.10+
- [Ollama](https://ollama.com) met:
  - `qwen3-embedding:4b` (embeddings; meertalige standaard. Kluizen met alleen Engels kunnen het lichtere `nomic-embed-text` gebruiken)
  - een chatmodel voor de geheugenbeoordeling/-extractie (standaard `qwen3.5:4b`; pin een ander via `<vault>/.claude/kennisbank-llm.json`, maar houd het klein genoeg om naast het embeddingmodel te passen)

Ollama is optioneel in de zin dat alles fail-open werkt zonder, maar de geheugen-sweep, semantische retrieval, en deduplicatie zijn het hart van het systeem: installeer het. Alleen voor de **LLM-beoordeling/-extractie** kan setup ook OpenRouter configureren als expliciete cloud-opt-in. Embeddings blijven standaard lokaal.

De setup maakt standaard twee hoofdmappen aan:
- `~/KennisBank/` - de kluis (wiki, logs, geheugen, templates, scripts)
- `~/Claude/research/` - uitvoermap voor `/autoresearch`

Beide paden zijn configureerbaar. Voor een niet-standaard kluis stel je `KENNISBANK_VAULT` in bij het draaien van setup; diezelfde waarde wordt in agent-hooks en MCP-config geschreven zodat clients niet terugvallen op `~/KennisBank`.

## Installatie

```bash
git clone https://github.com/Jvdbreemen/LLmWiki-KennisBank.git
cd LLmWiki-KennisBank
bash setup.sh           # interactive
bash setup.sh --yes     # non-interactive (recommended for AI agents)
KENNISBANK_VAULT="/absolute/path/to/vault" bash setup.sh --yes --agents claude,codex,opencode
```

In één idempotente run doet het setup-script:
- maakt de kluis-mappenstructuur aan onder `$KENNISBANK_VAULT` of `~/KennisBank/`
- kopieert scripts en templates op hun plaats
- initialiseert de settings-toggles en voert versie-gebonden migraties uit
- vraagt welke agent-omgevingen geïnstalleerd moeten worden (`claude`, `codex`, `opencode`, of `all`; standaard `claude,codex`)
- installeert Claude Code-commando's/skills/hooks wanneer `claude` is geselecteerd
- installeert Codex-commandskills, `/prompts:*`-compatibiliteitsaliassen,
  MCP-config en globale `AGENTS.md`; upgrades verwijderen oude KennisBank-hooks
- installeert OpenCode-commando's, gedeelde skills, MCP-config, globale `AGENTS.md`, en een lokale plugin-hook wanneer `opencode` is geselecteerd
- installeert Copilot-commandskills, MCP-config, persoonlijke instructies en
  een aangepast agentprofiel; upgrades verwijderen oude KennisBank-hooks
- vraagt om de LLM-backend in interactieve modus: standaard `ollama`, optioneel `openrouter` met model-slug en API-sleutel-omgevingsvariabele
- valideert de installatie voordat het terugkeert: `doctor.sh`, agent-config-controles, MCP-runtime-handshake voor Codex/OpenCode, lokale Ollama-smoke-tests, en OpenRouter-smoke-tests wanneer OpenRouter is geselecteerd

**`setup.sh` opnieuw draaien is veilig en is het upgrade-mechanisme**: het ververst tooling en repareert agent-config zonder gebruikersdata, aanpassingen, of kluisinhoud te overschrijven. De `/kennisbank-upgrade`-skill omhult het met release-tag-checkout, drift-detectie, back-ups, versie-stempeling, en dezelfde post-installatie-validatie.

Nuttige vlaggen:

```bash
bash setup.sh --yes --agents claude,codex      # default non-interactive target set
bash setup.sh --yes --agents all               # Claude Code + Codex + OpenCode + Copilot
bash setup.sh --yes --agents codex             # Codex only
bash setup.sh --yes --skip-model-check         # CI/offline validation without Ollama smoke tests
bash setup.sh --yes --skip-doctor              # skip the closing doctor gate (tests/CI that run doctor.sh themselves)
```

Voor OpenRouter schrijft setup alleen niet-geheime config naar
`<vault>/.claude/kennisbank-llm.json`: provider, model, endpoint, en
`api_key_env`. De API-sleutel zelf moet in de genoemde omgevingsvariabele staan
of, als je hem tijdens setup invoert, in het gebruikers-lokale secrets-bestand
`~/.config/kennisbank/secrets.json`. Hij wordt nooit weggeschreven naar de repo
of kluis.

Lees na installatie [POST-INSTALL.md](POST-INSTALL.md) voor de eerste-sessie-walkthrough.

### De hookset

Claude Code, Codex en Copilot krijgen elk één SessionStart-coördinator en één
exit-coördinator plus hun prompt/tool-hooks. De tabel noemt coordinator-children
als jobs, niet als los geregistreerde handlers. OpenCode gebruikt MCP plus een
globale plugin onder `~/.config/opencode/plugins/`.

| Hook | Script | Wat het doet |
|------|--------|--------------|
| SessionStart | `kb-session-start.py` | Coördineer parallelle index-/sweep-jobs, daarna meldingen; emit één actierapport |
| Coordinator-job | `build-embed-index.py`, `build-kb-index.py`, `build-activity-index.py`, `sweep-launch.py` | Draai onafhankelijk onderhoud parallel |
| Coordinator-melding | `memory-notify.py`, `distill-notify.py` | Rapporteer health/acties na onderhoud |
| UserPromptSubmit | `kb-retrieve.py` | Injecteer matchende wiki- + geheugencontext in de prompt |
| SessionEnd/Stop | `kb-session-end.py` | Leg transcript/event eerst vast; ken daarna gebruik toe en importeer Copilot-activiteit parallel |
| Exit-coördinator capture | `archive-transcript.py` of `kb-copilot-capture.py` | Bewaar de client-native sessiebron vóór vervolgwerk |
| Exit-coördinator jobs | `kb-usage-scan.py`, Copilot `import-copilot.py` | Ken nuttige recall toe en maak Copilot-activiteit direct indexeerbaar |
| PreToolUse (WebSearch\|WebFetch) | `kb-presearch.py` | Raadpleeg de kluis voordat je het web doorzoekt |

De hooks zijn fail-open van opzet: een fout betekent geen geïnjecteerde context of een overgeslagen achtergrondstap, nooit een geblokkeerde sessie.

## Commando-overzicht

| Commando | Argumenten | Wat het doet |
|---------|-----------|--------------|
| `/sessielog` | geen | Schrijft en cureert het semantische sessielog en draait daarna één mechanische coördinator |
| `/sessiestart` | geen | Leest kluiscontext, geheugen, wiki-status, stelt volgende acties voor |
| `/wiki` | optioneel onderwerp | Compileert ruwe logs (laatste 7 dagen) tot wiki-artikelen met herkomst per kernpunt, gevalideerd door kb-lint |
| `/intake` | geen | Verwerkt bestanden in `~/KennisBank/00-inbox/`, inclusief lokale LiteParse-conversie van PDF-/Office-/afbeeldingsdocumenten naar bron-markdown |
| `/stale` | geen | Detecteert artikelen ouder dan 60 dagen, en slaat recent gebruikte over |
| `/import` | `cc` \| `claudeai <path>` \| `folder <path> [prefix]` \| `documents <path> [prefix]` \| `cowork` \| `all` | Bulk-import van oude sessies uit Claude Code-geschiedenis, een claude.ai-exportbundel, een willekeurige markdown-map, documentbronnen via LiteParse, of Mac desktop Claude-data; `all` draait elke gedetecteerde bron, geen argument vraagt interactief |
| `/destilleer` | geen | Importeert gearchiveerde CC-transcripts en compileert ze tot de wiki |
| `/autoresearch` | onderwerp | Multi-ronde webresearch via de autoresearch-skill (geen commandobestand), slaat op in `~/Claude/research/` |
| `/reconcile` | optioneel onderwerp | Brengt tegenstrijdigheden tussen wiki-artikelen naar boven en produceert een reconciliatie-log |
| `/uitdaag` | stelling of beslissing | Daagt een stelling adversarieel uit op zwakke redenering of ontbrekend bewijs |
| `/brug` | twee onderwerpen | Vindt conceptuele bruggen en gedeelde principes tussen twee onderwerpen |
| `/weeklog` | optionele periode/onderwerp | Wekelijkse activiteitensamenvatting met beslissingen, releases/taken, open eindjes en bronverwijzingen |
| `/timeline` | datum/periode/onderwerp | Chronologische temporele activiteitentijdlijn met strikte bereikfiltering |
| `/watdeedik` | datum/periode/onderwerp | Compact antwoord op "wat deed ik toen?" met bewijslinks |
| `/kennisbank:settings` | geen | Toont en schakelt de achtergrond-automatiek-toggles |
| `/kennisbank:review` | optioneel onderwerp | Loop de unverified-memory-wachtrij door; de mens beslist approve/reject/skip per item |
| `/kennisbank:rebuild-index` | geen | Herbouwt de hybride zoekindex uit de kluis-markdown |
| `/kennisbank:rebuild-memory` | geen | Her-extraheert ALLE geheugen uit gearchiveerde transcripts (zwaar; semantische dedup maakt het bijna-idempotent) |
| `/kennisbank-upgrade` | optioneel `--dry-run` | Upgradet de gedeployde kluis naar de nieuwste release-tag |
| `/kennisbank-contribute` | optioneel `--dry-run` | PR't lokale tooling-wijzigingen terug upstream |

## Skills

Drie skills worden met het systeem meegeleverd. Claude Code krijgt ze onder `~/.claude/skills/`; Codex en OpenCode krijgen ze onder de gedeelde gebruikers-skill-locatie `~/.agents/skills/`, die beide clients ontdekken. Commando's zijn enkele prompts; skills zijn meerstaps-procedures met hun eigen guardrails.

| Skill | Aangeroepen via | Wat het doet |
|-------|-------------|--------------|
| `autoresearch` | `/autoresearch <topic>` of "research/deep dive/onderzoek [topic]" | Autonome iteratieve research-loop: multi-ronde webzoekopdrachten, synthese, en één gestructureerd document met bronvermelding in `~/Claude/research/`. Controleert eerst je eigen kluis (luie hiërarchie) zodat research gaten vult in plaats van te herhalen wat je al weet. Gebouwd op Karpathy's autoresearch-patroon. |
| `kennisbank-upgrade` | `/kennisbank-upgrade [--dry-run]` | Upgradet een gedeployde kluis naar de nieuwste officiële release-tag (nooit kale main): haalt tags op, toont de changelog-delta, detecteert lokale drift met een CRLF-agnostische diff, maakt back-ups van gedrifte categorieën, deployt via `setup.sh`, stempelt de geïnstalleerde versie, en verifieert met `doctor.sh`. |
| `kennisbank-contribute` | `/kennisbank-contribute [--dry-run]` | De omgekeerde richting: isoleert lokale tooling-wijzigingen in een gedeployde kluis (scripts, templates, commando's, skills), filtert persoonlijke kluisinhoud eruit, en maakt dan een branch, commit, push, en opent een upstream-PR. Eigenaarschap staat gelijk aan duurzaamheid: verbeteringen overleven de volgende upgrade omdat ze upstream terechtkomen. |

Upgrade en contribute zijn twee helften van één lus: `contribute` stuurt je lokale verbeteringen upstream, `upgrade` brengt uitgebrachte verbeteringen weer terug. Een kluis die beide volgt, drift nooit permanent weg van het project.

## Kluisstructuur

```
~/KennisBank/
  00-inbox/        Drop files here for processing
  01-raw/
    sessies/       Session logs (raw-sessie-YYYY-MM-DD-topic.md)
    transcripts/   Archived Claude Code transcripts (SessionEnd hook)
  02-wiki/         Compiled wiki articles
  03-projecten/    Project-specific notes
  04-templates/    Article and log templates
  05-bronnen/      Source materials and references
  06-claude/       Claude-internal context files, eval + calibration sets
  07-media/        Media descriptions and asset metadata (not the binaries)
  08-archive/      Archived articles
  09-memory/       Agent memory (typed, judged, bi-temporal; archive/ for retired items)
  .claude/
    scripts/       Python + shell tooling (incl. doctor.sh)
    kb-index.db    Hybrid vector + FTS index (refreshed incrementally each session)
    kb-usage.db    Usage telemetry (survives rebuilds and model switches)
  graphify-out/    Knowledge graph output (optional)
```

## Achtergrond-automatiek-toggles

Elf achtergrondgedragingen zijn individuele toggles in `kennisbank-settings.json`, beheerd met `/kennisbank:settings`:

| Toggle | Standaard | Regelt |
|--------|---------|----------|
| `auto_archive` | uit | Archiveer het transcript bij sessie-einde |
| `distill_notify` | aan | Meld bij start dat transcripts in behandeling zijn |
| `embed_index` | aan | Ververs de wiki-embedding-cache bij start |
| `daily_graphify` | aan | Werk de kennisgraaf eens per dag bij |
| `memory_capture` | aan | Extraheer en beoordeel herinneringen naar `09-memory/` |
| `memory_recall` | aan | Injecteer herinneringen in context via hooks |
| `usage_telemetry` | aan | Volg welke geïnjecteerde kennis wordt gebruikt |
| `activity_llm_fallback` | uit | Lokale-LLM-terugval voor exotische datumformuleringen in temporele recall |
| `checkpoints` | uit | Schrijf bij context-compaction (PreCompact) automatisch een werkstand-stub |
| `orientation` | uit | Injecteer een compacte vault-oriëntatie bij sessiestart |
| `graph_retrieval` | aan | Haal de buur-expansie uit de gewogen graafindex (A/B-bewezen, TASK-87) |

## Je retrieval meten

Twee harnassen houden het systeem eerlijk:

```bash
# recall@k against your personal eval set (06-claude/kb-eval-set.json)
python3 ~/KennisBank/.claude/scripts/kb-eval.py

# threshold calibration against the active embedding model
python3 ~/KennisBank/.claude/scripts/kb-calibrate.py
```

Onderhoud de evalset naarmate je kluis groeit (vragen waarvan je het antwoord kent, met het verwachte artikel), en draai beide harnassen na elke wijziging aan drempels, modellen, of rangschikking. Voorbeeldsets worden meegeleverd in de repo-root.

## Migreren vanaf oudere Claude-tooling

Het `/import`-commando vult de kluis aan vanuit bestaande Claude-geschiedenis. Het verwerkt Claude Code-sessie-JSONL-bestanden onder `~/.claude/projects/`, claude.ai-exportbundels, Mac desktop Claude (Cowork)-gespreksdata, en elke generieke markdown- of tekstmap. Elke importer schrijft ruwe sessiebestanden die `/wiki` daarna kan compileren. Voor de geheugenlaag her-extraheert `/kennisbank:rebuild-memory` alle gearchiveerde transcripts via de volledige sweep (semantische dedup maakt herruns bijna-idempotent).

Voor binaire/bron-documenten gebruiken `/intake` en `/import documents <path>`
LiteParse 2.x lokaal om PDF's, Office-bestanden, spreadsheets, presentaties,
en documentachtige afbeeldingen om te zetten naar markdown onder
`05-bronnen/liteparse/`. Dit roept geen cloud-parser of LLM aan. OCR is opt-in
(`--ocr`) zodat PDF's met native tekst niet vervuild raken door diagnostiek over
ontbrekende Tesseract/tessdata; Office-/afbeeldingsformaten kunnen nog steeds
lokale LibreOffice-/ImageMagick-tooling vereisen, zoals LiteParse rapporteert.

## KennisBank gebruiken vanuit andere agents (Codex, OpenCode, Copilot, ChatGPT)

De kluis is niet alleen voor Claude Code. `scripts/kb-mcp.py` is een lokale **MCP-server** die negen primitieven blootstelt: acht tools - `recall` (zoek geheugen + wiki), `capture` (sla een nieuwe herinnering op), `review_pending` en `review_decide` (de menselijke reviewwachtrij), en de temporele set `what_did_i_do`, `timeline`, `weeklog`, `topic_timeline` - plus een `instructions`-resource (een duwtje om te trekken vóór je extern zoekt). MCP is het ene protocol dat elke moderne agent al spreekt, dus elke client die **op deze machine** draait kan de kluis gebruiken.

Elke tool draagt MCP-annotaties, en dat is niet cosmetisch: een client leidt uit `readOnlyHint` af of een aanroep bevestiging nodig heeft en of hij parallel mag draaien, en zet beide op "nee" als de hint ontbreekt. De zes read-only retrieval-tools zijn als zodanig gemarkeerd; `capture` is een niet-destructieve schrijver, `review_decide` een destructieve. Het pull-duwtje reist via drie dragers, omdat geen enkele op zichzelf elke client bereikt: het `instructions`-veld van de protocol-handshake, de `kennisbank://instructions`-resource, en de managed block in `.github/copilot-instructions.md`.

**De harde grens: alleen lokaal.** De MCP-server bindt niets aan het netwerk
(stdio-transport); de kluis verlaat nooit je machine. Claude Code, Codex,
GitHub Copilot CLI, OpenCode en compatibele lokale stdio-clients bereiken hem
direct. Agents die *in de cloud* draaien (gehoste ChatGPT) kunnen geen lokale
stdio-server bereiken, en het antwoord is **niet** om je soevereine kluis naar
het internet te tunnelen - het is de handmatige brug hieronder.

### Codex CLI

`setup.sh --agents codex` installeert:

- `~/.agents/skills/<commando>/SKILL.md`, inclusief `sessiestart`, `sessielog`,
  temporele commando's en de handgeschreven KennisBank-skills
- `~/.codex/prompts/*.md`-aliassen, aangeroepen als `/prompts:sessielog`, `/prompts:sessiestart`, `/prompts:kennisbank-upgrade`, enz.
- `~/.codex/AGENTS.md` met het actieve kluispad
- `~/.codex/hooks.json` met één SessionStart- en één exit-coördinator plus
  fail-open prompt/tool-hooks
- `~/.codex/config.toml` MCP-server `kennisbank`

Gebruik `$sessiestart` en `$sessielog` als native Codex-skills. Codex biedt geen
willekeurige kale slash-aliassen; de verouderde promptcompatibiliteit is
`/prompts:<name>`. KennisBank installeert geen Codex lifecycle-hooks omdat
Codex `suppressOutput` wel parseert maar nog niet uitvoert. Setup verwijdert
oude KennisBank-hookentries en bewaart overige hooks. MCP blijft beschikbaar.

Handmatig MCP-equivalent:

```bash
py -3 -m pip install mcp==1.28.1
```


```toml
[mcp_servers.kennisbank]
command = "py"
args = ["-3", "/absolute/path/to/vault/.claude/scripts/kb-mcp.py"]

[mcp_servers.kennisbank.env]
KENNISBANK_VAULT = "/absolute/path/to/vault"
KB_LLM_PROVIDERS = "ollama"
KB_LLM_MODEL = "qwen3.5:4b"
KB_LLM_ENDPOINT = "http://localhost:11434"
```

### OpenCode

`setup.sh --agents opencode` installeert:

- `~/.config/opencode/commands/*.md`, aangeroepen als `/sessielog`, `/sessiestart`, `/kennisbank-upgrade`, enz.
- `~/.agents/skills/{autoresearch,kennisbank-upgrade,kennisbank-contribute}/`
- `~/.config/opencode/AGENTS.md` met het actieve kluispad
- `~/.config/opencode/opencode.json` MCP-server `kennisbank`
- `~/.config/opencode/plugins/kennisbank.js`, een fail-open lokale plugin voor sessie-onderhoudsevents

OpenCode leest globale commando's rechtstreeks uit `~/.config/opencode/commands/`, dus de commandonamen komen overeen met de Claude Code-namen. Retrieval moet de MCP-tool `recall` en de geïnstalleerde skills gebruiken; de plugin handelt achtergrondonderhoud af waar OpenCode overeenkomende events blootstelt.

### GitHub Copilot CLI - een eersteklas lokale agent

De **standalone** GitHub Copilot CLI (`npm install -g @github/copilot`, aangeroepen als `copilot`) is een beheerde KennisBank-target, precies zoals Codex en OpenCode - geen handgeschreven snippet. Eén lokale kluis, één stdio MCP-server, één lokale recall-laag, nu gedeeld over alle vier de agents. Wat je ook doet in een Copilot-sessie wordt doorzoekbare KennisBank-geschiedenis naast je Claude Code-, Codex-, en OpenCode-werk; vraag `/watdeedik` of `/timeline` en Copilots sessies verschijnen naast de rest.

```bash
KENNISBANK_VAULT="/absolute/path/to/vault" bash setup.sh --yes --agents copilot
```

`setup.sh --agents copilot` installeert, idempotent en zonder login:

- `~/.copilot/mcp-config.json` - MCP-server `kennisbank` (`recall`, `capture`, en de temporele tools), geregistreerd via een key-scoped JSON-merge en gevalideerd met een echte initialize/list-tools-handshake
- `~/.copilot/hooks/kennisbank.json` - één cross-platform start- en
  exit-coördinator plus fail-open prompt/tool-capture-hooks
- `~/.copilot/copilot-instructions.md` - een door KennisBank beheerd instructieblok
- `~/.copilot/agents/kennisbank.agent.md` - een aangepast agent-profiel, geselecteerd met `copilot --agent kennisbank`
- native slash-commandskills onder `~/.agents/skills/`, inclusief
  `/sessiestart`, `/sessielog`, `/weeklog` en `/timeline`

KennisBank coördineert startup achter één hook, omdat Copilot geen hookveld
biedt om zijn eigen tijdlijnregels te verbergen. Eén generieke regel kan
blijven; zes tot acht oude regels worden één. Bij upgrade verwijdert setup
alleen bekende oude SessionStart-commando's.

Draai Copilot via de wrapper om de kluis en local-LLM-env vast te pinnen: `python3 <vault>/.claude/scripts/kennisbank-copilot.py` (een triviale exec die het overdraagt aan de echte `copilot`; `--kb-doctor`, `--kb-dry-run`, en `--kb-print-env` werken zonder GitHub-login).

**De cloud-grens is precies.** Copilot is cloud-gebaseerd; een live modelbeurt
vereist een abonnement en stuurt verzoeken naar GitHub. Je kluis, recall,
MCP-server, skills en instructies blijven lokaal. Zie de
[integratiedocumentatie](docs/agent-integrations.md) en de
[SessionStart-coördinator-ADR](docs/adr/ADR-006-coordinate-sessionstart-work-behind-one-client-hook.md)
en de [sessielog/exit-coördinator-ADR](docs/adr/ADR-007-coordinate-session-logging-and-exit-work-behind-one-client-hook.md).

### GitHub Copilot (VS Code agent-modus) - werkt, met één kanttekening

Dit is Copilots **VS Code agent-modus** (MCP-tools binnen de editor) - een andere, handmatige integratie dan de standalone GitHub Copilot CLI die hierboven behandeld is. Copilots agent-modus ondersteunt MCP-**tools** over stdio, maar **geen** MCP-resources of -prompts. Dus `recall` en `capture` werken, maar het `instructions`-duwtje (een resource) komt niet naar boven. Zet het duwtje in plaats daarvan in `.github/copilot-instructions.md`:

```markdown
You have a local KennisBank via MCP tools `recall` and `capture`.
Call `recall` before searching externally; call `capture` to save a reusable fact.
```

Registreer de server in de VS Code-instellingen (`mcp.json` / `"servers"`):

```json
{
  "servers": {
    "kennisbank": {
      "command": "python3",
      "args": ["/absolute/path/to/vault/.claude/scripts/kb-mcp.py"]
    }
  }
}
```

Het bredere adapter-register en de rest van de client-snippets staan in
[docs/agent-integrations.md](docs/agent-integrations.md).

### ChatGPT - de handmatige brug (soevereiniteit eerst)

Gehoste ChatGPT kan alleen verbinden met **remote** MCP-servers op het publieke internet; een lokale server blootstellen betekent tunnelen (Secure Tunnel / ngrok / Cloudflare), wat je queries **en** de teruggegeven kennis via OpenAI's infrastructuur leidt. Dat breekt het hele punt van een soevereine kluis, dus KennisBank doet dit standaard niet. In plaats daarvan blijf **jij** de poort:

```bash
python3 .claude/scripts/kb-ask.py "how did I fix the ESP32 BLE crash"
python3 .claude/scripts/kb-ask.py "my topic" --k 8 --clip   # also copy to clipboard
```

`kb-ask` haalt lokaal op en print een kant-en-klaar te plakken contextblok (een korte instructie voor het model, dan de treffers, dan je vraag). Plak het bovenaan je ChatGPT-bericht. Niets verlaat de machine automatisch - jij kiest wat je deelt.

### ChatGPT-data-export - krijg de controle over je eigen chats terug

Je kunt je ChatGPT-geschiedenis *in* de soevereine kluis trekken, zodat lessen uit die gesprekken je eigen ophaalbare kennis worden in plaats van alleen in OpenAI's cloud te leven:

1. Open in ChatGPT **Settings → Data controls → Export data** en bevestig. (Vereist dat je bent ingelogd op de webapp.)
2. OpenAI mailt je binnen enkele minuten tot een dag een downloadlink; de link is tijdgebonden. Download de ZIP - die bevat `conversations.json` (plus `chat.html`, media).
3. Importeer het in de kluis:
   ```bash
   python3 .claude/scripts/import-chatgpt-export.py --input ~/Downloads/chatgpt-export.zip
   # preview first if you like:
   python3 .claude/scripts/import-chatgpt-export.py --input ~/Downloads/chatgpt-export.zip --dry-run --verbose
   ```
   Elk gesprek wordt een ruwe sessie-log onder `01-raw/sessies/`. Draai daarna `/wiki` om ze tot artikelen te compileren en `/kennisbank:rebuild-memory` om de geheugenlaag te extraheren. Herimports worden standaard overgeslagen (idempotent); geef `--force` mee om te overschrijven.

De importer loopt door ChatGPT's bericht-*boom* (`mapping`), ordent beurten op tijdstempel, en houdt alleen jouw en de assistent-beurten - systeem- en tool-nodes worden weggelaten. Het draait volledig lokaal; er wordt niets ergens naartoe gestuurd.

## Documentatie

| Bestand | Voor |
|------|-----|
| [docs/guiding-principles-and-values.nl.md](docs/guiding-principles-and-values.nl.md) | De guiding principles en values, uitgewerkt als één document |
| [PRINCIPLES.nl.md](PRINCIPLES.nl.md) | De ontwerp-wetten die elke beslissing sturen (beknopte referentie) |
| [VALUES.nl.md](VALUES.nl.md) | Waar het project om geeft - het karakter (beknopte referentie) |
| [AGENTS.md](AGENTS.md) | AI-codeer-agents (Claude Code, Codex, GitHub Copilot CLI en OpenCode) die dit namens een gebruiker installeren |
| [POST-INSTALL.md](POST-INSTALL.md) | Eerste-sessie-walkthrough nadat `setup.sh` klaar is |
| [CONFIGURATION.md](CONFIGURATION.md) | Elke configureerbare knop: paden, drempels, modellen, toggles |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Symptoom / oorzaak / oplossing voor veelvoorkomende problemen |
| [OBSIDIAN.md](OBSIDIAN.md) | Open de kluis in Obsidian, aanbevolen gratis plugins |
| [CHANGELOG.md](CHANGELOG.md) | Release-geschiedenis, Keep a Changelog-formaat |
| [vault-structure/README.md](vault-structure/README.md) | Map-voor-map-referentie |

## Aanpassen

1. Bewerk `<vault>/CLAUDE.md` na setup. Vervang `[YOUR NAME]` en `[YOUR PROJECTS]` door je eigen. Voor een niet-standaard installatie is `<vault>` het exacte `KENNISBANK_VAULT`-pad dat je gebruikte.
2. **Kluispad.** Alle Python-scripts, `doctor.sh`, en gegenereerde agent-integraties respecteren de omgevingsvariabele `KENNISBANK_VAULT` (standaard `~/KennisBank`). Zie [CONFIGURATION.md](CONFIGURATION.md) sectie 9 voor het niet-standaard-kluiscontract.
3. **Embedding-backend.** Verwisselbaar via `<vault>/.claude/kennisbank-embed.json` of `KB_EMBED_*`-env-vars: standaard lokale Ollama, OpenAI-compatibele endpoints wanneer geconfigureerd. Van model wisselen invalideert de cache by design; draai daarna `kb-calibrate.py` om de drempels tegen het nieuwe model te controleren (het stelt waarden voor, jij stelt ze in).
4. **LLM-backend** (beoordeling/extractie): `<vault>/.claude/kennisbank-llm.json` of `KB_LLM_*`-env-vars. Standaard Ollama `qwen3.5:4b` (past naast het embeddingmodel op één GPU); optioneel OpenRouter gebruikt `https://openrouter.ai/api/v1/chat/completions` via het OpenAI-compatibele chat-schema.
5. **Wiki-categorieën.** `build-karpathy-index.py` groepeert artikelen met een ingebouwde taxonomie; overschrijf met een `categories.json` (kopieer [`categories.example.json`](categories.example.json)).
6. De commando's zijn standaard in het Nederlands (ze volgen de prompt-taal). Wijzig de sectiekoppen als je Engels prefereert.
7. Stale-drempel (standaard 60 dagen): geef `--days N` mee of bewerk `stale-check.py`.
8. `auto-crosslink.py`-instelbare waarden: `MIN_CONFIDENCE` (standaard `0.75`) en `MAX_NEW_LINKS` (standaard `5`).
9. Research-uitvoerpad: het wijzigen raakt meerdere plekken (`setup.sh`, de autoresearch-skill, en de commando-tekst) - zie [CONFIGURATION.md](CONFIGURATION.md) sectie 5.
10. Om de `/autoresearch`-trigger in te schakelen, voeg dit snippet toe aan je globale `~/.claude/CLAUDE.md`:
    ```
    # autoresearch
    - **autoresearch** (`~/.claude/skills/autoresearch/SKILL.md`) - multi-round research with lazy hierarchy check. Output to `~/Claude/research/`. Trigger: `/autoresearch`
    When the user types `/autoresearch`, invoke the Skill tool with `skill: "autoresearch"` before doing anything else.
    ```

## Optioneel: graphify-integratie

`auto-crosslink.py` leest uit `<vault>/graphify-out/graph.json`, geproduceerd door de graphify-skill wanneer die op de kluis wordt gedraaid. Zonder dit wordt de crosslink-stap stilletjes overgeslagen. Retrieval profiteert indirect: de graaf-buur-uitbreiding volgt de wikilinks die crosslinking onderhoudt.

## Optioneel: kennisgraaf-dashboard

[Understand-Anything](https://github.com/Lum1104/Understand-Anything) is een aparte Claude Code-plugin (MIT) die een wiki volgens het Karpathy-patroon omzet in een interactief kennisgraaf-dashboard. Bouw de vereiste index met `python3 scripts/build-karpathy-index.py`, en draai dan `/understand-knowledge` binnen `<vault>/02-wiki`. Zie `--help` voor vlaggen; categorieën zijn aanpasbaar via `categories.json`.

## Dankbetuigingen

- Patroon: [Andrej Karpathy's LLM Wiki-gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- Kluis-/CMS-inspiratie: [claude-obsidian door AgriciDaniel](https://github.com/AgriciDaniel/claude-obsidian)
- Geheugenarchitectuur-lessen: het publieke werk rond Mem0, Zep/Graphiti, Letta, en Cognee, hier local-first herbouwd

## Licentie

MIT. Zie [LICENSE](LICENSE).
