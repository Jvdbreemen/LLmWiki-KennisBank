# Source-grounded experience recall v1 - productieplan

**Datum:** 2026-09-04

**Branch:** `codex/source-grounded-experience-production`

**Productie-epic:** TASK-225
**Beslisrecord:** ADR-010 (Proposed; blijft Proposed tot de release-gates slagen en
de eigenaar expliciet accepteert)

## 1. Uitkomst en productbesluit

We brengen niet een algemene derde vectorlaag naar productie. We brengen een
smallere, bewijsgebonden functie naar productie:

1. **Experience recall** zoekt uitsluitend expliciet naar eerder beoordeelde,
   outcome-gebonden ervaringen en geeft een toepasbare les terug.
2. **Source recall** hydrateert daarna, op verzoek, de exacte bronpassage achter
   zo'n ervaring. Vrij zoeken in ruwe bronnen blijft beschikbaar als expliciete,
   gelabelde lexical/FTS-zoekactie.

De productvolgorde is dus **experience-first bij retrieval, source-first bij
vertrouwen**. Een ervaringsrecord is nooit zijn eigen bewijs. Ruwe bronnen
blijven autoritatief; alle zoekindexen en afgeleide ervaringen zijn
rebuildable projections.

De volgende onderdelen gaan uitdrukkelijk **niet** mee in v1:

- automatische failure advisories of waarschuwingen;
- source-vectorsearch of sparse-first vectorreranking;
- een automatische fallback van gewone wiki/memory-recall naar bronnen;
- één gemengde ranking over wiki, memory, experience en source;
- outcome-based boosts in gewone recall;
- automatische promotie naar procedures of skills;
- automatische validatie van een door een LLM geformuleerde les;
- source- of experience-injectie in SessionStart/UserPromptSubmit hooks.

Dit is geen cosmetische beperking. Het experiment bewees waarde voor expliciete
experience-context, maar verwierp de automatische advisory en de vectorroute
voor raw sources. Productie mag alleen de bewezen doorsnede implementeren.

## 2. Bewijs waarop de scope rust

| Vraag | Bestaand bewijs | Productiegevolg |
| --- | --- | --- |
| Helpt experience-context bij handelen? | 43/60 correct/actionable tegen 19/60 baseline; delta +0.40; 95% bootstrap-CI +0.20 tot +0.5833 | Expliciete experience recall mag worden gehard voor productie |
| Is automatische failure-advisory veilig genoeg? | 2/10 false warnings; limiet was 1/10 | Geen automatische advisory in v1 |
| Voegt source-vectorreranking genoeg toe? | hit@5 0.25 tegen BM25 0.75; specificity 0.90; warm p95 8.33 s | Geen source-vectors of reranking in v1 |
| Is exact bronbewijs technisch mogelijk? | Bestaande contracttests bewaren path, hash, chunk en offsets | Exacte SourceRef-resolutie wordt een harde productie-invariant |
| Mag normale recall veranderen? | ADR-008 en ADR-010 vereisen een aparte gate en behoud van de sub-second hot path | Gewone wiki/memory-output blijft byte/shape-compatible en betaalt maximaal 1 ms p95 overhead |

De reeds gebruikte holdouts mogen niet opnieuw als onbevooroordeeld bewijs
worden gepresenteerd. Ze worden na deze beslissing alleen nog als **locked
regression sentinels** gebruikt: geen thresholdselectie, promptwijziging of
productclaim wordt erop afgestemd.

### 2.1 Wat we uit Supamem overnemen - en wat niet

