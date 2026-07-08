# Changelog

All notable changes to LLmWiki-KennisBank are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.14.0] - 2026-07-08

### Added
- **Local LiteParse document intake.** New `scripts/parse-document.py` and `scripts/_liteparse.py` parse PDFs, Office files, spreadsheets, presentations, and document-like images into citeable markdown under `<vault>/05-bronnen/liteparse/`.
- **Document import command route.** `/import documents <path> [prefix]` batches LiteParse-backed source conversion while keeping imported source material separate from raw session logs.
- **LiteParse intake tests.** `tests/test_liteparse_integration.py` covers supported extensions, frontmatter rendering, lazy dependency loading, intake action routing, and dry-run directory handling.

### Changed
- **Inbox routing now uses LiteParse for source documents.** `/intake` routes PDFs and Office-like documents to `parse_with_liteparse`, while document-like images can use LiteParse OCR or fall back to the existing media description flow.
- **Setup and doctor validate document parsing.** `setup.sh` installs `liteparse>=2.0,<3`, and `doctor.sh` checks the same interpreter used by setup on Windows (`py -3`) so document parsing is validated where it will actually run.
- **OCR is opt-in.** `parse-document.py` defaults OCR off to avoid polluting native-text PDF output with missing Tesseract/tessdata diagnostics; `--ocr` enables OCR explicitly for scans.

## [0.13.0] - 2026-07-08

### Added
- **Temporal Activity Recall.** New local activity-memory layer with canonical activity events, deterministic Dutch/English date parsing, strict period filtering, topic/entity timelines, deterministic daily/weekly rollups, and a derived SQLite index at `<vault>/.claude/kb-activity.db`.
- **New user commands.** `/weeklog`, `/timeline`, and `/watdeedik` build/query the same activity API and always return source refs or a recoverable warning.
- **MCP temporal API.** `kb-mcp.py` now exposes `what_did_i_do`, `timeline`, `weeklog`, and `topic_timeline` alongside the existing `recall` and `capture` tools. Codex/OpenCode validation now requires these tools during the stdio MCP handshake.
- **Temporal eval harness.** `scripts/kb-activity-eval.py` measures date recall, period recall, topic timeline behavior, negative controls, and provenance coverage. The repo ships `kb-activity-eval-set.example.json`.
- **Architecture spec.** `docs/superpowers/specs/2026-07-08-temporal-activity-recall-design.md` records the local SQLite/file-first decision and compares the design with Mem0, Zep/Graphiti, Letta/MemGPT, and ClawMem.

### Changed
- **Setup/doctor now cover temporal recall.** `setup.sh` deploys temporal scripts and commands, builds/refreshed the activity index before the final validation gate, and SessionStart hooks include `build-activity-index.py`. `doctor.sh` reports missing/corrupt/stale activity indexes and checks temporal MCP wrappers when MCP is configured.
- **Agent integrations install temporal aliases.** Codex gets `/prompts:weeklog`, `/prompts:timeline`, and `/prompts:watdeedik`; OpenCode gets matching commands; Claude Code gets slash commands.
- **Progress output is more explicit.** Activity index rebuilds report counts, current source and elapsed time at least every 300 seconds during long backfills.

## [0.12.2] - 2026-07-07

### Fixed
- **Codex/OpenCode MCP startup is now runtime-validated.** `setup.sh` installs `mcp==1.28.1` into the same Python interpreter used by the generated MCP command, and `scripts/install-agent-envs.py` now performs a real stdio MCP initialize/list-tools handshake that requires both `recall` and `capture`.
- **Doctor now catches configured-but-broken MCP installs.** If Codex or OpenCode has a KennisBank MCP server configured, `doctor.sh` verifies that the Python MCP SDK imports successfully and fails the install when it is missing instead of leaving the agent to fail at startup.

## [0.12.1] - 2026-07-07

### Fixed
- **Codex MCP config repair is now TOML-safe.** Re-running setup no longer duplicates `[mcp_servers.kennisbank.env]` in `~/.codex/config.toml`; the replacement now consumes the full KennisBank MCP table plus subtables before writing the refreshed block.
- **Codex validation now catches malformed TOML.** The agent installer validates that Codex has exactly one KennisBank MCP table and env subtable, and parses `config.toml` with `tomllib` where available. This prevents `codex mcp list` from failing after a seemingly successful setup.

## [0.12.0] - 2026-07-07

### Added
- **Multi-agent setup and validation (`setup.sh`, `scripts/install-agent-envs.py`).** Setup now installs and validates selected agent environments with `--agents claude,codex,opencode,all`. Claude Code keeps native commands/skills/hooks, Codex receives shared skills, `/prompts:*` aliases, lifecycle hooks, MCP config and global `AGENTS.md`, and OpenCode receives commands, shared skills, MCP config, global rules and a local plugin.
- **OpenRouter as explicit opt-in LLM backend.** Interactive setup keeps `ollama` as the default and offers `openrouter` as a deliberate cloud option for judge/extraction. The live config stores only provider, model, endpoint and `api_key_env`; optional entered keys are stored user-local in `~/.config/kennisbank/secrets.json`, never in the repo or vault.
- **Post-install model smoke tests.** Setup validates the configured embedding and LLM backends before completing. Ollama uses local model/API smoke checks; OpenRouter uses a minimal authenticated chat-completions smoke check when selected.

### Changed
- **README rewritten as a stronger English product introduction.** The top-level story now presents KennisBank as a sovereign memory layer for Claude Code, Codex, OpenCode and other local agents, with a dedicated `v0.12.0` section for the new setup, validation and OpenRouter behavior.
- **Agent operating contract refreshed (`AGENTS.md`, `CONFIGURATION.md`, `docs/agent-integrations.md`).** The docs now emphasize active vault-path resolution, setup as the single install/upgrade/repair path, Codex/OpenCode behavior, MCP wiring, hooks, model validation and privacy boundaries.
- **Hook registration self-heals the active vault path.** Re-running setup updates stale `KENNISBANK_VAULT` values in Claude Code hook environment blocks instead of leaving hooks pointed at an old vault.

### Fixed
- **Non-default vault handoff no longer points back to `~/KennisBank`.** Setup's final message now reports the active vault path and selected agent targets, preventing confusing follow-up instructions after installs such as `D:/Users/Robert/Documents/Claude/Projects/Kluis`.
- **Release metadata now includes the tracked MIT license in the release narrative.** The repo already ships `LICENSE`; this release keeps README and changelog aligned around that MIT licensing contract.

## [0.11.0] - 2026-07-07

