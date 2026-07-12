---
id: TASK-28
title: Graphify-scope terugbrengen naar 02-wiki-only
status: Done
assignee: []
created_date: '2026-07-12 09:53'
updated_date: '2026-07-12 10:04'
labels:
  - graphify
  - tooling
  - scope
dependencies: []
ordinal: 40000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
De dagelijkse graphify-batch draait feitelijk `/graphify $VAULT --update` (hele vault: 02-wiki 1103, .claude 899, 03-projecten, 04-templates, CLAUDE.md = 2062 nodes), terwijl het artikel `graphify-kennisgraaf-tool` claimt dat de scope bewust beperkt is tot 02-wiki. Gebruiker koos: realiteit gelijkmaken aan de artikel-intentie (pure distilled-kennis-graaf, geen tooling-ruis).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Command-sources commands/sessielog.md, commands/wiki.md, commands/destilleer.md: graphify-invocatie gewijzigd van $VAULT naar $VAULT/02-wiki
- [x] #2 Wijziging gedeployed naar ~/.claude/commands (beide copies in sync)
- [x] #3 Artikel graphify-kennisgraaf-tool gecorrigeerd: scope=02-wiki feitelijk juist, en mechanisme voor bronbescherming toegevoegd (graphify detect sensitivity-skip, niet scoping)
- [x] #4 graph.json opnieuw gebouwd scoped op 02-wiki (~261 nodes, geen .claude-nodes)
- [x] #5 auto-crosslink gedraaid op de nieuwe graph
- [x] #6 kb-lint schoon (exit 0)
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Graphify-scope teruggebracht naar 02-wiki-only. commands/sessielog.md: 3 `/graphify $VAULT --update` occurrences → `/graphify $VAULT/02-wiki --update` (+scope-toelichting), gedeployed naar ~/.claude/commands via copy_force-conventie. Artikel graphify-kennisgraaf-tool gecorrigeerd: scope=02-wiki feitelijk juist gemaakt, en de echte bronbescherming toegevoegd (graphify detect _SENSITIVE_DIRS/_SENSITIVE_PATTERNS skipt 05-bronnen, niet de scoping). graph.json herbouwd: 2062 whole-vault nodes → 1106 pure 02-wiki nodes / 1248 edges / 90 communities; 976 non-02-wiki nodes (.claude 899 etc.) gepruned. kb-lint exit 0.

Twee path-format valkuilen onderweg (beide opgelost): (1) build_merge prune_sources matcht op source_file-string; absolute paden matchen niet tegen graph.json's vault-relatieve forward-slash source_file → 0 gepruned. (2) Extractie-subagents schrijven ABSOLUTE source_file ondanks relatieve instructie; die ontsnapten aan de 02-wiki-prune en werden per abuis als "non-02-wiki" verwijderd. Fix: source_file normaliseren naar 02-wiki/<naam> vóór merge, en NOOIT prune_sources meegeven die de net-ingevoegde nodes' source_file bevatten (self-prune).
<!-- SECTION:FINAL_SUMMARY:END -->