De analyse van [Supamem](https://github.com/dzmitrys-dev/supamem/) verandert
niet ons geheugenmodel, maar scherpt de operationele vorm aan.

We nemen de volgende patronen over:

- opslag en retrieval zijn aparte verantwoordelijkheden;
- afgeleide zoekdata is rebuildable en heeft expliciete schema-/modelversies;
- geldigheid, status en scope worden op één centrale plek gefilterd;
- tools zijn expliciet en bounded in plaats van impliciete promptinjectie;
- migrations, health checks en observeerbare rebuilds horen bij het product,
  niet bij nazorg;
- hybrid retrieval is alleen zinvol op de kleine, gevalideerde
  experience-projectie waar het experiment daadwerkelijk winst aantoonde.

We nemen deze patronen niet over:

- één collectie waarin transcript, ruwe bron, feit en ervaring dezelfde
  retrievalautoriteit krijgen;
- door agents geschreven herinneringen meteen als vertrouwde lessen behandelen;
- alle ruwe bronnen vooraf embedden;
- automatisch gevonden ervaringen zonder review in gewone gesprekken injecteren;
- database- of frameworkkeuzes kopiëren die de lokale, inspecteerbare
  KennisBank-opslag niet aantoonbaar verbeteren.

Kort gezegd: Supamem levert bruikbare productmechanica, maar geen reden om de
afgewezen brede derde-vectorlaag alsnog te bouwen.

## 3. Productcontract

### 3.1 Gebruikersflow

```text
expliciete vraag naar eerdere aanpak/uitkomst
                  |
                  v
        experience_recall(query)
                  |
     gevalideerde les + outcome + SourceRef-id's
                  |
          gebruiker/agent wil bewijs?
                  |
                  v
   source_recall(source_ref=<id>, mode="reconstruct")
                  |
 exact passage + path + hashes + offsets + freshness
```

Een vrije bronvraag gebruikt hetzelfde publieke `source_recall`-oppervlak met
`mode="explicit"`, maar wordt als **best-effort lexical evidence search**
gelabeld. Een lege uitkomst bewijst niet dat informatie afwezig is.

### 3.2 Publieke read-API's

`experience_recall(query, k=3)`:

- accepteert alleen expliciete aanroepen;
- doorzoekt alleen `status=validated` en `review_state=accepted`;
- gebruikt hybrid FTS+dense retrieval op de kleine experience-projection;
- valt bij ontbrekende Ollama/vectorindex terug op gelabelde FTS-resultaten;
- retourneert maximaal drie diverse ervaringen;
- toont situation, approach/action, observed result, lesson, applicability,
  outcome/attempt/resolution state, confidence, validation stamp en SourceRef-id's;
- retourneert geen raw passage en doet geen writes.

`source_recall(query="", source_ref="", mode="explicit", k=5)`:

- `reconstruct` met `source_ref` is een deterministische lookup, geen ranking;
- `explicit` met `query` gebruikt uitsluitend FTS/BM25;
- `verify` is alleen een expliciete variant die dezelfde SourceRef-validator
  gebruikt;
- `fallback` bestaat niet in de publieke v1-contracten;
- geeft passage, approved-root-relative path, source hash, passage hash,
  offsets, offset unit, freshness en historische/current status terug;
- een stale/missing/mutated ref levert een expliciete status en nooit stil een
  nieuw passagefragment.

### 3.3 Niet-publieke write-/buildpaden

- Capture schrijft append-only events en outcomes naar het ledger.
- Extractie maakt uitsluitend `candidate` records.
- Een afzonderlijke validator controleert evidence en outcome refs.
- Alleen een expliciet geaccepteerde reviewbeslissing kan een candidate naar
  `validated` brengen.
- Rebuild maakt een tijdelijke projection, valideert die en vervangt de vorige
  projection atomisch.
- Geen van deze stappen draait in de prompt-hot-path.

## 4. Doelarchitectuur en data-eigenaarschap

| Artefact | Rol | Autoriteit | Mutatiebeleid |
| --- | --- | --- | --- |
| Ruwe bestanden in goedgekeurde vault-roots | Oorspronkelijk bewijs | Hoogste | Nooit door recall gewijzigd |
| `.claude/kb-experience-ledger.db` | Events, outcomes en menselijke reviewbesluiten | Canoniek voor experience-lifecycle | Append-only; correcties als nieuwe events |
| `.claude/kb-experience-index.db` | Zoekbare, gevalideerde experience-projectie | Afgeleid | Volledig rebuildable en atomisch vervangbaar |
| `.claude/kb-source.db` | Manifest, chunks en FTS-index van approved raw roots | Afgeleid | Volledig rebuildable; geen vectors in v1 |
| `kb-index.db` | Bestaande wiki/memory-recall | Bestaand productpad | Niet mengen met de nieuwe lagen |

Het huidige experimentele `kb-experience.db` mengt canonical events/outcomes en
zoekprojectie. De productie-migratie splitst die verantwoordelijkheden. Het
oude bestand wordt tijdens de migratie niet vernietigd: eerst backup/copy,
integriteitscontrole en een succesvolle rebuild; opruimen is een latere,
expliciete migratie.

## 5. SourceRef v1

Een stringpad is geen productieprovenance. Elke referentie wordt een
versioned, canoniek object met minimaal:

```json
{
  "schema_version": 1,
  "source_ref_id": "sr_...",
  "source_path": "01-raw/...",
  "source_sha256": "...",
  "chunk_id": "...",
  "start": 120,
  "end": 480,
  "offset_unit": "unicode_codepoint",
  "passage_sha256": "...",
  "captured_at": "2026-09-04T00:00:00Z",
  "redaction_state": "clear"
}
```

Productie-invarianten:

- `source_path` moet na resolutie onder een approved vault-root blijven;
- path traversal, symlink escape en absolute externe paden worden geweigerd;
- `source_sha256` en `passage_sha256` worden onafhankelijk gecontroleerd;
- offsets zijn half-open `[start, end)` en hun unit staat vast in het schema;
- het ref-id is content-addressed en deterministisch;
- een gewijzigde bron wordt `stale`, niet stil opnieuw gekoppeld;
- redacted of verwijderde bronnen worden niet als bewijs getoond;
- migratie van legacy stringrefs levert candidates op tot verificatie slaagt.

## 6. Experience-validatie

De huidige experimentele regel "refs aanwezig + outcome bekend = validated" is
te zwak. Productie scheidt drie assen:

- `status`: `candidate | validated | superseded | retracted`;
- `evidence_state`: `unverified | verified | stale | missing | contradictory`;
- `review_state`: `unreviewed | accepted | rejected`.

Een record mag alleen `validated` zijn als:

1. alle SourceRefs schema-valid zijn en exact resolven;
2. alle OutcomeRefs bestaan en bij dezelfde session/task horen;
3. outcome state niet `unknown` is;
4. attempt, resolution en final outcome afzonderlijk zijn bewaard;
5. de les geen onbewezen causale claim toevoegt;
6. tegenstrijdige evidence zichtbaar is opgelost of tot candidate leidt;
7. validator- en extractorversies zijn vastgelegd;
8. `review_state=accepted` door een expliciete menselijke beslissing.

Automatische extractie kan nuttige kandidaten voorbereiden, maar niet haar
eigen interpretatie valideren.

## 7. Feature flags en beleidsgrenzen

Vervang de twee te grove experimentele toggles door onafhankelijke flags:

| Flag | Default | Betekenis |
| --- | --- | --- |
| `experience_capture` | uit | Append-only events/outcomes verzamelen |
| `experience_projection` | uit | Afgeleide experience-index bouwen |
| `experience_explicit_recall` | uit | Publieke expliciete experience-tool |
| `source_explicit_recall` | uit | Publieke reconstructie/FTS-tool |

`experience_advisory`, `experience_ranking`, `experience_promotion` en
`source_fallback` worden geen inschakelbare productflags in v1. Hun publieke
routes worden verwijderd of afgewezen en door negatieve contracttests bewaakt.
De legacy keys `source_recall` en `experience_recall` worden gelezen voor een
migratiewaarschuwing, maar een oude `true` schakelt de nieuwe productieflags
niet automatisch in.

## 8. Test-first uitvoeringsvolgorde

### Gate A - beleid en contracten rood maken

Schrijf vóór productiecode tests die bewijzen dat de huidige experimentele
implementatie nog niet voldoet:

- structured SourceRef en exacte resolver;
- path/symlink/redaction/stale-ref afwijzing;
- extractor kan niet direct valideren;
- reviewbesluit vereist voor retrieval;
- ledger en projection zijn fysiek/rebuildmatig gescheiden;
- source-vectortabellen en embeddingcalls ontbreken in de v1 source-route;
- `failure`, `fallback`, ranking en promotion zijn niet publiek routeerbaar;
- lexical fallback van experience recall is gelabeld;
- normale recall blijft byte/shape-compatible;
- migratie is idempotent en herstelt na een onderbroken rebuild;
- telemetry bevat geen prompt, passage of raw lesson.

De contractcommit bevat alleen tests/fixtures en moet rood zijn om de kloof
zichtbaar te maken. Implementatietaken starten pas daarna.

### Gate B - storage en provenance groen

Implementeer SourceRef/resolver, ledger-splitsing, migration en review-gated
validation. Draai eerst focused tests, daarna alle source/experience/storage-
tests. Geen retrieval-API wordt ingeschakeld.

### Gate C - expliciete retrieval groen

Implementeer lexical source lookup/reconstructie en expliciete experience
hybrid+FTS fallback. Verwijder de onveilige publieke modes. Verifieer MCP-wire,
CLI-contracten, bounded output, privacy en fail-open gedrag.

### Gate D - operationele hardening groen

Voeg staged rebuild, doctor, migration reporting, aggregate telemetry,
cross-client installatie en rollback toe. Test in tijdelijke vaults en daarna
read-only tegen de geconfigureerde vault.

### Gate E - productbewijs en eigenaarbesluit

Gebruik drie soorten bewijs zonder opnieuw op de oude holdout te tunen:

1. **Locked regressions:** de bestaande 60-case set bewaakt dat retrieval niet
   instort; resultaten zijn regressiebewijs, geen nieuw onafhankelijk bewijs.
2. **Deterministische productiecontracten:** 100% SourceRef-integriteit,
   kandidaatlekkage 0, forbidden-route tests 100% groen, migrations idempotent.
3. **Kleine live canary:** twintig natuurlijk ontstane expliciete recalls,
   vooraf gelabeld als use-case en achteraf door de eigenaar beoordeeld op
   useful/neutral/harmful en evidence correct/incorrect.

Pas daarna krijgt ADR-010 een expliciete accept/reject/amend-beslissing.

## 9. Release-gates

Alle gates zijn conjunctief; een gemiddelde kan geen veiligheidsfout maskeren.

| Gate | Vereiste |
| --- | --- |
| Provenance | 100% van getoonde passages matcht path, source hash, offsets en passage hash |
| Review safety | 0 candidate/unreviewed/unknown records in gewone expliciete experience recall |
| Forbidden routes | 0 publiek routeerbare advisory/fallback/ranking/promotion paden |
| Retrieval regression | Locked experience hit@3 >= 0.85 en evidence precision 1.00; geen threshold tuning op deze set |
| Normal path | Bestaande output byte/shape-compatible; extra p95 overhead <= 1 ms |
| Explicit latency | Warm experience p95 <= 250 ms; source FTS p95 <= 250 ms; exact hydration p95 <= 50 ms op referentiehardware |
| Availability | Ontbrekende Ollama geeft gelabelde lexical fallback voor experience en raakt source hydration niet |
| Privacy | Geen raw prompt, passage, lesson of persoonlijk absoluut pad in telemetry/logs |
| Rebuild | Onderbreking behoudt de vorige goede index; tweede run is idempotent |
| Canary | Minimaal 20 echte expliciete recalls; >= 70% useful, <= 5% harmful, 100% getoond bewijs correct |
| Suite | Volledige repositorysuite groen op alle ondersteunde platformpaden |
| Authority | Eigenaar accepteert ADR-010 expliciet; zonder acceptatie geen main/release |

De canary-grenzen zijn productbeslisgrenzen, geen wetenschappelijke claim. Een
enkele harmful case of incorrecte bron wordt inhoudelijk onderzocht; de 5%-grens
is geen vrijbrief om een provenancefout weg te middelen.

## 10. Migratie en rollback

### Migratie

1. Detecteer legacy stores en flags; schrijf een read-only preflight-report.
2. Maak een timestamped backup van canonical experimental data.
3. Kopieer events/outcomes naar het nieuwe ledger met idempotency keys.
4. Converteer legacy stringrefs naar unverified SourceRef candidates.
5. Valideer referenties en schrijf review candidates; niet automatisch
   accepteren.
6. Bouw source- en experience-projections naar tijdelijke bestanden.
7. Draai schema-, integrity-, count- en sample-hydrationchecks.
8. Vervang projections atomisch; laat alle nieuwe flags uit.
9. Laat doctor en client-smokes slagen voordat een canaryflag aan gaat.

### Rollback

- Zet `experience_explicit_recall` en `source_explicit_recall` uit.
- Normale wiki/memory-recall blijft bruikbaar zonder de nieuwe bestanden.
- Verwijder nooit het ledger als rollbackstap.
- Derived projections mogen worden weggegooid en opnieuw gebouwd.
- Herstel de backup alleen bij bewezen ledger-corruptie en leg die handeling
  vast; een gewone release-rollback gebruikt uitsluitend flags en de vorige
  binaries.

## 11. Rolloutfasen

| Fase | Ingeschakeld | Bewijs voor volgende fase |
| --- | --- | --- |
| 0. Merge candidate | Niets | Suite, migration en doctor groen |
| 1. Shadow capture | `experience_capture` | Ledger-integriteit en geen hooklatency-regressie |
| 2. Shadow projection | plus `experience_projection` | Rebuild/idempotency, 100% validated refs |
| 3. Source canary | plus `source_explicit_recall` | Tien exacte reconstructies correct; privacy groen |
| 4. Experience canary | plus `experience_explicit_recall` | Twintig beoordeelde echte recalls halen gates |
| 5. Productie | De vier bewezen flags | ADR-010 expliciet Accepted/Amended en releasechecklist groen |

Elke fase duurt lang genoeg om ten minste de vereiste gebeurtenissen te
observeren; kalenderduur alleen is geen bewijs. Bij een gatefailure gaat de
betreffende read-flag uit terwijl capture/ledgerdata behouden blijft.

## 12. Observability

Doctor en aggregate metrics rapporteren:

- ledger schema/version, event/outcome/review counts en duplicate idempotency
  keys;
- candidate/validated/stale/missing/contradictory counts;
- projection build/version/model, laatste succesvolle atomic swap en leeftijd;
- SourceRef resolution coverage en redenen voor afwijzing;
- retrieval route (`hybrid`, `lexical_fallback`, `exact_ref`), latency en count;
- disabled/forbidden route attempts;
- migration/rollbackstatus per client.

Niet loggen: querytekst, passages, lessons, absolute persoonlijke paden,
embeddings of volledige SourceRefs. Debugoutput met inhoud is handmatig,
lokaal, tijdelijk en standaard uit.

## 13. Parallel uitvoerbaar werk

Na TASK-226 en de rode contracttests in TASK-227 kunnen drie werkstromen
parallel lopen:

```text
TASK-228 SourceRef/resolver ----+--> TASK-231 source retrieval --+
                               |                                |
TASK-229 ledger/projection ----+--> TASK-230 validation --------+--> TASK-232 experience retrieval
                                                                |
TASK-227 policy tests -------------------------------------------+--> TASK-233 flags/API policy
                                                                     |
                                                                     +--> TASK-234 operations
                                                                          |
                                                                          +--> TASK-235 clients/docs
                                                                                 |
                                                                                 +--> TASK-236 eval/canary
                                                                                        |
                                                                                        +--> TASK-237 decision/release
```

Taken die hetzelfde schema of publieke contract wijzigen worden niet parallel
gemerged zonder eerst de contractfixtures te rebasen. Elke taak levert een
focused testlog en een korte evidence-sectie in zijn backlogbestand.

## 14. Definition of Done

De productie-epic is pas klaar als:

- alle TASK-226 t/m TASK-237 klaar of expliciet met bewijs afgewezen zijn;
- de twee publieke read-routes exact het v1-contract volgen;
- raw evidence, ledger en projections afzonderlijk herstelbaar zijn;
- alle release-gates slagen op tijdelijke en geconfigureerde lokale vault;
- alle ondersteunde clients dezelfde flags en toolsemantiek tonen;
- de canary door de eigenaar is beoordeeld;
- ADR-010 expliciet Accepted of Amended is;
- rollback is geoefend en gedocumenteerd;
- release naar main via de normale review/releaseflow gebeurt, niet rechtstreeks
  vanaf deze werkbranch.

## 15. Eerste uitvoerbare stap

Start met TASK-226 en TASK-227: leg het productiecontract als tests vast en laat
ze aantoonbaar falen tegen de experimentele implementatie. Bouw daarna pas de
SourceRef-resolver en de gescheiden ledger/projection. Daarmee blijft de
volgende codewijziging toetsbaar en kan er geen brede “derde geheugenlaag”
ontstaan voordat de grenzen afdwingbaar zijn.
