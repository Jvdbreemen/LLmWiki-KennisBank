---
id: TASK-254
title: kb-checkpoint.py --done blokkeert op een open stdin-pipe
status: In Progress
assignee: []
created_date: '2026-10-04 13:03'
updated_date: '2026-10-04 14:09'
labels:
  - bug
  - checkpoint
dependencies: []
priority: medium
ordinal: 190600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
kb-checkpoint.py leest in main() altijd eerst stdin (sys.stdin.buffer.read(), regel 183-185) zodra stdin geen tty is, ook bij --done, --list en --register. Een agent-tool die een pipe meegeeft die nooit sluit (Claude Code Bash-tool, 2026-10-04) laat het script eeuwig blokkeren voordat mark_done() draait: checkpoints blijven open, twee python-processen blijven hangen. Waargenomen via /sessielog stap 6 (commands/sessielog.md:181); commands/checkpoint.md:50,57 roept --done net zo aan. Werkaround: aanroepen met </dev/null (POSIX) of < NUL (cmd).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 stdin wordt alleen gelezen in de PreCompact-hookmodus (geen subcommando)
- [x] #2 --done, --list, --register en --notify lezen geen stdin
- [x] #3 Test: --done met een open, nooit sluitende stdin-pipe eindigt binnen enkele seconden en sluit de pending checkpoints
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Fixed: stdin read moved into the PreCompact hook branch of main(). StdinHandlingTest reproduces the hang (red on main, 10s timeout) and passes now; hook mode still parses its payload. Targeted run: 188 passed; the one failure (test_opruimen_skill self-test, Windows path compare /tmp/x vs D:\tmp\x) also fails on clean main. Full suite not run: commit charge at 95%.
<!-- SECTION:NOTES:END -->
