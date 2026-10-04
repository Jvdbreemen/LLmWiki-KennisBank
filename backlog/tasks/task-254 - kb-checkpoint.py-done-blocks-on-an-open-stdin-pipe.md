---
id: TASK-254
title: kb-checkpoint.py --done blocks on an open stdin pipe
status: In Progress
assignee: []
created_date: '2026-10-04 13:03'
updated_date: '2026-10-04 20:33'
labels:
  - bug
  - checkpoint
dependencies: []
priority: medium
ordinal: 190600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
kb-checkpoint.py read stdin in main() (sys.stdin.buffer.read()) before parsing its subcommand whenever stdin was not a tty, so also for --done, --list and --register. An agent shell tool that passes a pipe which never closes (Claude Code Bash tool, 2026-10-04) made the script block forever before mark_done() ran: checkpoints stayed open and two Python processes hung. Observed via /sessielog step 6 (commands/sessielog.md:181); commands/checkpoint.md:50,57 call --done the same way. Workaround until deployed: run with </dev/null (POSIX) or < NUL (cmd).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 stdin is read only in PreCompact hook mode (no arguments)
- [x] #2 --done, --list, --register and --notify do not read stdin
- [x] #3 Test: --done with an open, never-closing stdin pipe finishes within seconds and closes the pending checkpoints
- [x] #4 An unrecognised argument neither reads stdin nor writes a hook-mode stub
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Fixed: stdin read moved into the PreCompact hook branch of main(). StdinHandlingTest reproduces the hang (red on main, 10s timeout) and passes now; hook mode still parses its payload. Targeted run: 188 passed; the one failure (test_opruimen_skill self-test, Windows path compare /tmp/x vs D:\tmp\x) also fails on clean main. Full suite not run: commit charge at 95%.

Copilot review on PR #180: (1) an unrecognised argument fell through into hook mode, read stdin and could hang or write a stub; main() now returns with a stderr note for any leftover argument, covered by test_unknown_argument_neither_blocks_nor_writes_a_stub (red before, green after). The installed PreCompact hook passes no arguments (register-hooks.py builds the bare script path), so hook mode is unaffected. (2) Task text translated to English per AGENTS.md.
<!-- SECTION:NOTES:END -->
