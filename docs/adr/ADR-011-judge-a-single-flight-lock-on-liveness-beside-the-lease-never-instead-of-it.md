---
id: "ADR-011"
title: "Judge a single-flight lock on holder liveness beside the lease, never instead of it"
status: "Accepted"
date: "2026-09-11"
binding: true
gate: null
documents_shipped: false
verified_in: ["TASK-247"]
supersedes: []
superseded_by: null
format: "madr"
topics:
  - single-flight
  - locking
---

# ADR-011: Judge a single-flight lock on holder liveness beside the lease, never instead of it

## Context and Problem Statement

Every single-flight lock in this repository answers one question: does this lock
still represent a running worker? Two independent signals can answer it, and
they fail in opposite directions.

A **time lease** is what the holder proves by refreshing a timestamp. It is
deliberately not PID-based, because PID numbers are reused: a lock naming PID
30968 tells you nothing about whether the sweep still runs, only that some
process once had that number. Its weakness is the opposite case. A hard kill
never runs the context manager's `__exit__`, so the file survives and nothing
frees it until the full lease expires.

A **liveness probe** asks the operating system whether the named PID exists. Its
weakness is the reuse above, plus two of its own: `_common.pid_alive` answers
"dead" when it cannot tell, and on Windows reads a terminated process as alive
for as long as any handle to it remains open.

The sweep lock had only the lease. Measured in the owner vault on 2026-09-08 and
again on 2026-09-09: an orphaned lock named a PID that no longer existed, and
`sweep-launch.py` refused to spawn with "er draait al een sweep" until the file
was removed by hand. `STALE_SEC` is 3600, so each occurrence cost up to an hour
of skipped maintenance. The index lock (`index-launch.py`) had already solved
this; the sweep lock was the one that had not caught up.

## Decision Drivers

- The two signals must not be traded against each other; each covers the other's
  blind spot.
- Uncertainty must never free a live lock. A second concurrent worker is the
  failure this whole mechanism exists to prevent, and it is worse than a delay.
- The repository must not grow a third copy of the liveness probe. ADR-less but
  recorded in `_common.pid_alive`: an earlier task ended two divergent copies.

## Considered Options

1. Lease only (the status quo for the sweep lock).
2. Liveness only, replacing the lease.
3. Liveness beside the lease, with uncertainty falling back to the lease.

## Decision Outcome

**Option 3.** A lock no longer represents a running worker when EITHER the lease
has expired OR the holder is provably gone. Expressed as `is_free(lock) =
is_stale(lock) or is_orphaned(lock)`, and every caller that used to ask
`is_stale` asks `is_free` instead.

Three properties make this safe rather than merely faster.

**The probe judges only its own machine.** The lock token carries the hostname
alongside the PID and the randomness (`host:pid:random`). A PID number from
another machine says nothing locally, and on a vault living on a network share
or a sync folder, "that number is free here" would steal a live lock. A token
without a host, an unknown host, or a lock that cannot be stat-ed all fall back
to the lease alone.

**A dead PID frees a lock only once the lock is also old.** `PID_GRACE_SEC` is 5
seconds, the same guard and the same reason as `index-launch.py`. It absorbs a
probe that answers "dead" because it could not tell, the Windows zombie window,
and the clock skew that already makes `is_stale` a symmetric window. Five
seconds against the lease's 3600 leaves the gain intact.

**Faster detection obliges closing the reclaim race in the same change.**
`acquire_lock` has always judged, then unlinked, then created. That was
survivable while an orphan surfaced only after an hour, because two acquirers
were never realistically inside the window together. A probe that answers
immediately puts them there. `acquire_lock` therefore re-reads the token and
removes only the lock it just judged.

The probe itself is `_common.pid_alive`. Not a new one: on Windows it must go
through `OpenProcess` with `PROCESS_QUERY_LIMITED_INFORMATION` and
`GetExitCodeProcess`, because CPython translates every signal other than
`CTRL_C_EVENT` and `CTRL_BREAK_EVENT` into `TerminateProcess` — so
`os.kill(pid, 0)` there kills the process it is meant to ask about.

## Decision Contract

Binding on every single-flight lock in this repository:

1. A lock is judged free when the lease has expired or the holder is provably
   gone. Never on liveness alone.
2. The liveness judgement applies only when the token names this host.
3. A provably dead holder frees the lock only once the lock is older than the
   grace window.
4. Anything the probe cannot answer, an unparseable or hostless token, and an
   unreadable lock all fall back to the lease.
5. Reclaiming removes only the lock that was just judged, verified by re-reading
   the token.
6. Liveness is asked through `_common.pid_alive`. A second implementation is a
   defect, not an optimisation.

## Consequences

Good: an orphan left by a hard kill is reclaimed in seconds instead of up to an
hour, and `sweep-launch.py` stops reporting a dead holder as a running sweep.
The rule is one sentence and its failure direction is stated, so a future lock
can be checked against it without re-deriving the reasoning.

Bad: two mechanisms where there was one, and a grace constant that must stay
consistent with the lease. A lock whose holder exited but whose parent still
holds a handle is not reclaimed early on Windows; it waits out the lease, which
is the pre-existing behaviour and errs toward safety.

Not addressed: what kills the worker. The observed kills came from memory
pressure on the development machine, which is a separate matter from the lock.

## Related Decisions

- `_common.pid_alive` carries the record that an earlier task ended two
  divergent copies of the probe. This ADR makes that rule binding rather than
  incidental.
- TASK-246 (partial status writes) shares the incident but not the mechanism: it
  is about a killed run being indistinguishable from a run that did nothing.

## References

- `scripts/_sweepstate.py` — `is_orphaned`, `is_free`, `PID_GRACE_SEC`, `_owner`
- `scripts/index-launch.py` — the prior art this decision generalises
- `tests/test_sweepstate.py::VerweesdeLockTest` — eleven tests; the probe is
  injected there because a genuinely terminated PID is not a reproducible
  fixture on Windows, measured reading False in one run and True in another
