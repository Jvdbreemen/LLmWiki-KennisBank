---
id: TASK-199
title: >-
  SessionStart freshness gate is vault-global: a second client gets no notices
status: To Do
assignee: []
created_date: '2026-08-16 12:00'
updated_date: '2026-08-16 12:00'
labels:
  - bug
dependencies: []
ordinal: 167700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found while reviewing Eaves for multi-agent memory patterns (see
docs/research/eaves-memory-architecture.md). The defect is ours; asking their
question of our code is what surfaced it.

`kb-session-start.py` keeps one state file for the whole vault
(`state_path = runtime / STATE_NAME`, line 492) and gates on elapsed time
alone (`is_fresh`, line 256, `FRESHNESS_SECONDS = 300`). `_write_state` does
record which client last completed — and nothing reads that field.

The gate answers two different questions with one piece of state:

- *Has the maintenance work run recently?* Vault-global, and correctly so —
  the index needs rebuilding once no matter how many agents start.
- *Has THIS client been told what it needs to know?* Per client, and today
  answered with the wrong state.

Reproduction: start Claude Code, then start Codex within 300 s. The second
session returns at line 524 before the NOTIFICATIONS phase, so it receives no
`memory-notify` health warning, no `distill-notify` prompt, no
`kb-orientation` summary and no `git-upstream-check`. Nothing reports a
problem — the output is simply empty, which is indistinguishable from
"nothing to report", because silence is the designed success signal of every
one of those scripts.

The window is not hypothetical: three clients on one vault is the supported
configuration, and 300 s comfortably covers opening a second client after the
first.

TASK-79 already hit the neighbouring case and solved it for one script by
moving `kb-checkpoint.py --notify` in front of the gate, rather than by
fixing the gate.

Proposal: key the freshness state per client (a map of client -> completed_at
in the same file, or one file per client) so notifications are gated per
client, while the maintenance lock and the maintenance phase stay global.
Notifications are cheap reads; maintenance is not, and must not start running
once per client.

Also worth a measurement while the code is open: count how often a second
client starts inside a first client's window. The multi-client path has never
had a number pointed at it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A second client starting within FRESHNESS_SECONDS of a first receives the full NOTIFICATIONS payload
- [ ] #2 The MAINTENANCE phase still runs at most once per freshness window across all clients
- [ ] #3 The single-flight lock behaviour is unchanged; no client can start a second maintenance worker
- [ ] #4 A state file written by the old format is read without error (fail-open, treated as not fresh for other clients)
- [ ] #5 Tests cover: same client twice inside the window, two different clients inside the window, and a stale state file
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->
