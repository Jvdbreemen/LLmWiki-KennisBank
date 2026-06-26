---
title: KennisBank als agent-geheugen + leesbare kennisbank
date: 2026-06-26
status: design
author: Robert van den Breemen (+ Claude)
---

# KennisBank als agent-geheugen + leesbare kennisbank

## Doel

KennisBank tegelijk maken tot:
1. **Lange-termijn agent-geheugen** — agents (Claude Code, lokale MCP-clients) vinden
   eerder, vergelijkbaar werk snel terug: lessons learned, oude bugs, gerelateerde
   projecten — automatisch gepusht in de context binnen een fractie van een seconde.
2. **Mens-leesbare kennisbank** — Robert vindt zijn kennis zinvol en leesbaar terug
   (Obsidian-markdown), en kan een memory daarna als artikel nalezen.

"Best of both worlds": ruw, snel agent-geheugen **én** gecureerde, leesbare wiki —
zonder dat het een doorzoekbare-maar-onleesbare DB-soep wordt.

## Niet-onderhandelbare randvoorwaarden

Afgeleid uit het ontwerp-interview (angst-ranking van de gebruiker):

1. **Geen foute/stale recall** (#1 angst) — onbeoordeelde of achterhaalde memory mag
   nóóit als geldige context bovenkomen.
2. **Geen ruis** (#2) — kwaliteitspoort zodat relevante kennis niet verdrinkt.
3. **Geen bloat / dubbelen** (#3) — geen speld-in-hooiberg.
4. **Lokaal, altijd** (#4, hard) — niets mag zonder expliciete toestemming naar de cloud.
   SQLite-file lokaal, Ollama lokaal (GPU), MCP via stdio/localhost. Geen netwerk-bind.
5. **Leesbaar** (#5) — markdown blijft de leesbare laag.
6. **DB altijd herbouwbaar** (#6) — de index is een wegwerp-cache, herbouwbaar uit files.
7. **Geen handwerk** — alles wat handmatige discipline vereist gebeurt in de praktijk niet;
   kwaliteit moet autonoom/geautomatiseerd geborgd worden.
8. **Performance: vooraf betalen, snel ophalen** — zware verwerking off de hot path;
   recall is een index-lookup, geen corpus-scan.
9. **Onafhankelijk ontkoppeld** (hard) — het geheugen-subsysteem is volledig losgekoppeld
   van het bestaande werk (`auto_archive`, `distill_notify`, `embed_index`,
   `daily_graphify`). Eigen toggles, **default aan** (uitzetbaar). Geheugen uit = die
   features draaien exact als voorheen, nul impact. Geheugen behandelt
   `auto_archive`/`daily_graphify` als *optionele input*, nooit als afhankelijkheid.
   (Bewuste afwijking van de bestaande opt-in-conventie voor achtergrond-automatiek:
   geheugen is kern-functionaliteit, dus default aan.)

## Kernprincipe

```
markdown-files = BRON VAN WAARHEID   (Git, Obsidian, mens-leesbaar)
        │  build-index (afgeleid, incrementeel, herbouwbaar)
        ▼
   kb-index.db = WEGWERP-ZOEKINDEX   (rm + rebuild = altijd terug uit files)
```

De DB wordt nooit autoritatief. `rm kb-index.db && kb-index --rebuild` reconstrueert
'm volledig uit de markdown. Dekt randvoorwaarde #4 (lokaal, één file) en #6 (herbouwbaar).

## Architectuur — twee lagen, één waarheid

```
                  ┌─────────────────────────────────────────┐
   agents ──push──┤  RECALL (kb-retrieve hook + lokale MCP)  │
   (CC, Cursor)   │  zoekt: wiki + memory(current), beide  │
                  └──────────────┬──────────────────────────┘
                                 │ hybride query (<1s)
        ┌────────────────────────┴───────────────────────┐
        ▼                                                  ▼
  02-wiki/ (gecureerd)                            09-memory/ (ruw)
  mens-leesbare artikelen                         atomair → maand-merge
        ▲                                          status: unverified|current|...
        └──────────── /wiki promoot ◄──────────────────────┘

  files = waarheid  ──build-index──►  kb-index.db (sqlite-vec vec0 + FTS5)
```

Twee lagen, één vault, één afgeleide index:

- **`02-wiki/`** — bestaande gecureerde wiki. Ongewijzigd in rol.
- **`09-memory/`** — nieuwe ruwe agent-geheugenlaag (volgende vrije vault-nummer;
  `05-` is al `05-bronnen/`).
- **`kb-index.db`** — nieuwe afgeleide SQLite-index over beide lagen.

## Toggles & ontkoppeling

Het geheugen-subsysteem is volledig losgekoppeld van het bestaande werk. Twee **nieuwe**
toggles in `$VAULT/kennisbank-settings.json` (via bestaande `_settings.py get/set`),
**beide default `true`** (aan; uitzetbaar). Setup/upgrade schrijft ze als afwezig op `true`
(`_settings.py init`/`DEFAULTS`). Afwijking van de opt-in-conventie van `auto_archive`:
geheugen is kern-functionaliteit.

| Toggle | Gate-t | Onafhankelijk van |
|---|---|---|
| `memory_capture` | extractie + judge → `09-memory/`, sweep-onderhoud, index van memory | werkt mét `auto_archive` (auto) óf zonder (alleen via `/sessielog`) |
| `memory_recall`  | hook + MCP injecteren memory(current) in context | `memory_capture` — recall-only of capture-only kan |

Bestaande toggles blijven ongemoeid: `auto_archive`, `distill_notify`, `embed_index`,
`daily_graphify`.

Gedrag per combinatie:

- **beide aan (default):** geheugen capture + recall actief out-of-the-box.
- **beide uit (handmatig):** archive/distill/graphify/embed draaien exact als voorheen.
  Geheugen bestaat niet; nul impact (randvoorwaarde #9 — uitzetbaarheid blijft gegarandeerd).
- **`memory_capture` aan, `auto_archive` uit:** geheugen vult alleen als jij `/sessielog`
  draait. Geen stille afhankelijkheid van auto-archive.
- **`memory_capture` aan, `auto_archive` aan:** transcripts worden automatisch tot memory
  verwerkt — als gevolg van *twee aparte schakelaars*, niet één versmolten feature.
- **`memory_recall` los van `memory_capture`:** lezen-zonder-autonoom-schrijven of
  omgekeerd is mogelijk.

Ontkoppel-invariant: gedeelde idle-trigger-*infra* met graphify mag nooit één gedeelde
gate worden. Gedeelde *timing*, gescheiden *aan/uit*. Een test borgt dat met geheugen uit
geen enkel geheugen-pad (capture/sweep/recall/index-van-memory) draait.

## Componenten

Elk component heeft één doel, een gedefinieerde interface, en is los testbaar.

### 1. Memory-formaat (`09-memory/`)

Hybride: **atomair capture → maand-merge**.

- Capture = één `.md` per memory: `09-memory/YYYY-MM-DD-<slug>.md`.
- Memory ouder dan 30 dagen én niet gepromoot → gemergd naar maand-archief
  `09-memory/archive/YYYY-MM.md` (houdt file-count in toom, Obsidian browsebaar).

Frontmatter (truth-maintenance, randvoorwaarde #1):

```yaml
---
title: "<korte titel>"
type: memory
status: unverified        # unverified | current | superseded | retracted | expired
evidence_basis: cc-sessie # getypt | cc-sessie | audio | import | autoresearch | agent
source_session: <id/pad>  # herkomst voor provenance
created: 2026-06-26
updated: 2026-06-26
expires: 2026-12-26        # optioneel; judge/sweep schat vluchtigheid
superseded_by: [[...]]     # gezet bij supersession
tags: [...]
---
```

### 2. Capture + onafhankelijke judge (via bestaande transcript-pijplijn)

**Ontwerpkeuze A (goedgekeurd):** capture is volledig autonoom en hangt aan de
*bestaande* transcript-pijplijn, niet aan een skill die iemand moet onthouden. De
onafhankelijke judge draait in de SessionStart-sweep met *verse context* — niet inline
mid-sessie. Dit beslecht de trilemma: autonoom (#7) + onafhankelijk (#1) tegelijk.

Twee taken bewust gesplitst:
- **(a) per-memory kwaliteitspoort** = ruis/zekerheid-oordeel → in de sweep, verse context.
- **(b) cross-memory onderhoud** = globale blik → zelfde sweep (component 7).

Capture-flow:

```
SessionEnd-hook (autonoom, bestaat al):   transcript → 01-raw/transcripts/ archief
        │
SessionStart-sweep (volgende sessie, verse context = vanzelf onafhankelijk):
   ├─ lees nieuwe transcripts sinds vorige sweep
   ├─ extraheer kandidaat-memories (lessons learned, bugs, besluiten)
   ├─ capture-tijd dedup: embed + cosine tegen bestaande memories;
   │     similarity > DEDUP_THRESHOLD → merge in bestaande (updated-stamp), geen nieuwe file
   │     DEDUP_THRESHOLD (~0.92) is model-specifiek; empirisch tunen op qwen3-embedding,
   │     niet als constante hardcoden.
   └─ JUDGE per kandidaat (verse context, "probeer af te keuren; bij twijfel afkeuren"):
         hoge zekerheid + geen ruis → 09-memory/<slug>.md  status: current
         twijfel                    → 09-memory/<slug>.md  status: unverified
```

**Triggers (trigger-agnostisch pad).** Gegate op `memory_capture` (eigen toggle). De
extractie+judge-pijplijn vuurt op meerdere momenten — capture hangt nooit aan één moment
en nooit aan een andere toggle:
- **SessionStart-sweep** — autonome baseline; verwerkt aanwezige transcripts in
  `01-raw/transcripts/`. Dat die map gevuld wordt door `auto_archive` is *optionele input*,
  geen vereiste: ontbreekt auto-archive, dan is er simpelweg minder te verwerken.
- **`/sessielog`-skill** — on-demand: archiveert + verwerkt het transcript meteen
  (eigen, ingebouwde archiveerstap — werkt óók als `auto_archive` uit staat). Geeft een
  within-session capture-pad wanneer jij dat wilt.

Ontkoppeling: capture leest `01-raw/transcripts/` als *bron indien aanwezig*, maar bezit
z'n eigen trigger (`/sessielog`) en eigen gate (`memory_capture`). `auto_archive` aan/uit
verandert niets aan óf geheugen werkt — alleen hoeveel transcripts automatisch klaarstaan.

Onafhankelijkheid — **invariant, ongeacht de trigger:** de judge draait altijd in een
**verse-context sub-agent**, los van de sessie die de kennis produceerde → geen
zelf-keuren (#1 geborgd), óók wanneer `/sessielog` mid-sessie triggert. Expliciete
afkeur-bij-twijfel.

- `unverified` blijft **uitgesloten van recall** → vangnet onder een twijfelende judge.
- `current` wordt recallbaar zodra de sweep-stap de index bijwerkt (zelfde SessionStart,
  vaste volgorde sweep→index→recall).
- **Geen handwerk:** alles hangt aan SessionEnd/SessionStart-hooks die al draaien.
- Bewuste prijs: een memory uit sessie A is recallbaar vanaf sessie B, niet binnen A.
  Aanvaard — de kern-use-case (eerder werk) is weken oud; within-session is geen vereiste.

### 3. kb-index builder (uitbreiding van `build-embed-index.py`)

- Incrementeel: alleen gewijzigde files re-embedden (mtime/contenthash — bestaand gedrag).
- Schrijft naar `kb-index.db`:
  - **sqlite-vec `vec0`** virtuele tabel voor vectoren (brute-force KNN; gepinde versie).
  - **FTS5** tabel voor keyword (zit in Python-stdlib `sqlite3`; rotsvast).
- Indexeert `02-wiki/` (gegate op bestaande `embed_index`, ongewijzigd) + `09-memory/`
  met `status: current` (gegate op `memory_capture`; NIET unverified). Memory uit → alleen
  wiki geïndexeerd, exact als nu.
- Embeddings: `qwen3-embedding:8b` via Ollama op GPU.
- `--rebuild` flag: drop + herbouw volledig uit files.

### 4. kb-recall (query-lib)

Hybride query, gebruikt door zowel de hook als de MCP-server:

- Embed query 1× (Ollama GPU, tientallen ms).
- Vector-KNN (sqlite-vec) **+** keyword (FTS5), gefuseerd.
- Resultaten uit **beide** lagen (top-k wiki + top-k memory); wiki + `created` (recency)
  als tiebreaker bij gelijke relevantie — geen harde voorrang die memory begraaft
  (zie "Recall-balans").
- Filtert `status != current` weg (geen unverified/superseded/retracted/expired in recall).
- Output linkt naar bron-`.md` (zodat de mens het als artikel naleest).

### 5. kb-retrieve hook (uitbreiding bestaand)

- Bestaande UserPromptSubmit-hook, nu over de gecombineerde `kb-index.db`.
- Push top-matches in context. **Memory-laag gegate op `memory_recall`:** uit → de hook
  injecteert alleen wiki, exact als nu; aan → ook memory(current). Wiki-recall blijft
  onveranderd.
- **Fail-open, altijd** — nooit de prompt vertragen of blokkeren (bestaand contract).

### 6. kb MCP-server (nieuw)

- Lokale **stdio**-MCP-server; exposeert `kb-recall` (read) aan lokale MCP-clients
  (Cursor, LM Studio, Claude Desktop). Gegate op `memory_recall`.
- Geen netwerk-bind; cloud-web-AI's bewust uitgesloten (#4).
- Write-via-MCP: externe lokale client schrijft direct een memory → landt als
  `unverified`, wordt door de eerstvolgende sweep gejudged (zelfde quarantaine-poort).

### 7. memory-sweep (extractie + judge + cross-memory onderhoud)

De autonome motor. Draait op **SessionStart** (hook bestaat al; verse context). Doet
zowel de capture-judge (taak a, component 2) als het globale onderhoud (taak b) dat één
capture niet kan zien. Off hot path.

```
op SessionStart, verse context, idle:
   ├─ EXTRACTIE + JUDGE (taak a): nieuwe transcripts → kandidaat-memories →
   │     dedup → judge → current / unverified   (zie component 2)
   ├─ resterende unverified van eerdere sweeps → herbeoordeel:
   │     goed? → current   ruis? → retracted   dubbel? → merge, retracted
   ├─ cross-memory (globale blik, taak b):
   │     vluchtig?                       → expires zetten
   │     spreekt huidige current tegen?  → superseded + superseded_by-link
   │     clusterbaar?                    → markeer als promotie-kandidaat voor /wiki
   ├─ TWEEDE VERDEDIGINGSLINIE: hercontroleer recent gepromote current memories
   │     → alsnog retracted/superseded indien fout doorgelaten
   └─ rapport: "12 nieuw, 8 current, 3 retracted, 1 superseded, 0 fouten"
```

- Statuswijzigingen zijn **niet-destructief**: files blijven, alleen status flipt
  (reversibel, in Git-historie). Respecteert controle (#5).
- **Geen autonome hard-delete.** Verwijderen blijft mens-actie.
- **Eigen gate `memory_capture`** — *niet* de `daily_graphify`-toggle. De sweep deelt
  hooguit de idle-trigger-*infra* (wanneer draait achtergrondwerk) met graphify, maar is
  een **aparte aan/uit-beslissing**. Gedeelde timing, gescheiden gates.

### 8. /wiki promotie (uitbreiding bestaand)

- `/wiki` cluster gerelateerde `current` memories → één gecureerd wiki-artikel.
- Gepromote memories verlaten de hot recall (declutter, #3).

### 9. /stale uitbreiding

- Surfacet `expired` + oude transient memories als mens-leesbaar overzicht (optioneel —
  de sweep doet het zware werk; `/stale` is de menselijke inspectie-view).

### 10. Health & zichtbaarheid (kritiek voor optie C)

Optie C leunt op de sweep als vangnet; zijn falen moet **luid** zijn, anders verschuift
"inbox-rot" naar "quarantaine-rot":

- **`doctor.sh` no-cloud-check:** assert dat geen component een externe host aanroept.
- **`doctor.sh` quarantaine-rot-check:** waarschuw bij N memories `unverified` > 48u
  (de sweep ruimt niet op / draait niet).
- **Sessiestart-waarschuwing:** toon sweep-gezondheid + achterstand bij sessiestart.

## Data flow

```
Archief:  SessionEnd-hook / /sessielog ──► transcript → 01-raw/transcripts/
                                                              │
Sweep:    SessionStart / /sessielog ──► memory-sweep:
            extractie → dedup → JUDGE (verse-context sub-agent)
                                       hoge zekerheid ──► 09-memory/<slug>.md [current]
                                       twijfel ─────────► 09-memory/<slug>.md [unverified]
            + cross-memory onderhoud (supersede/expire/cluster) + rapport
                                                              │
Index:    sweep-stap / idle ──► kb-index builder ──(status=current only)──► kb-index.db
                                                              │
Recall:   prompt ──► kb-retrieve hook / MCP ──► kb-recall ──► kb-index.db
                                                  (beide lagen, current only, <1s)
                                                              │
Promote:  /wiki ──► current memories ──► 02-wiki/<artikel>.md
```

### SessionStart-volgorde (kritisch voor "leert door de dag")

Een memory is pas recallbaar als hij (a) `status: current` heeft én (b) in `kb-index.db`
staat. Bij SessionStart draaien zowel de sweep (flipt `unverified`→`current`) als de
index-build. Verkeerde volgorde = net-gepromote memory mist deze sessie. Daarom vaste
volgorde, idempotent:

```
SessionStart (of /sessielog):
   0. gate-check     (memory_capture? memory_recall? — alles hieronder is gegate)
   1. memory-sweep   (alleen als memory_capture: extractie+judge; status-flips; supersede)
   2. kb-index build (memory(current) alleen als memory_capture; wiki onder embed_index)
   3. recall actief  (memory in context alleen als memory_recall)
```

Met beide toggles uit draait stap 1–3 voor geheugen niet; wiki-index/recall blijven
ongemoeid onder hun eigen bestaande toggles.

Een memory uit sessie A is dus recallbaar vanaf sessie B (of meteen als jij `/sessielog`
draait — dat vuurt dezelfde sweep+index in deze sessie). Binnen-sessie automatisch (zonder
`/sessielog`) is bewust geen vereiste — de kern-use-case is recall van eerder werk.

## Performance-ontwerp

Principe: **betaal vooraf, retrieval snel.**

| Fase            | Wanneer            | Kost                                            |
|-----------------|--------------------|-------------------------------------------------|
| Embed + index   | sweep-stap / idle, incrementeel | off hot path                       |
| Memory-sweep    | SessionStart / /sessielog, idle | extractie + judge (verse-context sub-agent) + onderhoud, off hot path |
| **Recall**      | hot path           | index-lookup + 1× query-embed (Ollama GPU, ~tientallen ms) |

- Recall raakt nooit het corpus: sqlite-vec `vec0` brute-force KNN over enkele duizenden
  vectoren = sub-milliseconde. ANN-index (IVF/DiskANN) pas bij > 100k memories.
- Bottleneck = query-embedding. `qwen3-embedding:8b` op GPU → tientallen ms.
  Query- en index-model moeten identiek zijn (geldige cosine).
- Min-impact: index = één SQLite-file (`mmap`, geen proces); hook fail-open; sweep idle.

## sqlite-vec — risico, verificatie & mitigatie

Status (juni 2026): `v0.1.10-alpha.4` is de laatste alpha; `v0.1.9` is een stabiele
non-prerelease tag, Mozilla-backed, actief. Risico = breaking changes in SQL-API/storage-format.

**Geverifieerd op doelmachine (2026-06-26):** sqlite-vec laadt op Windows / Python 3.14.2.
De stdlib `sqlite3` ondersteunt `enable_load_extension(True)`, `pip install sqlite-vec`
levert `vec_version() = v0.1.9` (de stabiele tag). De backbone-aanname is dus empirisch
bevestigd; `vec0` is de vector-backend, geen fallback nodig.

Mitigatie:
- **Versie pinnen** op `v0.1.9` (de geverifieerde stabiele tag).
- **Brute-force `vec0`** gebruiken (stabiel), experimentele IVF/DiskANN mijden tot v1.
- Index is **afgeleid + herbouwbaar** → storage-break kost een rebuild, geen dataverlies.
  Het engste alpha-risico raakt deze use-case niet.
- Fallback-ontwerp (FTS5 + vectoren-als-blob + numpy-cosine, geen extensie nodig) blijft
  achter de hand mocht een toekomstige upgrade `vec0` breken — zelfde `kb-index.db`.

## Error handling

- **Recall (hook):** fail-open. Elke fout/lege cache/cold index → geen output, exit 0.
- **Index-builder:** corrupte/missende `kb-index.db` → `--rebuild` uit files.
- **Sweep-faal:** zichtbaar bij sessiestart + `doctor.sh`; geparkeerde memories blijven
  `unverified` (veilig: niet recallbaar) tot volgende succesvolle sweep. Niet-geëxtraheerde
  transcripts blijven in `01-raw/transcripts/` staan → volgende sweep pakt ze op.
- **Judge-faal:** kandidaat valt terug op `unverified` (fail-safe: bij twijfel of fout
  nooit direct `current`).
- **Model-mismatch:** cache-entries met afwijkend embed-model/dimensie worden genegeerd
  (bestaand cross-model-veiligheidsgedrag van kb-retrieve).

## Testing

- Unit: extractie+dedup+frontmatter, judge (afkeur-bij-twijfel), kb-recall (beide-lagen,
  status-filter, recency-tiebreak), index-builder (incrementeel + rebuild-idempotentie).
- Integratie: transcript → sweep extraheert+judget; twijfel → recall ziet `unverified`
  niet; hoge zekerheid → na index-build recallbaar; sweep hercontroleert `current` → kan
  alsnog retracten.
- Onafhankelijkheid judge: draait in verse-context sub-agent (ook bij `/sessielog`-trigger),
  keurt producent-ruis af (geen zelf-keuren).
- Eigenschap: `rebuild` uit files reproduceert dezelfde index (herbouwbaarheid #6).
- No-cloud: test/doctor assert geen externe host-calls (#4).
- **Ontkoppeling (#9):** met `memory_capture`+`memory_recall` uit draait geen enkel
  geheugen-pad (capture/sweep/recall/memory-index); archive/distill/graphify/embed gedragen
  zich byte-identiek aan vóór het geheugen-subsysteem. Toggles onafhankelijk schakelbaar.

## UX & output-principe (zie `CLAUDE.md`)

KennisBank moet voelen alsof het er niet is — snel, automatisch, uit de weg. Dit stuurt
alle componenten:

- **Onzichtbaar tenzij waardevol.** De recall-hook injecteert stil; sweep/index draaien
  idle. Geen ceremonie, geen log-ruis richting de gebruiker.
- **Feitelijke output, samengevat.** Sweep/index rapporteren in één heldere regel
  ("12 nieuw, 8 current, 3 retracted, 0 fouten"), niet met log-dumps. Onderdruk ruis,
  behoud status-besef.
- **Proactief surfacen, hoog-precies.** "Hé, hier liep je twee maanden geleden ook
  tegenaan." Dit rijdt op dezelfde relevantie-score als recall, maar spreekt alleen
  ongevraagd boven een **hogere** drempel dan de stille injectie. Onterechte
  onderbrekingen zijn precies de cruft die we vermijden — liever stil dan vals-positief.
- **Performance + retrieval leidend** bij elke afweging; KISS bij elke keuze.

## Recall-balans (wiki eerst, memory niet begraven)

"Wiki eerst" mag de kern-use-case (recall van rúwe sessie-lessons/bugs in `09-memory`)
niet verdringen. Een generiek wiki-artikel mag de specifieke ruwe memory die het antwoord
ís niet wegdrukken. Daarom: recall garandeert resultaten uit **beide** lagen (bv. top-k
wiki + top-k memory), met wiki als tiebreaker bij gelijke relevantie — niet als harde
voorrang die memory uit de top verdringt.

## YAGNI — bewust NIET

- ❌ DB als bron-van-waarheid (breekt herbouw + leesbaarheid).
- ❌ `confidence`-gegokte cijfers (schijnprecisie).
- ❌ cloud-web-AI-toegang (leak-risico #4).
- ❌ access-keys / multi-tenant filtering (single-user, nul waarde).
- ❌ inbox-omweg voor twijfel-captures (vervangen door sweep-judge + quarantaine).
- ❌ rigide 1×/dag janitor (vervangen door SessionStart/`/sessielog`-getriggerde sweep).
- ❌ inline-judge mid-sessie (vervangen door verse-context judge in de sweep — autonoom
  + onafhankelijk; trilemma-besluit A).
- ❌ autonome hard-delete (alleen reversibele status-flips).

## Open punten

Geen. Alle ontwerpkeuzes zijn in het interview vastgelegd. Implementatie-volgorde
(fasering) wordt in het implementatie-plan (writing-plans) uitgewerkt.