### Added
- **MCP-first toegang buiten Claude Code (`scripts/kb-mcp.py`, `scripts/kb-ask.py`, `docs/agent-integrations.md`, `adapters/registry.json`).** De lokale KennisBank is nu ook bruikbaar door andere agent-clients via een dunne stdio MCP-server met `recall`, `capture` en instructions. `kb-ask.py` biedt een CLI-brug voor handmatige vraag/antwoordflows, de adapter-registry legt client-integraties vast, en `.github/copilot-instructions.md` is de eerste native push-adapter.
- **ChatGPT-export/import (`scripts/import-chatgpt-export.py`).** ChatGPT-conversaties kunnen nu naar raw sessies worden geïmporteerd, zodat de wiki- en memory-laag niet Claude-only blijven.
- **`memory-doctor rejudge` (`scripts/memory-doctor.py`).** Na een LLM/Ollama-outage kunnen oude `unverified` memories opnieuw gejudged worden. Alleen een expliciet `current`-verdict promoveert; twijfel, model-down of exceptions blijven fail-safe op `unverified`.

### Changed
- **Herkomst/trust wordt zichtbaar en licht meegewogen in retrieval (`scripts/_memory.py`, `scripts/kb-retrieve.py`, `scripts/_rank.py`).** Memory-hits krijgen een compacte deterministische herkomst/status-tag in het injectieblok, en de memory-ranking gebruikt een kleine bounded trust-factor op `evidence_basis` (`getypt` > mens-in-lus > agent). Wiki-hits blijven ongetagd.
- **Usage-scan telt alleen load-bearing gebruik (`scripts/kb-usage-scan.py`).** Een losse prose-verwijzing naar een geïnjecteerde stem telt niet langer als `used`; alleen tool-use input geldt als werkelijk geraadpleegd. Dit voorkomt dat de agent zijn eigen injectie terugpraat en daarmee vals-positieve usage-boosts maakt.
- **Testsuite-hardening en CI-dekkingspoort (`tests/__init__.py`, `.github/workflows/ci.yml`, `requirements.txt`).** De suite is hermetischer tegen echte netwerk/model-calls, de CI-run heeft een timeout-vangnet en draait onder `coverage` met een `--fail-under=75` gate.

### Fixed
- **Backfill-cap voor mega-transcripts (`scripts/memory-sweep.py`, `--max-per-transcript`).** De `--all` her-extractie kreeg een per-transcript write-cap zodat een grote source_session niet onbeperkt facetten dumpt. De normale per-sessie sweep blijft ongewijzigd; dit raakt alleen het aantal geschreven memories per transcript in de backfill-route.
- **Deterministische exacte-body dedup vóór embeddings (`scripts/_sweeputil.py`, `scripts/memory-sweep.py`).** Exacte re-extracties worden nu op body-hash gevangen voordat cosine/embedding nodig is, zodat een tijdelijke vectorloze bestaande memory geen duplicate-escape meer veroorzaakt.
- **Embed-retry bij tijdelijke embedding-hikjes (`scripts/memory-sweep.py`).** Kandidaten waarvan `emb.embed(body)` tijdelijk `None` teruggeeft worden nu kort opnieuw geprobeerd voordat `embed_failed` telt. De route blijft fail-soft na de maximale retries en introduceert geen per-kandidaat herverwerking of extra watermark-risico.

## [0.10.0] - 2026-07-03

### Added
- **LLM-backend example + documentatie (`kennisbank-llm.example.json`, CONFIGURATION sectie 4a).** De embedding-backend had een voorbeeld-config en documentatie, maar de LLM-backend voor de memory judge/extractie (`scripts/_llm.py`) stond nergens in CONFIGURATION.md en had geen voorbeeld. Nu beide: een voorbeeld-config (default ollama/gemma4:latest, opt-in cloud openrouter/claude-cli, per-provider model-overrides, ordered local-then-cloud fallback-chain) en sectie 4a (provider-keten, `KB_LLM_*` env-vars, config-precedentie, en de noot dat dit bestand niet auto-gedeployed wordt). Met de 'pin your model'-gotcha: de code-default is de tag `gemma4:latest`; heeft je lokale Ollama een andere tag (bv. `gemma4:12b`) dan faalt de sweep-probe stil en meldt de heartbeat `model_unreachable: true` terwijl Ollama draait — capture produceert dan niets. Check `ollama list` en pin de tag.
- **Provenance met tanden: fail-closed op niet-herleidbare herkomst (`kb-lint.py --strict`, doctor 13d FAIL-tier, `/wiki` stap 4.5).** Tot nu toe was elke provenance-poort zacht: `/wiki` stap 4.5 was een model-prompt met ontsnapping ("waarschuwingen mag je laten staan") en doctor 13d mapte alles naar WARN. Een destillatie-hallucinatie die een `[[raw-sessie]]`-link sloopt (missing/dangling artikel) kon zo ongezien landen. kb-lint onderscheidt nu HARD findings (missing/dangling = niet-auditeerbaar) van advisory (path-only): `--strict` geeft exit 2 alleen op HARD (path-only blijft exit 0), het JSON-rapport draagt een `hard`-teller, doctor 13d promoveert HARD naar FAIL (path-only blijft WARN), en `/wiki` stap 4.5 draait `--strict` als harde stop vóór afronden. Deterministisch, nul LLM-kosten, werkt op elke topologie (geen git-hook/CI, geen cloud-push). Bewust NIET als green-CI merge-gate (vault staat buiten de repo; zou soevereiniteit schenden) — governance-hardening binnen de bestaande hook/command-laag. TASK-13.

### Fixed
- **kb-eval fidelity: per-laag meten i.p.v. gefuseerde ranking (`scripts/kb-eval.py`).** Het harnas fuseerde wiki+memory in één ranked lijst, maar de UserPromptSubmit-hook injecteert die lagen als TWEE gescheiden, gelabelde blokken (`_wiki_block` via wiki_hits, `_memory_block` via memory_hits) en fuseert nooit. De gefuseerde meting scoorde daardoor een topologie die de hook niet gebruikt en gaf vals signaal: op een vault met een gevulde geheugenlaag kelderde de gerapporteerde wiki-recall@1 van 0.914 naar 0.314 doordat memories in de gefuseerde lijst wiki-artikelen verdrongen — een "regressie" die in productie niet bestaat (de blokken staan los). kb-eval meet nu per laag (wiki-set wiki-only, geheugen-set memory-only) en draait zonder `--set` beide sets in één run, elk tegen zijn eigen laag. `--layer wiki|memory` voor een custom set.

### Added
- **Geheugen-eval-set (`06-claude/kb-memory-eval-set.json`, `kb-memory-eval-set.example.json`).** Aparte eval-set met geheugen-verwachte antwoorden, zodat de nuttigheid van het geheugen-blok meetbaar is i.p.v. als ruis geteld te worden tegen de wiki-set. Eerste baseline op de Kluis-vault (588 memories na backfill, qwen3): memory recall@1 0.529, recall@3 0.882, MRR 0.686 — de over-extractie van de mega-sessies (148 memories uit één transcript) verdunt de rang-1-precisie meetbaar, terwijl top-3 gezond blijft.

