---
id: TASK-42
title: 'Transcript-stripper voor /destilleer: grote .jsonl subagent-verteerbaar maken'
status: Done
assignee: []
created_date: '2026-07-24 05:22'
updated_date: '2026-07-24 11:20'
labels:
  - destilleer
  - tooling
  - upstream
dependencies: []
references:
  - 'https://github.com/Jvdbreemen/LLmWiki-KennisBank/pull/52'
ordinal: 56000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
/destilleer compileert wiki-kennis uit gearchiveerde Claude Code transcript-.jsonl. Die transcripts zijn te groot om heel in context te lezen (waargenomen tot 11.9 MB / ~3M tokens), en de geimporteerde raw-sessielogs zijn bewust stubs (index naar de .jsonl, geen inhoud — zie wiki import-cc-history-stubs). Zonder gereedschap moet een agent elke run ad-hoc de .jsonl strippen.

Doel/waarde: een herbruikbare transcript-stripper die tool-payloads verwijdert (~10x kleiner), zodat grote sessies subagent-verteerbaar worden en /destilleer ze kan destilleren zonder de hoofdcontext te vullen. Plus command-guidance zodat de werkwijze (strip + subagent-fan-out) en de valkuilen (lage net-new door overlap met /sessielog; kb-lint --json om nieuwe artikelen schoon te bewijzen) vastliggen. Dit wordt upstream teruggegeven als feature via /kennisbank-contribute.

Ontwerp is met de gebruiker afgestemd: mechanische content->tekst-logica in een gedeeld importeerbaar helper-module, stripper als CLI naar stdout/scratch (niets naar de vault, respecteert de stub-opzet), subagent-fan-out als guidance (niet verplicht — kleine transcripts leest de agent inline).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Een herbruikbare helper produceert uit een Claude Code transcript-.jsonl platte conversatietekst met alleen user- en assistant-turns; thinking-, tool_use-, tool_result- en isSidechain-turns worden weggelaten.
- [x] #2 De strip-functionaliteit is beschikbaar als CLI die een transcript-pad of bare stem accepteert (stem resolvet tegen 01-raw/transcripts/) en de gestripte tekst naar stdout schrijft.
- [x] #3 De content->tekst-logica wordt gedeeld met import-cc-history.py zonder duplicatie; import-cc-history blijft functioneel identiek en de bestaande importer-tests blijven groen.
- [x] #4 Een test toont met een synthetisch transcript aan dat alleen user+assistant-tekst overblijft en dat thinking/tool_use/tool_result/sidechain wegvallen.
- [x] #5 commands/destilleer.md verduidelijkt dat raw-sessielogs stubs zijn (compileer de .jsonl, niet de stub) en beschrijft de strip + subagent-fan-out werkwijze voor grote of vele transcripts, plus dat destilleer zwaar overlapt met /sessielog (verwacht lage net-new, vermijd duplicaat-artikelen).
- [x] #6 commands/wiki.md stap 4.5 beschrijft kb-lint --json om een nieuw artikel schoon te bewijzen zonder globale exit 0 te forceren tegen pre-existing dangling artikelen.
- [x] #7 De nieuwe scripts volgen de repo-interpreter-conventie (python3-shebang) en worden door setup.sh naar de deploy gekopieerd.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
TDD op branch feat/transcript-stripper (basis origin/main 2c4def4).
1. Nieuw scripts/_transcript.py: extract_text(content) (verhuisd uit import-cc-history) + strip_to_text(jsonl_path) generator.
2. Test tests/test_strip_transcript.py eerst (synthetische jsonl: user-str, assistant thinking/text/tool_use, user tool_result, sidechain) -> RED.
3. Implementeer _transcript.py + scripts/strip-transcript.py (CLI -> stdout; stem resolvet tegen 01-raw/transcripts/) -> GREEN.
4. Refactor import-cc-history.py: from _transcript import extract_text; bestaande importer-tests groen houden.
5. Edit commands/destilleer.md (stub!=bron, Stap 3-bis strip+fan-out, Regel lage net-new/overlap sessielog) + commands/wiki.md (4.5 kb-lint --json).
6. Volledige testsuite groen. Dan /kennisbank-contribute voor PR naar origin (Jvdbreemen).
<!-- SECTION:PLAN:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Gemerged upstream via PR #52 (Jvdbreemen/LLmWiki-KennisBank, merge-commit 2cc700a, 2026-07-24). Lokale main ge-fast-forward naar de merge; feature-branch (lokaal + fork-remote) opgeruimd.

Geleverd: transcript-stripper die grote Claude Code .jsonl-transcripts subagent-verteerbaar maakt.
- scripts/_transcript.py: gedeelde jsonl->tekst-helpers (extract_text met include_tool_result-vlag, iter_turns, strip_to_text).
- scripts/strip-transcript.py: CLI pad-of-stem -> stdout, UTF-8 geforceerd (Windows cp1252-fix, door smoke gevangen), -o naar bestand.
- import-cc-history.py hergebruikt _transcript.extract_text (behavior-preserving).
- commands/destilleer.md: stub != bron, strip + subagent-fan-out, lage net-new/overlap /sessielog.
- commands/wiki.md: kb-lint --json om nieuw artikel schoon te bewijzen zonder globale exit 0.
- tests/test_strip_transcript.py: strip-semantiek + non-ASCII stdout-regressie.

Verificatie: volle suite 761 passed / 2 skipped (enige failure = lokale untracked research-doc, niet in PR); smoke echt OTGW-transcript 1.44 MB -> 58 KB (24.7x); feature groen op gemergde main.
<!-- SECTION:FINAL_SUMMARY:END -->
