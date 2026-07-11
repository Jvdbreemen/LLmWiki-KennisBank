# KennisBank - Kernwaarden

[English](VALUES.md) · **Nederlands**

Waarden zijn geen regels. Ze zijn waar dit project *om geeft* - het karakter
achter de code. Waar `PRINCIPLES.md` zegt *hoe* KennisBank werkt, zegt dit
*waarom we de moeite nemen*. Wanneer de principes zwijgen of met elkaar botsen,
geven de waarden de doorslag.

De keten is eenvoudig: **waarden → principes → code.** Een ontwerpbeslissing die
de principes eert maar een waarde verraadt, is de verkeerde beslissing.

## De waarden

### Sovereignty
Jouw kennis is van jou. Lokaal als standaard, geen cloud zonder jouw toestemming,
geen lock-in, geen stille telemetrie. Onafhankelijkheid is het extra
engineeringwerk waard - het alternatief is toegang huren tot je eigen geheugen.

### Privacy
Wat je vastlegt blijft van jou en blijft binnen de perken. Geheimen worden
gemaskeerd voordat ze de schijf raken; niets bereikt een cloud-provider zonder
een expliciete waarschuwing vooraf en jouw opt-in; er is standaard geen
telemetrie. Een geheugenlaag die lekt is erger dan helemaal geen geheugenlaag.

### Honesty
Waarheid boven gemak, ook wanneer de waarheid ongelegen komt. Elke bewering is
terug te voeren op een bron; onzekerheid wordt gemarkeerd, niet weggepoetst; het
systeem verzint nooit iets om compleet te lijken. Een zelfverzekerd antwoord
zonder bron is een bug, geen feature.

### Transparency
Geen verborgen gedrag. Je kunt altijd zien wat KennisBank heeft vastgelegd,
geïnjecteerd of verstuurd - via gewone bestanden, gestructureerde status, en een
doctor die je de waarheid vertelt. Het systeem is een glazen doos, geen zwarte;
een tool die je niet kunt inspecteren, is een tool die je niet kunt vertrouwen.

### Traceability
Een volledig audit trail. Elk feit, elke recall, elke injectie is te herleiden
tot zijn oorsprong en zijn *waarom* - welke sessie, welke bron, welke score.
Herkomst is geen bijzaak die er achteraf op geschroefd wordt; het is hoe het
systeem vertrouwen verdient. Niets komt de kennisbank binnen dat niet naar huis
te volgen is.

### Care
Voor de mens, voor het werk, en voor de lange termijn. Code die de volgende
beheerder kan begrijpen en repareren. Een systeem dat je aandacht, je tijd en de
energie van je machine respecteert. Dit project is iets wat het beschermen en
koesteren waard is - geen probleem dat je mechanisch oplost en vervolgens laat
vallen.

### Clarity
Begrijpelijk wint van slim. We willen weten hoe dingen onder de motorkap werken
- tot aan de query, de index, de byte - en we bouwen zó dat de volgende persoon
dat ook kan. Slimme oplossingen zijn altijd bespreekbaar; helderheid is de
standaard waar we naar terugkeren.

### Respect for the human
Jij bent de hoofdredacteur. De tool stelt voor; jij beslist. Je focus is
kostbaar, en elke onderbreking moet haar plek verdienen. KennisBank doet het saaie
werk, zodat een mens de zeggenschap houdt over wat waar is.

### Helpfulness
Écht nuttig zijn is de hele bedoeling - een echte partner in het werk, geen
passieve tool die op instructies wacht. Nut wordt gemeten aan de vraag of jouw
echte werk makkelijker werd, niet aan hoeveel het systeem deed.

### Integrity
We zeggen wat waar is, ook als het ongelegen komt, brengen risico's naar voren
waar niet naar gevraagd is, en zijn het oneens wanneer het bewijs dat
ondersteunt. Nauwkeurigheid boven instemming, altijd. Vertrouwen bouw je op door
correct en eerlijk te zijn, niet door meegaand te zijn.

### Curiosity and joy
Gebouwd door iemand die dol is op begrijpen hoe dingen werken - van SID-chips en
copper bars tot embeddings en vector search. Elegante hacks worden gevierd, kennis
op laag niveau wordt gekoesterd, en het werk zelf hoort een plezier te zijn. Een
project dat met plezier gemaakt is, is doorgaans een project dat het gebruiken
waard is. (En ook: "mostly harmless".)

## Hoe waarden in de praktijk tot uiting komen

- **Sovereignty** → lokale SQLite/markdown, lokale Ollama, stdio MCP; cloud is opt-in.
- **Privacy** → maskeren van geheimen in hooks, een expliciete waarschuwingspoort vóór elke cloud-aanroep, geen standaard telemetrie.
- **Honesty** → herkomstlinks, `kb-lint`, quarantaine voor niet-geverifieerd geheugen.
- **Transparency** → `doctor.sh` PASS/WARN/FAIL, gestructureerde JSON-output, heldere status boven logruis.
- **Traceability** → `source_ref` op elk event, herkomst-wikilinks, de Recall Inspector die laat zien *waarom* iets naar boven kwam.
- **Care** → idempotent-veilige installers, fail-open hooks, back-ups vóór bewerkingen.
- **Clarity** → KISS, ADR's die het *waarom* uitleggen, één mechanisme boven drie.
- **Respect** → hoge relevantiedrempel voordat iets naar boven komt, geen stille verwijderingen.
- **Helpfulness** → sub-seconde recall, de juiste context op het juiste moment.
- **Integrity** → het systeem markeert wat het niet kan verifiëren in plaats van te gokken.
- **Curiosity/joy** → het project mag een beetje leuk zijn.

_Zie ook: `PRINCIPLES.md` (de ontwerpwetten die deze waarden voortbrengen),
`CLAUDE.md` (hoe KennisBank moet aanvoelen), en `docs/adr/` (de beslissingen die
ze tot leven brengen)._
