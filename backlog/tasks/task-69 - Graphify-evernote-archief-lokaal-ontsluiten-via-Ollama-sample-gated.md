---
id: TASK-69
title: 'Graphify: evernote-archief lokaal ontsluiten via Ollama-sample (gated)'
status: To Do
assignee: []
created_date: '2026-07-25 15:21'
labels:
  - graphify
  - privacy
  - lokaal
dependencies:
  - TASK-67
priority: low
ordinal: 79000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Gebruiker heeft gekozen: evernote gaat de graaf in, maar uitsluitend met een lokale backend. Geen cloud, conform CLAUDE.md ("Lokaal, altijd").

Uitvoering: `--backend ollama`. Ollama draait (v0.32.3, localhost:11434) met gemma4:12b (11,9B Q4_K_M, completion+tools, 262k context) als extractiemodel en bge-m3 / qwen3-embedding:8b / nomic-embed-text voor embeddings.

Omvang: 14837 md, gemiddeld ~251 woorden (steekproef n=400, 1505 bytes gemiddeld) = ~3,7M woorden ~ 5,6M input-tokens. Dat is 12x het hele kern-corpus. Doorlooptijd op lokale hardware is onbekend en moet gemeten worden, niet geschat.

Twee risico's, los van kosten:
1. Clustering-verdrinking: 14837 nodes tegenover 139 wiki-nodes laat de Leiden-partitie communities vinden over e-mailbevestigingen in plaats van over kennis. Tegengif: --exclude-hubs <N> en --resolution <N>.
2. Ruis: directorynamen tonen dubbelen en lege titels ("(geen titel)", "(geen titel) (1)", identieke e-mailbevestigingen in drievoud). Ontdubbelen vóór extractie scheelt direct tokens en nodes.

BELANGRIJK - onjuiste aanname corrigeren: de final summary van TASK-28 en het wiki-artikel graphify-kennisgraaf-tool stellen dat `graphify detect` 05-bronnen overslaat via _SENSITIVE_DIRS/_SENSITIVE_PATTERNS. Geverifieerd op 2026-07-25: _SENSITIVE_DIRS = {.secrets, .gcloud, .aws, .ssh, secrets, credentials, .gnupg} en _SENSITIVE_PATTERNS dekt uitsluitend credential-bestanden (.env, .pem, id_rsa, .netrc, ...). 05-bronnen en evernote komen nergens in graphify.detect voor. Alleen expliciete scoping beschermt dit archief; er is geen automatisch vangnet.

Corpus-drempels van graphify detect: CORPUS_UPPER_THRESHOLD = 500.000 woorden, FILE_COUNT_UPPER = 500. Evernote overschrijdt beide ruim.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Sample van ~500 evernote-notities lokaal geëxtraheerd met --backend ollama; geen enkele aanroep naar een cloud-endpoint
- [ ] #2 Doorlooptijd en tokendoorvoer van de sample gemeten en vastgelegd, als basis voor de extrapolatie naar 14837 bestanden
- [ ] #3 Communities uit de sample beoordeeld op zinnigheid; oordeel expliciet vastgelegd voordat de volledige run start
- [ ] #4 Ontdubbeling toegepast op lege titels en identieke notities; aantal overgeslagen bestanden gerapporteerd
- [ ] #5 --exclude-hubs en --resolution afgestemd zodat wiki- en memory-communities niet verdwijnen in evernote-massa
- [ ] #6 Onjuiste claim over automatische 05-bronnen-skip gecorrigeerd in het artikel graphify-kennisgraaf-tool
- [ ] #7 Volledige run pas gestart na expliciete go op basis van de sample-meting
<!-- AC:END -->
