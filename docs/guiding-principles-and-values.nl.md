# KennisBank - Leidende principes en waarden

[English](guiding-principles-and-values.md) · **Nederlands**

Dit is het kompas voor KennisBank: waar het project om geeft (zijn **waarden**)
en de ontwerpwetten die die waarden voortbrengen (zijn **principes**), samen
uitgewerkt tot één document. Waar de beknopte referentielijsten in
[`VALUES.md`](../VALUES.nl.md) en [`PRINCIPLES.md`](../PRINCIPLES.nl.md) leven, is
dit de uitgewerkte versie - het *waarom*, het *hoe*, en de draad die ze verbindt.

De keten is bewust en één-richting:

> **waarden → principes → code.**

Waarden bepalen wat ertoe doet. Principes vertalen dat naar ontwerpwetten. Code
gehoorzaamt de principes. Als een beslissing onduidelijk is, loop dan de keten
terug omhoog: een wijziging die de principes eert maar een waarde verraadt, is de
verkeerde wijziging.

## De noord-ster: onzichtbaar, snel, uit de weg

Alles hieronder dient één beeld. KennisBank moet aanvoelen alsof het er niet is.
Zijn taak is jou te helpen met je echte werk - schrijven, coderen, denken -
zonder ooit zelf aandacht op te eisen. De beste versie van KennisBank is die je
vergeet dat hij draait, tot precies het moment waarop hij je exact de context
aanreikt die je nodig had.

## Deel 1 - De waarden (waar we om geven)

Waarden zijn geen regels; ze zijn het karakter achter de code. Ze clusteren in
een paar thema's.

### Jouw data, beschermd: Sovereignty en Privacy

**Sovereignty** - Jouw kennis is van jou. Lokaal by default, geen cloud zonder
jouw toestemming, geen lock-in, geen stille telemetrie. Onafhankelijkheid is het
extra engineeringwerk waard; het alternatief is toegang tot je eigen geheugen
huren.

**Privacy** - Wat je vastlegt blijft van jou *én* blijft besloten. Secrets worden
geredigeerd voordat ze de schijf raken; niets bereikt een cloudprovider zonder
een expliciete waarschuwing vooraf en jouw opt-in; er is geen telemetrie by
default. Een geheugenlaag die lekt is erger dan helemaal geen geheugenlaag.

### Het vertrouwenstrio: Honesty, Transparency, Traceability

Deze drie vormen een keten op zich - elk hangt af van de voorgaande.

**Honesty** - Waarheid boven gemak, ook wanneer de waarheid ongelegen komt. Het
systeem verzint nooit iets om compleet te lijken; onzekerheid wordt gemarkeerd,
niet gladgestreken. Een stellig antwoord zonder bron is een bug, geen feature.

**Transparency** - Geen verborgen gedrag. Je kunt altijd zien wat KennisBank heeft
vastgelegd, geïnjecteerd of verstuurd - via gewone bestanden, gestructureerde
status, en een doctor die je de waarheid vertelt. Het systeem is een glazen doos,
geen zwarte; een tool die je niet kunt inspecteren, is een tool die je niet kunt
vertrouwen.

**Traceability** - Een compleet audittrail. Elk feit, elke recall, elke injectie
is terug te herleiden tot zijn oorsprong en zijn *waarom* - welke sessie, welke
bron, welke score. Herkomst is geen bijzaak die er later op geschroefd is; het is
hoe het systeem geloof verdient. Niets komt de kennisbank binnen dat niet naar
huis te volgen is.

Samen: honesty betekent dat het niet tegen je liegt, transparency betekent dat je
het kunt zien werken, en traceability betekent dat je kunt bewijzen waar alles
vandaan kwam.

### Het vakmanschap: Care en Clarity

**Care** - Voor de mens, het werk en de lange termijn. Code die de volgende
onderhouder kan begrijpen en repareren. Een systeem dat jouw aandacht, jouw tijd
en de energie van je machine respecteert. Dit project is iets wat het beschermen
en koesteren waard is - geen probleem dat mechanisch wordt opgelost en daarna
verlaten.

