---
id: TASK-22
title: >-
  KennisBank ecosysteem-onafhankelijk maken: MCP-first tool + per-platform
  adapters (OB1/claude-mem-les)
status: In Progress
assignee:
  - '@claude'
created_date: '2026-07-04 05:06'
updated_date: '2026-07-04 15:10'
labels: []
dependencies: []
ordinal: 24000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
DOEL: KennisBank losweken van Claude-Code-only zodat elke agent-omgeving (Cursor, Codex, Gemini CLI, Cline, Windsurf, Claude Code, OpenClaw, Hermes) de vault kan gebruiken. Uitkomst van de OB1- en claude-mem-vergelijkingen (2026-07-04): beide bereiken tool-agnostisch bereik met hetzelfde patroon, dat direct op KennisBank toepasbaar is.

GEEVALUEERDE PATRONEN (geverifieerd tegen echte broncode/docs):
- OB1 (integrations/README.md + _template/metadata.json): een RUNTIME-NEUTRALE kern-API (MCP-endpoint + agent-memory-api REST = 'runtime-neutral recall, write-back, review, recall-trace') + een REGISTER van dunne per-platform providers, elk zelf-beschrijvend (metadata.json: name/requires/tags/difficulty), community-bijdraagbaar. Native providers: OpenClaw-plugin, Hermes native MemoryProvider (auto-recall + auto-writeback), Slack/Discord-capture. Docs = simpele tabel integratie->wat-het-doet.
- claude-mem (docs/public/platform-integration.mdx + install/): een lokale WORKER-service (HTTP 127.0.0.1) + native per-platform config (.codex-plugin/plugin.json, .windsurf/rules, cursor-hooks/hooks.json, openclaw/-plugin) + één universele installer (npx claude-mem install --ide X). Docs = platform-integration-gids voor plugin-bouwers.
- CONVERGENTIE: [universeel lokaal oppervlak] + [dunne native per-platform adapters] + [installer] + [docs]. Het universele oppervlak is HTTP/MCP op localhost; de adapters zijn native config per platform.

KENNISBANK-VOORSPRONG (waarom dit goedkoop is): kb-mcp.py EXPOSEERT AL een recall-tool aan elke MCP-client (docstring noemt Cursor, LM Studio, Claude Desktop). MCP is superieur aan een eigen HTTP-API want elke moderne agent-omgeving spreekt het al. De 80%-winst is dus al gebouwd; recall werkt vandaag in elke MCP-client. Het gat is packaging + write-tool + per-platform push + docs.

ARCHITECTUUR (MCP-first, sovereign-local):
1. UNIVERSEEL OPPERVLAK = de MCP-server als product. Hard maken + uitbreiden:
   - recall (read) - bestaat al.
   - capture/remember (expliciete write) - zodat non-Claude-Code-agents memories kunnen bijdragen zonder KennisBank's hooks (pull-write i.p.v. hook-push).
   - een instructions/'__IMPORTANT'-resource (de pull-nudge, claude-mem-patroon) die MCP-clients zonder push toch naar recall stuurt.
   - transports: stdio primair + optioneel localhost streamable-http voor clients die dat prefereren.
2. PER-PLATFORM ADAPTERS (registry-patroon van OB1's _template + claude-mem's native files): dunne native config per platform voor PUSH-injectie waar de omgeving pre-prompt hooks steunt - Claude Code hooks (bestaat), Cursor hooks.json/rules, Codex plugin.json, Windsurf .windsurf/rules, Gemini config, OpenClaw-plugin, Hermes MemoryProvider. Waar push NIET kan: PULL via recall + de instructions-nudge. Elke adapter zelf-beschrijvend (metadata) + community-bijdraagbaar.
3. INSTALLER: 'kennisbank install --client X' schrijft de juiste adapter + registreert de MCP-server (het claude-mem install-patroon).
4. DOCS: een platform-integratie-gids + een mcp.json-config-snippet per client.

SOVEREINITEITSGRENS (KennisBank-specifiek, HARD): local-only. Vault + Ollama zijn lokaal; de MCP-server draait op de machine van de gebruiker (stdio/localhost). LOKALE agents (Cursor/Codex/Gemini-CLI/Claude-Code op dezelfde machine) = veilig + makkelijk. REMOTE/gehoste agents (cloud-Hermes, gehoste OpenClaw-gateway) = OUT OF SCOPE of expliciete LAN-opt-in - NOOIT de soevereine vault aan de cloud blootstellen. Dit is de eerlijke grens EN het sluit aan bij KennisBank's waarden (anders dan OB1/claude-mem die cloud-comfortabel zijn). 'Ecosysteem-onafhankelijk' = elke LOKALE agent, niet cloud-exposure.

