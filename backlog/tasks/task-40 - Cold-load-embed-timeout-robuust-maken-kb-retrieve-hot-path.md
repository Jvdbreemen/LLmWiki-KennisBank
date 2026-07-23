---
id: TASK-40
title: Cold-load embed-timeout robuust maken (kb-retrieve hot path)
status: Done
assignee: []
created_date: '2026-07-23 21:33'
updated_date: '2026-07-23 21:42'
labels:
  - hook
  - performance
  - embeddings
  - retrieval
dependencies: []
modified_files:
  - scripts/_embeddings.py
  - scripts/kb-retrieve.py
  - tests/test_kb_retrieve_wiki.py
  - tests/test_kb_retrieve_memory.py
  - tests/test_injection_provenance.py
priority: high
ordinal: 52000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
UserPromptSubmit-hook kb-retrieve.py timet af op 25s bij de eerste prompt van een sessie: qwen3-embedding:8b (8GB) is cold (build-embed-index draait incrementeel en laadt het model niet als niks veranderde), en kb-retrieve kan dubbel embedden (wiki faalt -> qvec None -> memory doet 2e embed) tot ~40s. Harness kilt op 25s en gooit de context weg. Warm embed = 0.45s gemeten; cold-load is inferentie (niet geforceerd gemeten, maar het first-prompt-only patroon is sterk). Fix lokaal (geen cloud, noord-ster): (1) embed EEN keer in main(), qvec doorgeven aan wiki+memory, bij None warm+bail; (2) hot-path timeout default 5s (sub-seconde noord-ster, niet <25s); (3) warm_async detached child laadt model voor volgende prompt, met sentinel-guard tegen pileup als Ollama down is; (4) child moet KENNISBANK_VAULT erven (CACHE_FILE roept vault_root() bij import). Canonical in repo scripts/, syncen naar Kluis deploy die de hook echt aanroept.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 kb-retrieve embed exact 1x per prompt; qvec doorgegeven aan wiki- en memory-blok
- [x] #2 Hot-path embed-timeout default 5s (config KB_RETRIEVE_TIMEOUT blijft override)
- [x] #3 Cold miss = geen injectie + geen block; hook blijft ruim onder harness-timeout
- [x] #4 warm_async laadt model detached voor volgende prompt; sentinel-guard voorkomt pileup bij Ollama-down
- [x] #5 Warm child erft KENNISBANK_VAULT zodat vault_root() bij import niet faalt
- [x] #6 Fix in canonical repo-scripts EN gesynct naar Kluis deploy; geverifieerd tegen deploy-pad dat de hook aanroept
- [x] #7 Fail-open contract intact: elke fout -> geen output, exit 0
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Hot path (kb-retrieve) embed nu exact 1x: qvec eenmalig in main() berekend, doorgegeven aan _wiki_block (signatuur +qvec, tuple-return weg) en _memory_block; dubbel-embed pad verwijderd. Timeout-default 5s (config KB_RETRIEVE_TIMEOUT override). Bij qvec None (cold/Ollama-druk): geen injectie, geen block, en emb.warm_async() vuurt een DETACHED child (_embeddings.py --warm) die het model laadt zodat de volgende prompt hot is. Sentinel-marker (.embed-warm.marker, 60s) voorkomt child-pileup bij Ollama-down; child erft env zodat vault_root() bij import resolvet. Fail-open intact. Getest tegen deploy-pad: cold-miss=exit 0/geen output/warm gevuurd, guard blokkeert 2e warm, --warm laadt qwen, happy-path 1 embed + injectie. Canonical repo-scripts gesynct naar Kluis deploy (identiek). Tests bijgewerkt naar nieuwe signatuur: 57 passed, 1 skipped. NB cold-load zelf is inferentie (warm gemeten 0.45s); fix is robuust ongeacht de oorzaak.
<!-- SECTION:FINAL_SUMMARY:END -->
