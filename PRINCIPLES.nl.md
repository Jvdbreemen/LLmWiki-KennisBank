# KennisBank - Kernprincipes

[English](PRINCIPLES.md) · **Nederlands**

Dit zijn de principes die elke ontwerp- en codebeslissing in KennisBank sturen.
Ze vormen het *waarom* achter de code; wanneer een afweging onduidelijk is, geven
zij de doorslag. Operationele instructies staan in `AGENTS.md`; hoe het project
moet *aanvoelen* is hier vastgelegd.

## Noord-ster: onzichtbaar, snel, uit de weg

KennisBank moet aanvoelen alsof het er niet is. Zijn taak is je te helpen met je
echte werk - schrijven, coderen, denken - zonder ooit zelf aandacht op te eisen.
De beste versie van KennisBank is de versie waarvan je vergeet dat hij draait, tot
precies het moment waarop hij je exact de context aanreikt die je nodig had.

Alles hieronder staat ten dienste van die noord-ster.

## De principes

### 1. Performance vóór alles
Optimaliseer voor dagelijks gebruik. Zwaar werk (embedding, indexeren, extractie)
gebeurt **off the hot path** - op schrijfmoment, tijdens idle, of gepland. Het
interactieve pad (recall, prompt-injectie) blijft **sub-seconde**. Betaal vooraf,
haal snel op. Een kennissysteem dat latency toevoegt aan je echte werk is een
kennissysteem dat je uitzet.

### 2. Retrieval eerst
De kerntaak is enkelvoudig: de juiste, actuele context op het juiste moment
terugvinden en aanreiken. Al het andere - vastleggen, distilleren, visualiseren -
is bijrol. Wanneer twee features met elkaar concurreren, wint degene die retrieval
verbetert.

### 3. Lokaal, altijd
Niets verlaat je machine zonder expliciete toestemming. Lokale opslag (SQLite,
markdown), lokale embeddings (Ollama), lokale MCP (stdio). Geen gehoste dienst,
geen verplichte cloud, standaard geen telemetrie. Jouw kennis is van jou;
soevereiniteit is geen feature, het is het fundament.

### 4. Automatiseren boven discipline
Wat op handmatige discipline leunt, gebeurt in de praktijk niet. Kwaliteit wordt
autonoom geborgd - vastleggen, indexeren, stale-checks en geheugenhygiëne draaien
vanzelf. De gebruiker wordt alleen gevraagd naar wat alleen een mens kan beslissen.

### 5. De mens als hoofdredacteur
Het systeem stelt voor; de mens beslist. KennisBank verwijdert nooit stilletjes,
forceert nooit een merge van een overtuiging, herschrijft je kennis nooit achter
je rug om. Ongeverifieerde herinneringen wachten in quarantaine op een menselijke
beslissing. De machine doet het monnikenwerk; de mens houdt het gezag over wat
waar is.

### 6. Herkomst en auditbaarheid
Elk stuk kennis is terug te herleiden tot een bron - een ruwe sessie, een
document, een gebeurtenis. Geen samenvatting zonder bewijslinks; geen bewering die
je niet naar huis kunt volgen. Dit is de anti-hallucinatiegarantie: als iets niet
van een bron kan worden voorzien, wordt het gemarkeerd, niet vertrouwd.

### 7. Nooit twee keer dezelfde fout
Het systeem onthoudt lessons learned en oude bugs, en helpt actief voorkomen dat
ze terugkeren. "Precies tegen deze muur liep je twee maanden geleden al aan" - op
het juiste moment naar boven gehaald - is meer waard dan welke hoeveelheid ruwe
opslag dan ook.

### 8. Spontane, maar hoog-precieze, hulp
Eerdere kennis proactief naar boven halen mag - maar alleen boven een hoge
relevantiedrempel. Een ongewenste onderbreking is precies de cruft die KennisBank
bestaat om te vermijden. Onderdruk log-ruis; geef in plaats daarvan heldere
samenvattingen en status. Geen ceremonie, geen filler.

### 9. Fail-open
Een ontbrekende Ollama, een stale index, een kapotte hook, een model dat plat ligt
- geen van deze mag de agent blokkeren. KennisBank degradeert netjes: het slaat
zijn eigen side effect over, waarschuwt zachtjes, en gaat uit de weg. Het werk van
de gebruiker stopt nooit omdat de geheugenlaag een hik had.

### 10. Idempotent-veilig
Installers en config-mutaties zijn veilig om opnieuw te draaien, zowel voor verse
als bestaande setups. Ze verversen tooling, **behouden gebruikersdata**, gebruiken
gemarkeerde managed blocks en key-scoped bewerkingen, maken een back-up voordat ze
freeform-bestanden aanraken, en overschrijven nooit wat ze niet zelf hebben
aangemaakt. Upgraden is gewoon installeren, opnieuw uitgevoerd.

### 11. Multi-agent, één vault
Eén lokale vault en één stdio MCP-server, gedeeld door elke agent - Claude Code,
Codex, OpenCode, GitHub Copilot CLI, en wat er daarna ook komt. Je Copilot-sessie
wordt herroepbare historie in je Claude-sessie. De kennislaag is agent-agnostisch;
de vault is de single source of truth.

### 12. Tijd is een eersteklas dimensie
Het geheugen is **bi-temporeel**: *valid time* (wanneer een feit waar was) staat
los van *capture time* (wanneer het systeem het leerde). Je kunt vragen "wat was
waar op datum X" en een eerlijk antwoord krijgen. Feiten worden vervangen,
verlopen en worden ingetrokken - met de historie intact, nooit overschreven.

### 13. KISS - simpel en uitlegbaar boven slim en opaak
Bij elke splitsing: verkies de aanpak die een onderhouder kan begrijpen en
repareren boven degene die enkel werkt. Eén helder mechanisme verslaat drie
clevere. Maak ontwerpkeuzes expliciet - leg uit *waarom*, niet alleen *wat*.
Clever kan altijd besproken worden; helderheid is de standaard.

## Wat KennisBank niet is

- Geen gehost platform, geen SaaS, geen verplicht cloud-account.
- Geen systeem dat namens jou vergeet of je kennis stilletjes bewerkt.
- Geen graafdatabase, geen Obsidian-plugin, geen verplichte externe app.
- Geen bron van zelfverzekerde antwoorden zonder bronvermelding.

## Hoe deze principes te gebruiken

Wanneer je een wijziging voorstelt, weeg die dan tegen deze lijst. Maakt ze
KennisBank trager op de hot path, minder lokaal, moeilijker uit te leggen, of
luider - dan ligt de bewijslast bij de wijziging. Maakt ze retrieval scherper, het
systeem stiller, of de mens meer in controle - dan trekt ze de goede kant op.

_Zie ook: `CLAUDE.md` (hoe KennisBank moet aanvoelen, voor bijdragers en agents),
`docs/adr/` (de beslissingen die deze principes implementeren), en `AGENTS.md` (de
operationele install/upgrade-regels)._