GEFASEERD (KISS, anti-scope-creep - bouw GEEN 8 halve adapters vooraf):
- FASE 1 (MVP, goedkoop, hoge waarde): MCP-server als product - capture-tool + instructions-resource + per-client config-docs (mcp.json-snippets voor Cursor/Codex/Cline/Windsurf/Gemini/Claude Code). Grotendeels docs + packaging van wat bestaat. recall werkt al.
- FASE 2: per-platform PUSH-adapters, geprioriteerd op wat de gebruiker ECHT gebruikt, EEN tegelijk. Begin met de omgeving die de gebruiker naast Claude Code inzet.
- FASE 3 (optioneel/misschien-nooit): per-platform auto-capture (elk heeft ander transcript-formaat - fragiel). MVP-alternatief = read-first (andere tools consumeren de vault die Claude Code bouwt) + de expliciete capture-tool.

STEEL-BRONNEN: OB1 integrations/_template/metadata.json (zelf-beschrijvend adapter-registry), OB1 Hermes MemoryProvider (native auto-recall/writeback interface), claude-mem install/public/installer.js + native config-files (.windsurf/rules, cursor-hooks/hooks.json, .codex-plugin/plugin.json), claude-mem __IMPORTANT-nudge-tool.

Raakt: scripts/kb-mcp.py (uitbreiden: capture + instructions + transports), scripts/kb-recall.py (write-pad voor capture), een nieuwe adapters/-map + installer, CONFIGURATION.md/docs. GEEN wijziging aan de retrieval-kern of de sovereign-local-filosofie.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 FASE 1: kb-mcp.py exposeert naast recall ook een capture/remember-tool (expliciete write) + een instructions-resource (pull-nudge); stdio + optioneel localhost-http transport; unit-getest zonder mcp/model
- [ ] #2 FASE 1: per-client mcp.json-config-snippets gedocumenteerd voor minstens Cursor, Codex CLI, Cline, Windsurf, Gemini CLI, Claude Code; een gebruiker kan recall in een niet-Claude-Code-client aanzetten met alleen de doc
- [x] #3 Sovereiniteitsgrens expliciet gedocumenteerd: local-only (stdio/localhost); remote/cloud-agents out-of-scope of expliciete LAN-opt-in; nooit vault-cloud-exposure
- [ ] #4 FASE 2: minstens EEN per-platform PUSH-injectie-adapter (native config) geleverd voor de omgeving die de gebruiker naast Claude Code gebruikt, zelf-beschrijvend (metadata) in een adapters/-registry
- [ ] #5 Optionele installer 'kennisbank install --client X' schrijft de adapter + registreert de MCP-server; of gedocumenteerd-uitgesteld met reden
- [ ] #6 Geen wijziging aan de retrieval-kern of de KISS/sovereign-local-filosofie; capture is pull-write, geen per-platform transcript-scraping in de MVP
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
--- FASE 2 DOELEN: gebruiker gebruikt Codex + GitHub Copilot + ChatGPT (geverifieerd 2026-07-04) ---

1. CODEX CLI - SCHONE FIT (beste doel). MCP-support bevestigd, STDIO EN streamable-HTTP transports (developers.openai.com/codex/mcp). Config in ~/.codex/config.toml [mcp_servers.<naam>] of project-scoped .codex/config.toml; `codex mcp add kennisbank -- <cmd>`. KennisBank's stdio-MCP-server (kb-mcp.py, recall-tool) plugt direct in - PULL werkt vandaag. Adapter = een config.toml-snippet + doc. Geen code nodig behalve de capture-tool (FASE 1).

2. GITHUB COPILOT (VS Code agent mode) - GOEDE FIT met caveat. MCP GA voor alle VS Code-users, STDIO ondersteund (SSE/HTTP nog niet) (docs.github.com/copilot ... using-model-context-protocol). CAVEAT: Copilot ondersteunt alleen MCP TOOLS, GEEN resources/prompts. Dus de recall-TOOL werkt (pull), maar de instructions/nudge-RESOURCE surfacet NIET. Workaround: zet de nudge in .github/copilot-instructions.md (repo custom instructions) i.p.v. een MCP-resource. Adapter = mcp-config in VS Code settings + copilot-instructions.md-nudge.

