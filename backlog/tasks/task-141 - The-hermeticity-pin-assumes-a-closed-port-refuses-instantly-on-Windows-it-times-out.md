---
id: TASK-141
title: >-
  The hermeticity pin assumes a closed port refuses instantly; on Windows it
  times out
status: In Progress
assignee: []
created_date: '2026-08-12 17:48'
updated_date: '2026-08-13 18:35'
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
- [x] #1 The dead-endpoint premise is either made true (a target that refuses or answers instantly, verified by measurement on Windows and Linux) or removed in favour of stubbing the seam
- [x] #2 tests/__init__.py's comment states the measured behaviour, not the assumed one
- [x] #3 A test with a wall-clock budget that touches a network seam behaves the same on CI and on Windows
- [ ] #4 python -m pytest tests -q is green, and the local wall-clock runtime is recorded before and after
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## The fix

A socket that is BOUND AND LISTENING cannot be dropped by a firewall rule. `tests/__init__.py` now starts one on an ephemeral loopback port at import, accepts and immediately closes, and pins both endpoints at it. The TCP handshake completes against the backlog and the client sees a reset instead of a wait — same behaviour on Windows and on Linux. Fail-soft: if binding fails, the pin falls back to the old closed port, which is slower but still hermetic, and hermetic is the requirement.

`tests/test_hermetic_pin.py` measures the premise instead of asserting it in a comment: a bare socket connect, a urlopen, and `emb.embed` must each fail in well under a second. Measured: all four well inside their budgets, against 2012 ms before.

## The finding this uncovered, which is bigger than the timing

The first run of the new test failed on something else entirely: `KB_LLM_ENDPOINT` was `http://localhost:11434` — the real Ollama.

`~/.claude/settings.json` exports that variable for every session, because the KennisBank scripts need it for real work. The pin used `setdefault`, documented as "hermeticity by default, override by intent". The intent that actually reached it was nobody's: the pin never fired for the LLM seam on the machine where Ollama runs — the exact case TASK-21 added it for — while CI, which has no such variable, stayed pinned. The asymmetry the pin exists to remove, running the other way round, invisibly.

Now assigned rather than defaulted. The override is still there and is unambiguous: `KB_INTEGRATION=1` cannot be confused with a variable that also has a legitimate production meaning. Ambient configuration must not be able to switch off hermeticity.

**No test failed under the hardened pin** (1355 passed, 2 skipped). So nothing was actually depending on reaching a live model — the seams are mocked. The risk was latent, not realised, and is now closed.

## Runtime, honestly (AC#4)

    before   318.49s   1328 passed, 2 skipped
    after    327.64s   1355 passed, 2 skipped

Unchanged within noise, and the task's premise that "the local suite runs ~5 minutes; part of that is waiting on nothing" does not hold at suite level. The 2012 ms cost per connection is real, but few tests open a socket at all, so there is no measurable saving to claim. What the change actually buys is the two things that matter more than seconds: a wall-clock assertion now behaves the same on Windows and on Linux, and the hermeticity guarantee is no longer silently off.
<!-- SECTION:NOTES:END -->