## [0.9.0] - 2026-07-02

### Added
- **Usage-telemetrie: de retrieval-feedbackloop (`scripts/_usage.py`, `scripts/kb-usage-scan.py`).** Het grootste gat uit de externe review gedicht: het systeem leert nu welke kennis daadwerkelijk hielp. kb-retrieve registreert per injectie welke stems het injecteerde (pending in eigen `kb-usage.db`, bewust los van kb-index.db zodat gebruiksgeschiedenis modelwissels en index-rebuilds overleeft); een nieuwe SessionEnd-hook scant het transcript en markeert stems die in assistant-tekst of tool-calls voorkwamen als gebruikt (de injectie zelf, in user-berichten, telt niet mee). Het signaal voedt: (1) een gebruiks-boost in de ranking (`_rank.usage_factor`: ×1.10 bij gebruik ≤30d, ×1.05 ≤90d, voor beide lagen — een warm wiki-artikel is bewezen nuttig); (2) gebruiksdecay in `stale-check.py`: een recent gebruikt artikel is niet staal, hoe oud zijn `updated` ook is. Gegate op de `usage_telemetry`-toggle (default aan), fail-open op elke route.
- **Drempel-kalibratie-harnas (`scripts/kb-calibrate.py` + `kb-calibrate-set.example.json`).** Alle cosine-drempels (dedup 0.92, rewrite 0.83, reconcile 0.75, conflict 0.62, retrieve 0.60) zijn getuned op qwen3-embedding:8b; een modelwissel maakte die kalibratie stilletjes ongeldig. Het harnas embedt een handgelabelde parenset (duplicate/related/unrelated, `<vault>/06-claude/kb-calibrate-set.json`) met het actieve model en stelt per drempelklasse een grens voor, met separatiemarge en een OK/HERIJK-oordeel per huidige knop. Schrijft niets: de mens beslist. Nulmeting op qwen3 (24 paren): duplicate-grens schoon op 0.786 (alle huidige knoppen OK), related-grens toont overlap (exit 2) — het harnas meldt eerlijk wanneer de set of het model de klassen niet scheidt.
- **Memory-typering (`memory_type: feit|voorkeur|procedure|beslissing`).** De extractie typeert elke kandidaat (CrewAI/Cognee-les: verschillende kennistypes verouderen verschillend); `_memory.render` schrijft het veld, onbekende types vallen terug op `feit`. Bestaande memories zonder veld gedragen zich als `feit`.
- **Retrieval-scoring: relevance × recency × importance (`scripts/_rank.py`, Generative-Agents-patroon).** De judge kent bij capture een `importance` (1-5) toe; de recall-route herweegt memory-hits met een recency-verval (halfwaardetijd per memory_type: voorkeur 180d, feit/procedure 365d, beslissing 730d; vloer 0.6 zodat oud-maar-relevant nooit verdwijnt) en een importance-factor (0.9-1.1). De wiki-laag blijft ongewogen (gecureerd; stale-check bewaakt veroudering daar). Eval-hermeting op de Kluis-vault: identiek aan de nulmeting (recall@1 0.971, MRR 0.986) — geen regressie.
- **Derde retrievalsignaal: één-hop graafbuur-expansie (`_rank.one_hop_neighbor`, kb-recall/kb-retrieve).** Na de directe wiki-hits wordt de meest-verwezen wikilink-buur van die hits als extra entry toegevoegd (gemarkeerd `(buur)`), zodat de evidence pack een coherente kennisbuurt wordt in plaats van losse hits. Buren verdringen nooit directe hits. Default aan in de UserPromptSubmit-hook; uit te zetten met `KB_RETRIEVE_EXPAND=0` of `"retrieve_expand": 0`.
- **Recall-eval-harnas (`scripts/kb-eval.py` + `kb-eval-set.example.json`).** Meet recall@1/3/5 en MRR van de retrieval-route (dezelfde hybride cosine|FTS5-route als de UserPromptSubmit-hook) tegen een persoonlijke eval-set van vragen met verwachte documenten (`<vault>/06-claude/kb-eval-set.json`). Per-type breakdown (single-hop, keyword, paraphrase, oblique, temporal, multi-hop), `--json` en `--verbose`, injecteerbare `hits_fn` voor tests. Zonder meting is elke retrieval-wijziging gevoelsmatig; draai dit voor en na elke wijziging aan drempels, embeddingmodel of ranking. Nulmeting op de Kluis-vault (35 vragen, qwen3-embedding:8b): recall@1 0.971, recall@3 1.0, MRR 0.986; sabotage-run (onzin-vragen) scoort 0.0, dus het harnas kan falen.
- **Bi-temporeel geldigheidsmodel voor memories (`scripts/_memory.py`).** Elke memory krijgt `valid_from` (event-tijd: wanneer het feit ging gelden; default = `created`) naast `created` (capture-tijd), en optioneel `valid_until` (sluiting). De sweep zet `valid_from` op de sessiedatum uit de transcriptnaam, zodat een laat geïmporteerd transcript een feit op zijn echte ingangsdatum plaatst. Superseden en expiren stempelen `valid_until` (oud feit gold tot het nieuwe inging, resp. tot de expires-datum). Geïnspireerd op Zep/Graphiti's temporele kennisgraaf (LongMemEval-gat van 15 punten tegen niet-temporele systemen), gemodelleerd in markdown-frontmatter plus sqlite — geen graph-database nodig.
- **Write-time invalidatie in de capture-sweep (`scripts/_reconcile.py`, Mem0-patroon).** Nieuwe kandidaat-memories worden op schrijfmoment gereconciled tegen de meest gelijkende bestaande memories (current + unverified): per buur beslist een LLM-seam tussen ADD (echt nieuw), SUPERSEDE (nieuw feit vervangt/weerlegt oud; oude memory wordt gesloten met `superseded_by` + `valid_until`) en NOOP (al afgedekt; kandidaat wordt niet geschreven). Fail-safe-to-ADD: een dode of onparseerbare judge is nooit destructief. Deterministische temporele guard: een kandidaat uit een ouder transcript kan een nieuwer feit nooit invalideren (beschermt `--all`-rebuilds). Drempel-interplay gedocumenteerd: dup-skip (>0.92) blijft vóór reconcile voor idempotentie; de reconcile-band is 0.75-0.92 (top-2 buren); de bestaande supersede-pass (0.85, current-only) blijft als vangnet. Heartbeat/samenvatting tellen `reconciled_superseded` en `reconcile_noop`.
- **Guardrails uit de adversariële verificatie (32-agent review op bovenstaande).** Vier gedragsregels die de eerste implementatie miste, elk met regressietest: (1) `supersede_pass` ordent nieuwer/ouder op event-tijd (`valid_from`, fallback `created`) zodat een laat gecaptured oud feit een nieuwer feit niet kan sluiten met een geïnverteerd geldigheidsinterval; (2) de dedup is era-bewust (`_dup_skip`): een her-assertie van een eerder gesloten feit met latere `valid_from` (flip-back: "Jim zoekt weer een baan") is géén duplicaat en bereikt de reconcile-laag, terwijl her-captures uit hetzelfde tijdperk duplicaat blijven; (3) een kandidaat die zelf `unverified` landt mag geen `current` memory superseden (quarantaine sluit geen geverifieerde kennis; de supersede-pass pakt het paar op zodra beide current zijn), en een NOOP-verdict tegen een unverified buur telt niet; (4) `set_status` schrijft replacement-waarden literal (lambda i.p.v. string-replacement; geen `re.PatternError` op backslashes) en de expire-pass is fail-soft gewrapt. Bekende, gedocumenteerde beperking: een tegenspraak die >0.92 embedt tegen een open memory wordt als duplicaat geskipt — prijs van LLM-vrije idempotentie.
- **Provenance-lint (`scripts/kb-lint.py` + doctor-sectie 13d).** Valideert dat elk wiki-artikel in `02-wiki/` herleidbare sessie-herkomst heeft: minstens één resolvende `[[raw-sessie-...]]`-wikilink naar `01-raw/sessies/` of `08-archive/`. Drie finding-types: `missing` (geen enkele sessieverwijzing), `dangling` (dode wikilink), `path-only` (herkomst alleen als backtick-pad of proza, onzichtbaar voor backlinks en de kennisgraaf). Exit-conventie 0/1/2 (schoon/fout/waarschuwingen), `--json` voor machine-leesbare uitvoer; `doctor.sh` rapporteert de samenvatting als PASS/WARN. Rationale: een gecompileerd artikel zonder werkende link naar zijn raw-sessie is niet auditeerbaar — een hallucinatie tijdens destillatie wordt dan een duurzaam "feit" dat nooit meer tegen de bron te checken is.
- **Per-kernpunt sessie-herkomst in template en `/wiki` (`templates/tpl-wiki-artikel.md`, `commands/wiki.md`).** De `## Sessie-herkomst`-sectie krijgt een verplicht, machine-leesbaar formaat: `- <kernpunt, kort>: [[raw-sessie-YYYY-MM-DD-slug]]` — herkomst per claim in plaats van per artikel, altijd als wikilink (nooit backtick-pad). `/wiki` legt de koppeling op destillatiemoment (stap 4), valideert direct met kb-lint (stap 4.5), en bewaart bestaande herkomst-regels bij rewrites (stap 3.5). `## Bronnen` is voortaan exclusief voor externe bronnen (APA7).
- **Idempotent-veilige setup/upgrade (`setup.sh`, `scripts/_migrations.py`).** `setup.sh` is nu veilig om opnieuw uit te voeren voor zowel nieuwe als bestaande vaults: het ververst de tooling (scripts, templates, commands) zonder user-data te overschrijven of aanpassingen te verliezen. Idempotent via schema-version-stamp `<vault>/.claude/.kennisbank-schema-version` (v0.9.0), bewust los van de `.kennisbank-version` release-tag-stamp van de upgrade/contribute-skills.
- **Volledige hookset-registratie via `register-hooks.py --manifest` (`scripts/register-hooks.py`).** Registreert niet langer slechts twee retrieval-hooks, maar de volledige set: SessionStart (build-embed-index, distill-notify, build-kb-index, sweep-launch), SessionEnd (archive-transcript), UserPromptSubmit (kb-retrieve), en PreToolUse matcher WebSearch|WebFetch (kb-presearch). Alle hooks samen in één atomaire operatie.
- **Interpreter-aware hook-registratie (`scripts/register-hooks.py`).** Detecteert het platform en gebruikt `py -3` op Windows, `python3` elders; een self-heal op stale paden behoudt de originele interpreter zodat opnieuw registreren het platform niet verwisselt.
- **`scripts/_migrations.py` version-stamp + runner.** Beheert `<vault>/.claude/.kennisbank-schema-version` (apart van de upgrade-skill's `.kennisbank-version` release-tag-stamp), voert version-gated migraties uit (momenteel: geheugen-dirs, volledige hookset, toggle-migratie), en houdt de vault actueel over releases. De `kennisbank-upgrade`-skill delegeert z'n deploy nu aan `setup.sh` zodat upgrades de hooks/migraties/deps krijgen. Fail-soft per migratie; alles draait bij setup en upgrade.
- **Settings-migrate (`scripts/_settings.py.migrate()`).** Aanvullende helper voor het stellen van ontbrekende toggle-defaults in `kennisbank-settings.json`, inclusief backward-compatibility voor oude installs.
- **Learnings-file standaard AAN (`CLAUDE.md.template`, `commands/sessielog.md`, `POST-INSTALL.md`).** De `LEARNINGS_FILE`-regel is nu een actieve, ongecommente default-regel (`LEARNINGS_FILE=~/Claude/learnings.md`) i.p.v. een fenced voorbeeld; comment de regel uit of verwijder 'm om uit te zetten. `/sessielog` leest deterministisch de eerste ongecommente `LEARNINGS_FILE=`-regel, expandeert `~`, en maakt het bestand aan als het ontbreekt. Voorheen werd de stap stil overgeslagen als de regel in een code-fence stond. Complementair aan de automatische `09-memory/`-laag.
- **Hybrid wiki-recall in UserPromptSubmit-hook (`scripts/kb-recall.py`, `scripts/kb-retrieve.py`).** Dual-gate cosine|FTS5 + cosine-fallback — exacte termen vinden nu ook wiki-artikelen. Eval-helper `scripts/eval-wiki-recall.py` demonstreert before/after via `has_fts_match` + `wiki_hits`.
- **Cross-memory onderhoud v2 (`scripts/memory-sweep.py` + `scripts/_maintenance.py`).** De sweep draait na elke capture-loop drie onderhoudspassen: supersede (nieuwer spreekt ouder tegen → status superseded + link), 2e-lijn-hercontrole (her-judge current → retract bij non-current), en cluster-promotie (markeer `promote_candidate: true` voor /wiki bij ≥2 verwante buren). Gegate op `memory_capture`, fail-soft per pass; samenvatting in de heartbeat (`superseded`, `rechecked_retracted`, `promote_marked`).
- **Presearch hook (`scripts/kb-presearch.py`, PreToolUse).** Injecteert geheugen+wiki voor WebSearch/WebFetch vóór externe zoekactie (matcher `WebSearch|WebFetch`), niet-blokkerend, gegate op `memory_recall`.
- **CC transcript-archief (`scripts/archive-transcript.py`, SessionEnd-hook).** Archiveert elk transcript naar `01-raw/transcripts/`, fail-open en idempotent. Overleeft `cleanupPeriodDays`.
- **`/destilleer`-commando + `scripts/distill-notify.py` (SessionStart).** Piggyback-destillatie: melding van openstaande transcripts plus een commando dat ze via `import-cc-history.py --source` naar `/wiki` ketent. Watermark in `.distilled`.
- **`import-cc-history.py --source <dir>`.** Importeert een platte transcript-archiefmap.
- **Settings-store (`scripts/_settings.py`, `kennisbank-settings.json`).** Vier achtergrond-automatieken (auto-archive, distill-notify, embed-index, daily-graphify) zijn individueel aan/uit via een platte JSON-store. Gedeelde `get/set/init`-helper plus CLI; enige lezer/schrijver, geen key-drift.
- **`/kennisbank:settings`-commando.** Toont de toggles met huidige staat en zet ze aan/uit (genamespacet, deployt naar `~/.claude/commands/kennisbank/settings.md`).
- **Settings-bootstrap in `setup.sh` en de `kennisbank-upgrade`-skill.** Verse setup schrijft defaults (of vraagt interactief); upgrade vraagt ontbrekende toggles uit.
- **Memory-toggles (`memory_capture`, `memory_recall`, default aan) + `09-memory/`-fundament.** Twee nieuwe opt-in-knopen voor automatische memory-extractie en -injectie; `_memory.py`, frontmatter-contract en settings-defaults zijn aanwezig.
- **Geheugen-recall (`scripts/kb-recall.py`, `scripts/kb-retrieve.py`-hook, SessionStart-indexbouw).** `kb-recall.py` injecteert additief memory-fragmenten (`09-memory/`) in de retrieval-hook; gegate op `memory_recall`. `build-kb-index.py` draait als extra SessionStart-hook naast `build-embed-index.py` om `kb-index.db` vers te houden.
- **Autonome capture-sweep + detached launcher (`scripts/memory-sweep.py` + `scripts/sweep-launch.py`, SessionStart).** `memory-sweep.py` orchestreert de extract -> dedup -> judge -> schrijf pipeline over pending transcripts. `sweep-launch.py` spawnt de sweep DETACHED (niet-blokkerend) met een single-flight lockfile, gevolgd door `build-kb-index.py` (sweep-voor-index-ordening); gegate op `memory_capture`; exit 0 fail-open.
- **Upgrade-backfill (eenmalig memory-sweep over transcript-archief).** De `kennisbank-upgrade`-skill draait bij upgrade naar deze versie eenmalig `memory-sweep.py --all` over de bestaande transcript-backlog (idempotent via dedup), na bevestiging als `memory_capture` aan staat. Voltooit het geheugen-subsysteem: rebuild-memory, health-doctor, backfill.
- **Lokale stdio MCP-server (`scripts/kb-mcp.py`, optioneel).** Exposeert geheugen + wiki als `recall`-tool aan lokale MCP-clients (Cursor, LM Studio, Claude Desktop) via stdio; read-only via `kb-index.db` en lokale Ollama-embeddings. Vereist eenmalig `pip install mcp`; zonder de dep meldt het script dit netjes en de rest van KennisBank (hooks, sweep) werkt onafhankelijk.

### Changed
- **Hooks gaten zichzelf op hun toggle.** `archive-transcript.py` (auto_archive), `distill-notify.py`-meldpad (distill_notify) en `build-embed-index.py` (embed_index) eindigen fail-open als hun toggle uit staat. De daily-graphify-batch in `sessielog`/`wiki`/`destilleer` respecteert `daily_graphify`.
- **`setup.sh` deployt nu ook genamespacede commands** (`commands/*/*.md`) met behoud van de subdir-structuur.
- **`setup.sh` en `register-hooks.py` volledig geïntegreerd voor idempotent upgraden.** Setup.sh voert `_migrations.py` uit na registratie van hooks, dus existing installs krijgen toggle-defaults en version-stamp in één stap. Oude upgrades hoeven alleen `bash setup.sh` opnieuw te draaien.

### Behaviour change
- **`auto_archive` is default UIT.** Bestaande installaties stoppen na deze update met automatisch archiveren tot `auto_archive` expliciet aan wordt gezet. De `kennisbank-upgrade`-skill vraagt dit actief uit. Reden: opt-in, conform de wens "kan inschakelen".
## [0.8.2] - 2026-06-22

Retrieval hooks are now registered automatically, closing the cold-cache footgun
where `/uitdaag`, `/brug`, and `/wiki` self-rewrite silently found nothing on a
fresh install.

### Added

- **`scripts/register-hooks.py`** -- an idempotent, non-destructive merger that
  registers KennisBank hooks in `~/.claude/settings.json`. Existing hooks,
  permissions, env, and other settings are preserved; re-running is a no-op; a
  stale script path self-heals; an unparseable settings file is refused rather
  than clobbered.
- **`setup.sh` registers the retrieval hooks**: `SessionStart` -> `build-embed-index.py`
  (warms the wiki embed cache) and `UserPromptSubmit` -> `kb-retrieve.py` (injects
  matching wiki snippets). Skip with `--no-hooks`.
- **`doctor.sh` check #13** verifies both hooks are registered, warning (never
  failing) when they are missing or the settings file is absent/unparseable.