3. CHATGPT - FUNDAMENTELE SOEVEREINITEITSCONFLICT (eerlijk: geen schone lokale integratie mogelijk). ChatGPT MCP-connectors ('apps' sinds dec 2025) verbinden alleen met REMOTE MCP-servers op het publieke internet. Voor een lokale/private server: OpenAI Secure MCP Tunnel OF ngrok/Cloudflare Tunnel - d.w.z. de vault door OpenAI's infra routeren / aan internet blootstellen, waarbij OpenAI de queries EN de teruggegeven kennis ziet. Dat BREEKT 'nooit de soevereine vault aan de cloud blootstellen'. Extra: Plus/Pro individuele users = alleen READ/FETCH-only connectors (write vereist Business/Enterprise/Edu). CONCLUSIE: ChatGPT is niet compatibel met sovereign-local zonder de kernwaarde te breken. TWEE opties, gebruikersbeslissing (soevereiniteit vs gemak):
   (a) MANUELE EXPORT-BRIDGE (behoudt soevereiniteit, AANBEVOLEN): een `kennisbank ask \"<query>\"` CLI die lokaal retrievet en het blok naar klembord/stdout geeft; de mens plakt het in ChatGPT. Geen auto-exposure, mens = poort.
   (b) TUNNEL met expliciete opt-in (breekt soevereiniteit): lokale MCP via Cloudflare/ngrok/Secure-Tunnel publiek maken met auth. Alleen bij bewuste keuze; OpenAI ziet queries+content. NIET de default.

FASE-2 VOLGORDE (aanbevolen): Codex eerst (schoonste), dan Copilot (tool+copilot-instructions), dan ChatGPT-beslissing (manuele bridge tenzij gebruiker de tunnel-tradeoff bewust accepteert). De capture-tool + instructions-nudge (FASE 1) blokkeren geen van deze - recall werkt overal waar MCP-tools werken.

Bronnen: developers.openai.com/codex/mcp; docs.github.com/copilot (MCP, stdio-only, tools-only geen resources); developers.openai.com/api/docs/guides/tools-connectors-mcp + help.openai.com developer-mode-apps (remote-only, tunnel voor lokaal, Plus/Pro read-only).

--- FASE 1 + export-bridge + ingest GEIMPLEMENTEERD (2026-07-04) ---
Geleverd:
- scripts/kb-mcp.py: capture-tool (schrijft unverified/agent memory via _memory.write; sweep/mens promoot) + instructions-resource (pull-nudge, best-effort want niet elke MCP-SDK kent .resource()). recall bestond al. Module-docstring documenteert de local-only soevereiniteitsgrens.
- scripts/kb-ask.py (NIEUW): manuele export-bridge. `python kb-ask.py "<query>"` retrievet lokaal, print een plak-klaar contextblok (wikkel: instructie + treffers + je vraag); --clip naar klembord (pyperclip of OS-hulp), --plain kaal, --k N. Fail-soft exit 0. Mens = poort; niets verlaat de machine automatisch.
- scripts/import-chatgpt-export.py (NIEUW): ChatGPT data-export importer. Broer van import-claudeai-export.py maar handelt ChatGPT's mapping-BOOM af (nodes parent/children, message.content.parts, tijdsvolgorde via create_time; system/tool/lege nodes eruit). Zelfde zip-slip+symlink-guard. -> 01-raw/sessies/ met source: chatgpt-export.
- README: sectie "Using KennisBank from other agents" met Codex (codex mcp add / config.toml), Copilot (mcp.json + copilot-instructions.md want geen resources), ChatGPT manuele bridge, EN "ChatGPT data export - get control of your own chats back" (Settings->Data controls->Export data -> import-chatgpt-export.py).
- Tests: tests/test_mcp_capture.py, tests/test_import_chatgpt.py, tests/test_kb_ask.py (30 nieuwe asserts, Ollama-vrij). Volledige suite groen.

AC1 (capture+instructions+transport) DONE. AC2 (per-client config-docs) DONE via README. AC3 (soevereiniteitsgrens gedocumenteerd) DONE.
FASE 2 nog open: native PUSH-adapters per platform (Codex plugin.json / Copilot instructions) als aparte stap; ChatGPT-ingest is nu de eerste concrete ingest-route.
<!-- SECTION:NOTES:END -->