**Clarity** - Begrijpelijk wint van slim. We willen weten hoe dingen onder de
motorkap werken - tot aan de query, de index, de byte - en we bouwen zo dat de
volgende persoon dat ook kan. Slimme oplossingen zijn altijd bespreekbaar;
clarity is de default waarnaar we terugkeren.

### Het partnerschap: Respect, Helpfulness, Integrity

**Respect for the human** - Jij bent de hoofdredacteur. De tool stelt voor; jij
beslist. Jouw focus is kostbaar, en elke onderbreking moet zijn plek verdienen.

**Helpfulness** - Werkelijk nuttig zijn is het hele punt - een echte partner in
het werk, geen passieve tool die op instructies wacht. Nut wordt gemeten aan de
vraag of je echte werk makkelijker werd.

**Integrity** - We zeggen het ware ding wanneer het ongelegen komt, brengen
risico's naar boven waar niet naar gevraagd is, en zijn het oneens wanneer het
bewijs dat ondersteunt. Nauwkeurigheid boven instemming, altijd.

### De geest: Curiosity and joy

**Curiosity and joy** - Gebouwd door iemand die ervan houdt te begrijpen hoe
dingen werken, van SID-chips en copper bars tot embeddings en vector search.
Elegante hacks worden gevierd, low-level begrip wordt gekoesterd, en het werk zelf
hoort een plezier te zijn. Een project dat met plezier is gemaakt, is doorgaans
een project dat het gebruiken waard is. (Ook: mostly harmless.)

## Deel 2 - De principes (hoe de waarden ontwerpwetten worden)

Elk principe is een waarde die operationeel is gemaakt. Lees ze als "omdat we X
waarderen, bouwen we op deze manier."

1. **Performance boven alles.** Zwaar werk (embedding, indexering, extractie)
   gebeurt buiten de hot path - op write-time, bij idle, gepland. Het interactieve
   pad (recall, injectie) blijft sub-seconde. *Een systeem dat je echte werk
   vertraagt, zet je uit.*
2. **Retrieval-first.** De kerntaak is enkelvoudig: de juiste, actuele context op
   het juiste moment vinden en aanreiken. Al het andere is bijrol.
3. **Lokaal, altijd.** Lokale opslag (SQLite, markdown), lokale embeddings
   (Ollama), lokale MCP (stdio). Geen gehoste dienst, geen verplichte cloud, geen
   telemetrie by default. *(Sovereignty, Privacy.)*
4. **Automatiseren boven discipline.** Wat op handmatige discipline leunt, gebeurt
   niet. Kwaliteit wordt autonoom geborgd; de gebruiker wordt alleen gevraagd wat
   alleen een mens kan beslissen.
5. **Mens als hoofdredacteur.** Het systeem stelt voor; de mens beslist. Het
   verwijdert nooit stilletjes iets, forceert geen merge van een overtuiging, en
   herschrijft je kennis niet achter je rug om. *(Respect, Integrity.)*
6. **Herkomst en auditeerbaarheid.** Elk stukje kennis is te herleiden tot een
   bron. Geen samenvatting zonder bewijslinks; als iets niet te herleiden is tot
   een bron, wordt het gemarkeerd, niet vertrouwd. *(Honesty, Traceability.)*
7. **Nooit twee keer dezelfde fout.** Het systeem onthoudt lessen en oude bugs en
   helpt actief voorkomen dat ze terugkeren.
8. **Spontane, maar hoog-precieze, hulp.** Proactief surfacen alleen boven een
   hoge relevantiedrempel. Een ongewenste onderbreking is precies de cruft die
   KennisBank bestaat om te vermijden. *(Respect, Helpfulness.)*
9. **Fail-open.** Een ontbrekende Ollama, een verouderde index, een kapotte hook,
   een model dat down is - niets daarvan mag de agent blokkeren. KennisBank
   degradeert gracieus en gaat uit de weg. *(Care, Helpfulness.)*