## [0.8.1] - 2026-06-22

Slash-command launchers voor de lifecycle-skills en vault-pad-consistentie voor de
v0.8.0-commands.

### Added

- **`/kennisbank-upgrade`** en **`/kennisbank-contribute`** — slash-command launchers
  voor de gelijknamige lifecycle-skills, zodat upgrade en contribute direct als
  commando aanroepbaar zijn (de skills bleven anders alleen model-getriggerd).

### Changed

- **Vault-pad-resolutie in de v0.8.0-commands.** `wiki.md`, `reconcile.md`,
  `uitdaag.md`, `brug.md` en `sessiestart.md` roepen scripts nu aan via
  `VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"` in plaats van een hardcoded
  `~/KennisBank`-pad, in lijn met de repo-brede env-var-fix (PR #11) die deze
  nieuwere commands nog niet dekte. Een regressie-guard
  (`NoHardcodedVaultInCommandsTest`) bewaakt dit voortaan.

## [0.8.0] - 2026-06-21

Vault-onderhoud en denkgereedschap layer: self-rewriting `/wiki` with hybrid-autonomy
guards, contradiction detection and reconciliation, adversarial thinking tools, and
progressive context budgets.

### Added

- **Self-rewriting `/wiki` via `safe-edit.py`** (hybrid-autonomy edit engine). Guards
  every automated wiki rewrite by line-change count (`KB_EDIT_MAX_LINES`, default 20),
  heading removal, and deletion count (`KB_EDIT_MAX_DROP`, default 3). Edits that
  exceed any guard are held back and proposed for human review instead of being applied
  silently. (Similarity-based rewrite matching is handled by `find-similar.py` via
  `KB_REWRITE_THRESHOLD`, not by `safe-edit.py`.)
- **`scripts/find-similar.py`** — candidate match finder: returns the most
  semantically similar wiki articles for a query or article, powering `/wiki`'s
  de-duplication awareness.
- **`scripts/kb-search.py`** — query retrieval CLI: search the vault by
  natural-language query and return ranked results, usable standalone or wired into
  commands.
- **`scripts/conflict-scan.py`** — contradiction detection: compares wiki passage
  pairs and flags semantically similar but factually diverging claims. Threshold
  `KB_CONFLICT_SIM` (default 0.62).
- **`scripts/context-budget.py`** — progressive L0-L3 context layers: selects how
  much vault context to load at session start based on `KB_CONTEXT_LEVEL` (default
  1 = L1). L0 = bare minimum, L1 = default, L2 = extended, L3 = full.
- **`commands/reconcile.md`** (`/reconcile`) — surfaces contradictions detected by
  `conflict-scan.py` and produces a reconciliation audit trail.
- **`commands/uitdaag.md`** (`/uitdaag`) — adversarial thinking tool: challenges a
  claim or article for weak reasoning, missing evidence, or overgeneralization.
- **`commands/brug.md`** (`/brug`) — thinking tool: finds conceptual bridges and
  shared principles between two topics or articles.

### New env vars

| Variable | Default | Controls |
|----------|---------|---------|
| `KB_EDIT_MAX_LINES` | `20` | Max lines changed per automated `/wiki` edit pass |
| `KB_EDIT_MAX_DROP` | `3` | Max non-blank lines deleted per automated edit pass |
| `KB_REWRITE_THRESHOLD` | `0.62` | Min cosine similarity for auto-apply of a rewrite |
| `KB_CONFLICT_SIM` | `0.62` | Min cosine to classify passage pair as potential contradiction |
| `KB_CONTEXT_LEVEL` | `1` | Progressive context layer loaded at session start (0-3) |

## [0.7.0] - 2026-06-21

Swappable embedding backend and push-based wiki retrieval, plus cost-gated
graph upkeep and two contribute-skill safeguards.

### Added

- **Swappable embedding provider (`scripts/_embeddings.py`).** Config-driven
  backend (`ollama` | `openai` | `voyage`) behind a single `embed()` interface,
  so the embedding model is a one-file choice instead of a code change. Cross-
  model-safe cache keying via `embed_id()` (provider:model) plus dimension; a
  model switch invalidates the cache by design. Length-guarded `cosine()`,
  shared cache. Config via `kennisbank-embed.json` or `KB_EMBED_*` env; API key
  referenced by env-var NAME only, never stored.
- **Prompt-time wiki retrieval hook (`scripts/kb-retrieve.py`).** UserPromptSubmit
  hook embeds the prompt once and injects the top-N matching wiki articles above
  a threshold as `additionalContext` — push, not pull. Fail-open always: any
  error, missing backend, empty cache, or trivial prompt yields no output and
  exit 0. Cheap pre-filter skips short/slash/trivial prompts before the embed.
  Tuned threshold 0.60 for `qwen3-embedding:8b` (real match 0.73-0.80,
  noise <= 0.51).
- **Embedding index builder (`scripts/build-embed-index.py`).** SessionStart
  hook that warms/refreshes the wiki embedding cache off the per-prompt path.
  Self-locating, incremental, prunes vanished files.
- **`kennisbank-embed.example.json`** — sanitized default (ollama/qwen3, empty
  `api_key_env`), deployed by `setup.sh` (skips if a live config is present
  unless `--force`).

### Changed

- **`scripts/semantic-tiling.py` refactored onto `_embeddings`** — shares the
  cache and keeps the same thresholds/behaviour.
- **`/sessielog` wires incremental `/graphify --update` into Step 2** (before
  auto-crosslink), so new article nodes exist when crosslinks are added — fixes
  the stale-graph "geen nodes gevonden in graph.json" miss.
- **`/sessielog` daily-batch graph gate (cost control).** `--update` runs only
  on the first session where `graph.json` is >20h old; every session still
  appends changed paths to `.needs-rebuild` for free. auto-crosslink runs only
  when `--update` ran. Self-pacing off `graph.json` mtime, no cron.
- **`CONFIGURATION.md`** section 4 rewritten for the `_embeddings.py` backend
  (`KB_EMBED_*`), the retrieval hook, and the index builder (`KB_RETRIEVE_*`).
- **`tests/test_setup_deploy.py`** asserts the new scripts and config deploy.

### Fixed

- **`kennisbank-contribute`: branch-first gotcha.** Documents the failure mode
  where contribute edits committed to local `$DEFAULT` make a branch-off-DEFAULT
  PR show no diff and leave `$DEFAULT` ahead of origin with PR-bound commits a
  stray push would leak — plus the recovery (branch at HEAD, reset `$DEFAULT`
  to origin) and the rule.
- **`kennisbank-contribute`: localization auto-skip.** The scan now normalizes
  deploy-localized path/vault-name rewrites back to portable form and re-diffs;
  pure-localization files (symmetric `+N -N` diffstat) are skipped, so a
  contribute run over a long-deployed vault no longer surfaces every path-
  localized file as a candidate (which "default: all" would ship as a broken,
  path-leaking PR).

## [0.6.1] - 2026-06-20

Tooling self-update: the lifecycle skills now manage every skill, not just
autoresearch. Plus a test-coverage tightening.

### Changed

- **Skills deploy map generalized to `skills/*/`.** `kennisbank-upgrade` now
  refreshes every installed skill (including `kennisbank-upgrade` and
  `kennisbank-contribute` themselves), backing up each skill it overwrites;
  `kennisbank-contribute` can isolate and PR improvements to any repo-known
  skill. Personal/local-only skills (no `skills/<name>/` counterpart in the
  repo at BASE) are gated out via `git cat-file -e` and are never contributed.
- `tests/test_setup_deploy.py` also asserts `autoresearch` is installed, making
  the deploy test a complete guard for all three skills.

## [0.6.0] - 2026-06-20

Multilingual embedding default, configurable tiling thresholds, a deploy-gap
fix, and two new lifecycle skills for upgrading a vault and contributing
improvements upstream.

### Added

- **`kennisbank-upgrade` skill** — upgrades a deployed vault to the latest
  official release tag: checks the upstream tag, shows the changelog, guards
  against clobbering local edits, backs up the current deploy, copies the new
  tooling, stamps `$VAULT/.claude/.kennisbank-version`, and verifies with
  `doctor.sh`.
- **`kennisbank-contribute` skill** — isolates local tooling edits in a
  deployed vault (scripts, templates, commands, skill), filters out personal
  vault content, and opens an upstream PR.
- **`qwen3-embedding:8b` as the default embedding model** (multilingual, 119
  languages) with `nomic-embed-text` as the lighter English-only fallback via
  `OLLAMA_EMBED_MODEL`.
- **Configurable tiling thresholds** `TILING_THRESHOLD_ERROR` /
  `TILING_THRESHOLD_REVIEW`, with robust NL-decimal parsing and a safe fallback
  instead of a crash on bad input.

### Fixed

- **`setup.sh` now deploys `scripts/*.sh`**, so `doctor.sh` ships with every
  install instead of relying on a manual copy.
- **`doctor.sh` respects `OLLAMA_EMBED_MODEL`** and reports the actual default
  (`qwen3-embedding:8b`) instead of hardcoding `nomic-embed-text`.

## [0.5.0] - 2026-06-14

Second review round: regression tests + CI, configurable taxonomy, an env var that points every script at the vault, a documentation-drift sweep, and a code-duplication cleanup.

### Added

- **Test suite (stdlib `unittest`, no third-party dependency).** `tests/` covers `split_frontmatter`/`parse_frontmatter` (`test_frontmatter.py`), `slugify` (`test_slugify.py`), `categorize` (`test_categorize.py`), the `categories.json` loader (`test_categories_json.py`), the zip-slip/symlink guard (`test_zip_guard.py`), `_vaultpath` resolution (`test_vaultpath.py`) and the shared `_common.py` helpers (`test_common.py`). Hyphenated scripts are loaded via `tests/_loader.py`. Run with `python3 -m unittest discover -s tests`.
- **GitHub Actions CI** (`.github/workflows/ci.yml`): on every push and pull request it compiles all scripts (`python3 -m py_compile scripts/*.py`), syntax-checks the shell (`bash -n setup.sh scripts/doctor.sh`) and runs the unittest suite. Free for public repos, pure standard library, no install step.
- **Configurable taxonomy for `build-karpathy-index.py`.** The category rules, prefix hints, generic-tag set and "Overig/Other" labels load from a `categories.json` placed next to the script or in the vault root; the built-in set is the fallback. `categories.example.json` ships the current set as a documented template so an outsider can define their own categories without editing the Python.
- **`KENNISBANK_VAULT` environment variable** via the new `scripts/_vaultpath.py` (single `vault_root()` source of truth). `stale-check.py`, `semantic-tiling.py`, `intake-scan.py` and `doctor.sh` now resolve the vault through it instead of hardcoding `~/KennisBank`, with the same default. Point the whole script layer at another vault with one variable, e.g. `KENNISBANK_VAULT=/tmp/test python3 scripts/stale-check.py`. The `--dry-run` flag was added to `auto-crosslink.py`, the last writing script that lacked an escape hatch.
- `scripts/_common.py`: shared `slugify`, `_utcnow_iso`, `_today_iso` and `print_summary` helpers for the three importers.

### Changed

- **`build-karpathy-index.py` now uses the shared `_frontmatter.py` parser** instead of its own private frontmatter parser (and the optional PyYAML path). One parser, one regex (`_frontmatter.py`'s anchored `^---\s*$`), consistent with the rest of the script layer. Index and log output are unchanged. `categorize()` is untouched.
- **De-duplicated the three importers.** `slugify`, `_utcnow_iso`/`_today_iso` and the summary/dry-run print block were defined identically in `import-folder.py`, `import-claudeai-export.py` and `import-cc-history.py`; they now import from `scripts/_common.py`. Now-unused imports (`json`, `timezone`) were dropped where the dedup left them dangling. Behaviour is identical.

### Fixed

- **Documentation-drift sweep** of the six points found in the review: `AGENTS.md` "every check line ends in OK" corrected to the `[PASS]`/`[FAIL]` format, "four new slash commands" corrected to six, the stale `THRESHOLD_DAYS` reference replaced by the actual `--days` flag; `TROUBLESHOOTING.md` dropped the removed `ollama embed` CLI path in favour of the HTTP API; `POST-INSTALL.md` "four Python utility scripts" corrected to nine; `CONFIGURATION.md` replaced the brittle `setup.sh` line-number references with variable names.
- `scripts/semantic-tiling.py`: removed the unused `import subprocess` (leftover from the CLI era) and now skips the auto-generated `log.md` (in addition to `index.md`) so generated index content is no longer fed into the near-duplicate embeddings.
- `scripts/stale-check.py`: dropped the dead second date format (`%Y-%m-%dT%H:%M:%S`, unreachable because the value is sliced to `[:10]`) and the no-op `fmt[:len(fmt)]`.

## [0.4.0] - 2026-05-14

Release after a full multi-agent code review of v0.3.0. Two CRITICAL fixes (broken `semantic-tiling.py` and a silent `doctor.sh` false-green), four HIGH fixes (`setup.sh` hardening, importer security, frontmatter parser correctness), plus a quick-wins bundle.

### Added

- `setup.sh --force` (`-f`) flag. Default behavior is now no-clobber: existing scripts, templates, commands, skill files and `CLAUDE.md` are kept and reported (`behouden:`). With `--force` they are overwritten (`gekopieerd:`), with a loud warning when an existing customised `CLAUDE.md` is replaced.
- `scripts/_frontmatter.py`: shared helper with `split_frontmatter` and `parse_frontmatter`, used by `import-folder.py`, `stale-check.py` and `semantic-tiling.py`. Anchored multiline regex avoids the previous horizontal-rule false positive.
- `commands/sessielog.md` Stap 1 now invokes `scripts/build-karpathy-index.py` so the Karpathy index in `02-wiki/log.md` is rebuilt after every sessie-log. Previously the script was installed by `setup.sh` but never called by any command.
- README now documents the four `/import` variants (`cc`, `claudeai <path>`, `folder <path>`, `cowork`) inline in the commands table.

### Changed

- `setup.sh` runs from any working directory via `SCRIPT_DIR` detection (was: required CWD to be the repo root).
- `setup.sh` enables `shopt -s nullglob` so empty source globs no longer fail under `set -e`.
- Importer filenames in `import-cc-history.py` and `import-claudeai-export.py` now include an 8-character stable-id suffix (derived from `session_id`/`uuid`, with `sha1` fallback). Same-day same-title sessions no longer overwrite each other silently. **Migration note**: re-running an import after upgrade produces new filenames; old files from earlier runs remain in `01-raw/sessies/` and may need manual cleanup or a one-time rename.
- `commands/import.md` removed a dead reference to a non-existent `/sessielog --force` flag.
- `templates/tpl-wiki-artikel.md` default status is now `concept` (was `actief`), matching the "bij twijfel: status concept" rule in `commands/wiki.md`.
- `scripts/build-karpathy-index.py` emits `## [YYYY-MM-DD] OPERATION | Title` (was `SESSION`), aligning the script with README, `POST-INSTALL.md`, `CHANGELOG.md` and the module docstring.

### Fixed

- **CRITICAL** `scripts/doctor.sh` now verifies all six installed commands (`sessielog`, `wiki`, `intake`, `stale`, `sessiestart`, `import`). Previous versions checked only four and silently reported PASS when `sessiestart` or `import` failed to install. Doctor's PASS count grows from 32 to 34.
- **CRITICAL** `scripts/semantic-tiling.py` uses the Ollama HTTP API (`POST http://localhost:11434/api/embeddings`) instead of the removed `ollama embed` CLI subcommand. The previous implementation always returned `None` on current Ollama releases, producing zero near-duplicate matches without any error.
- **HIGH** `scripts/import-claudeai-export.py` validates every zip member before `extractall`. Absolute paths, `..` traversals and symlink-typed entries (`S_IFLNK`) are rejected; a malicious zip yields a clean `[error]` line on stderr with exit code 2 instead of a Python traceback.
- **HIGH** Frontmatter parsers in three scripts no longer truncate body content at a `---` horizontal rule. Anchored regex `^---\s*$` (multiline) replaces the previous `text.find("\n---", 3)` pattern.
- **HIGH** `scripts/intake-scan.py` boolean was `or` where `and` was intended in `detect_type`. Binary files (`.exe`, `.zip`, etc.) no longer fall through to `read_text` attempts.
- `AGENTS.md`, `POST-INSTALL.md`, `CONFIGURATION.md` docs-sync: "four global slash commands" updated to "six"; obsolete "once `--yes` is merged" qualifier dropped (already merged in 0.2.0); a stale `THRESHOLD_DAYS` discrepancy callout removed from `CONFIGURATION.md`.
- `POST-INSTALL.md` em dashes converted to hyphens (project style: no em dashes).
- `.gitignore` covers `graphify-out/`, `.venv/`, `.idea/`, `.vscode/`, `*.egg-info/`.

### Background

This release packages ten commits from a single review-and-fix pass driven by a multi-agent code review pipeline. The doctor false-green and the broken `semantic-tiling.py` are the two findings users were most likely to hit silently on a fresh install. The importer security fix protects against malicious zip exports (low real-world risk for trusted exports, but the script accepts arbitrary `--input`). The frontmatter parser unification eliminates a class of silent body-truncation bugs that would only show up on long-form wiki articles containing horizontal rules.

## [0.3.0] — 2026-05-09

### Added

- `scripts/build-karpathy-index.py` builds `02-wiki/index.md` and `02-wiki/log.md` in the format that Understand-Anything's `parse-knowledge-base.py` requires (`## Section` headings + `[[wikilink]]` rows for index, `## [YYYY-MM-DD] OPERATION | Title` rows for log). It scans `02-wiki/` frontmatter (using PyYAML when available, with a minimal fallback parser) and clusters articles into 5–12 categories via, in priority order: a `category` frontmatter field, the first non-generic tag, or the `wiki-<domain>-...` filename prefix. `wiki-memory` types are pinned to a trailing `Memory-snapshots` section. Log entries come from `01-raw/sessies/raw-sessie-YYYY-MM-DD-*.md` filenames, with titles read from frontmatter when present. Flags: `--dry-run`, `--force` (writes `.bak` before overwrite), `--vault-root`, `--wiki-dir`, `--sessies-dir`. Refuses to overwrite without `--force`; honours dry-run.
- README and POST-INSTALL document the optional `/understand-knowledge` (Understand-Anything plugin) workflow as Step 8: install plugin, build index, run skill, browse dashboard. Existing graphify integration stays unchanged; the two are complementary (graphify uses semantic embeddings + hyperedges, Understand-Anything uses wikilinks + per-batch LLM analysis with categorised layers and a guided tour).

### Changed

- `POST-INSTALL.md` step numbering shifted: graphify stays at Step 7, the new knowledge-graph dashboard step is Step 8, autoresearch is Step 9, backfill is Step 10.

### Background

The integration grew out of a hands-on test of Understand-Anything against a real KennisBank vault. The detector requires `index.md` and `log.md` and does not generate them itself; `/wiki` does not write a centralised index either. `build-karpathy-index.py` closes that gap so users do not run into the same `Not a Karpathy-pattern wiki` error during their first `/understand-knowledge` invocation.

## [0.2.0] — 2026-05-08

### Added

- `AGENTS.md`, `TROUBLESHOOTING.md`, `POST-INSTALL.md`, `CONFIGURATION.md`, `OBSIDIAN.md` — install, troubleshooting, post-install walkthrough, configuration reference, Obsidian setup.
- `scripts/doctor.sh` — 12-check health verifier for vault, scripts, templates, commands, skill installation.
- `commands/import.md` (`/import` slash command) plus three importers: `scripts/import-cc-history.py`, `scripts/import-claudeai-export.py`, `scripts/import-folder.py` (with `--list-cowork-candidates`).
- `commands/sessiestart.md` (`/sessiestart` slash command) — briefing flow at session start.
- `setup.sh` flags: `--yes`, `--no-commands`, `--no-skill`, `--help` for non-interactive install.

### Fixed

- Documentation discrepancies surfaced by the publish-check: `THRESHOLD_DAYS` removed (never existed), `MIN_CONFIDENCE` and `MAX_NEW_LINKS` documented, `LEARNINGS_FILE` clarified as a convention not a config, doctor's Python warning relaxed, README numbering repaired.

## [0.1.0] — 2026-04-26

### Added

- Initial release. Core slash commands (`/sessielog`, `/wiki`, `/intake`, `/stale`), four utility scripts (`auto-crosslink.py`, `intake-scan.py`, `semantic-tiling.py`, `stale-check.py`), session-log and wiki-article templates, vault scaffolding via `setup.sh`, `/autoresearch` skill, `CLAUDE.md.template`.

[Unreleased]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.14.0...HEAD
[0.14.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.12.2...v0.13.0
[0.12.2]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.12.1...v0.12.2
[0.12.1]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.12.0...v0.12.1
[0.12.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.8.2...v0.9.0
[0.8.2]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.6.1...v0.7.0
[0.6.1]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.6.1
[0.6.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.6.0
[0.5.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.5.0
[0.4.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.4.0
[0.3.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.3.0
[0.2.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.2.0
[0.1.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.1.0
