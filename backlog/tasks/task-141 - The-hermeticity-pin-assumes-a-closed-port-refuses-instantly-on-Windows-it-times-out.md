---
id: TASK-141
title: >-
  The hermeticity pin assumes a closed port refuses instantly; on Windows it
  times out
status: To Do
assignee: []
created_date: '2026-08-12 17:48'
labels:
  - tests
  - windows
  - reliability
dependencies: []
references:
  - tests/__init__.py
  - tests/test_session_start_status.py
  - scripts/_embeddings.py
priority: medium
ordinal: 135700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`tests/__init__.py` pins the embed and LLM endpoints to `http://127.0.0.1:1` and states the premise explicitly:

> 127.0.0.1:1 is used because nothing listens on port 1: the OS returns RST immediately (connection refused), so there is no timeout wait.

That is false on this machine. Measured with a plain `socket.connect` and a 2 s timeout:

| target | result | time |
| --- | --- | --- |
| `127.0.0.1:1` | TimeoutError | 2012 ms |
| `127.0.0.1:9` | TimeoutError | 2016 ms |
| `127.0.0.1:<freshly released ephemeral port>` | TimeoutError | 2014 ms |
| `localhost:<same>` | TimeoutError | 2018 ms |

Every closed loopback port drops the connection instead of refusing it, so changing the port number does not help — this is host policy (a firewall rule), not a property of port 1.

Consequences:

- Every test path that still attempts a connection pays the caller's full timeout instead of failing fast. The local suite runs ~5 minutes; part of that is waiting on nothing.
- Any assertion with a wall-clock budget is a latent flake. Concretely: adding a 100 ms `/api/ps` probe to `status_line` made `test_blijft_binnen_het_budget` measure 511 ms per call against its 250 ms budget, purely because the pinned endpoint times out rather than refuses. That test now stubs the probe, but the next one to touch a network seam will hit the same wall.
- CI (Linux) refuses instantly, so the suite behaves differently there than locally — the exact asymmetry TASK-21 introduced the pin to remove.

Directions to evaluate, cheapest first:

- Point the pin at a port that is bound-and-listening but immediately closes, e.g. a `socketserver` fixture started once per session. A live socket cannot be dropped by the firewall.
- Or stop relying on network behaviour at all: make the seam injectable and stub `_http_json` / `urlopen` in the shared fixture, so no test ever opens a socket.
- Whichever wins, `tests/__init__.py`'s comment must state what was measured rather than what was assumed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The dead-endpoint premise is either made true (a target that refuses or answers instantly, verified by measurement on Windows and Linux) or removed in favour of stubbing the seam
- [ ] #2 tests/__init__.py's comment states the measured behaviour, not the assumed one
- [ ] #3 A test with a wall-clock budget that touches a network seam behaves the same on CI and on Windows
- [ ] #4 python -m pytest tests -q is green, and the local wall-clock runtime is recorded before and after
<!-- AC:END -->