10. **Idempotent-safe.** Installers en config-mutaties zijn veilig om opnieuw te
    draaien, behouden gebruikersdata, gebruiken gemarkeerde managed blocks en
    key-scoped edits, maken een back-up voordat ze freeform-bestanden aanraken, en
    overschrijven nooit wat ze niet zelf hebben gemaakt. *(Care.)*
11. **Multi-agent, één vault.** Eén lokale vault en één stdio MCP-server, gedeeld
    door elke agent - Claude Code, Codex, OpenCode, GitHub Copilot CLI, en wat er
    hierna ook komt.
12. **Tijd is een eersteklas dimensie.** Geheugen is bi-temporeel: *valid time*
    (wanneer een feit waar was) staat los van *capture time* (wanneer het systeem
    het leerde). Feiten vervangen elkaar, verlopen en worden ingetrokken - met de
    historie intact, nooit overschreven.
13. **KISS - simpel en uitlegbaar boven slim en opaak.** Kies de aanpak die een
    onderhouder kan begrijpen en repareren. Eén helder mechanisme wint van drie
    slimme. *(Clarity, Transparency.)*

## Deel 3 - Hoe waarden zich in de praktijk tonen

De keten, concreet gemaakt:

| Waarde | Principe(s) | In de code |
|---|---|---|
| Sovereignty | Lokaal, altijd | lokale SQLite/markdown, lokale Ollama, stdio MCP; cloud opt-in |
| Privacy | Lokaal, altijd | secret-redactie in hooks, een waarschuwingspoort vóór elke cloud-call, geen telemetrie by default |
| Honesty | Herkomst & auditeerbaarheid | nooit verzinnen; markeer wat niet te verifiëren is |
| Transparency | KISS; Fail-open | `doctor.sh` PASS/WARN/FAIL, gestructureerde JSON, heldere status boven log-ruis |
| Traceability | Herkomst & auditeerbaarheid | `source_ref` op elke event, herkomst-wikilinks, het *waarom* van de Recall Inspector |
| Care | Idempotent-safe; Fail-open | veilig herdraaibare installers, back-ups vóór edits, gracieuze degradatie |
| Clarity | KISS | ADR's die het *waarom* uitleggen, één mechanisme boven drie |
| Respect | Mens als hoofdredacteur; hoge drempel | quarantaine voor niet-geverifieerd geheugen, geen stille deletes |
| Helpfulness | Retrieval-first; Performance | sub-seconde recall, de juiste context op het juiste moment |
| Integrity | Mens als hoofdredacteur | brengt risico's en meningsverschillen naar boven in plaats van te gokken |
| Curiosity/joy | - | het project mag een beetje leuk zijn |

## Wat KennisBank niet is

- Geen gehost platform, geen SaaS, geen verplicht cloud-account.
- Geen systeem dat namens jou vergeet of je kennis stilletjes bewerkt.
- Geen graph-database, geen Obsidian-plugin, en geen verplichte externe app.
- Geen bron van stellige, bronloze antwoorden.

## Hoe je dit document gebruikt

Wanneer je een wijziging voorstelt, weeg die dan tegen de keten. Als het
KennisBank trager maakt op de hot path, minder lokaal, minder privé, moeilijker
uit te leggen, minder traceerbaar, of luider - dan ligt de bewijslast bij de
wijziging. Als het retrieval scherper maakt, het systeem stiller, de mens meer in
controle, of het spoor helderder - dan trekt het de goede kant op.

_Zie ook: [`VALUES.md`](../VALUES.nl.md) en [`PRINCIPLES.md`](../PRINCIPLES.nl.md)
(de beknopte referentielijsten), `CLAUDE.md` (hoe KennisBank moet aanvoelen),
`AGENTS.md` (operationele install-/upgrade-regels), en `docs/adr/` (de
beslissingen die dit alles in de praktijk brengen)._
