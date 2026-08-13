"""Test-suite package init — hermeticity guard (TASK-21).

Plain ``python -m unittest discover -s tests`` imports this package BEFORE any
test module, so it is the single place that runs for the whole suite. (pytest's
conftest.py is NOT loaded by plain unittest, so a conftest cannot carry this.)

We pin the embed + LLM endpoints to a dead address so no test can ever reach a
real model server. The confirmed failure this prevents: the subprocess test in
test_kb_retrieve_memory hitting the real Ollama qwen3-embedding:8b (cold-load),
which hung the whole suite (>3 min, exit 143) on machines where Ollama is up,
and only "passed" on CI because Ollama was absent (connection-refused ->
fail-soft) — i.e. green for the WRONG reason.

WHY A LISTENING SOCKET AND NOT A CLOSED PORT (TASK-141)
-------------------------------------------------------
This used to pin ``http://127.0.0.1:1``, on the stated premise that "nothing
listens on port 1: the OS returns RST immediately, so there is no timeout
wait". Measured on this Windows machine, that premise is false:

    127.0.0.1:1                        TimeoutError   2012 ms
    127.0.0.1:9                        TimeoutError   2016 ms
    127.0.0.1:<free ephemeral port>    TimeoutError   2014 ms
    localhost:<same>                   TimeoutError   2018 ms

Every closed loopback port DROPS the connection instead of refusing it. That
is host policy — a firewall rule — not a property of port 1, so no other port
number helps. Two things followed from it: every test path that still opened a
socket paid the caller's full timeout instead of failing fast, and any
assertion with a wall-clock budget became a latent flake. A 100 ms /api/ps
probe in ``status_line`` measured 511 ms against a 250 ms budget for exactly
this reason. Worse, CI (Linux) refuses instantly, so the suite behaved
differently there than here — the very asymmetry the pin was introduced to
remove.

A socket that is BOUND AND LISTENING cannot be dropped by a firewall rule: the
TCP handshake completes against the backlog, the accept loop closes the
connection at once, and the client sees a reset instead of a wait. Same
behaviour on Windows and on Linux, and no test ever reaches a model.

Tests that must exercise the model-REACHABLE branch mock ``emb.embed`` / the
``hits_fn`` locally, so the dead pin does not interfere with them.

The opt-in integration tier (KB_INTEGRATION=1) deliberately skips the pin so it
can drive the real embed->index->retrieval pipeline.

WHY THE PIN IS ASSIGNED AND NOT setdefault (TASK-141)
------------------------------------------------------
It used to be ``setdefault``, "so an explicit endpoint exported by the caller
still wins — hermeticity by default, override by intent". The intent that
actually reached it was nobody's: this developer's ``~/.claude/settings.json``
exports ``KB_LLM_ENDPOINT=http://localhost:11434`` for every session, because
the KennisBank scripts need it for real work. The pin therefore never fired for
the LLM seam on the machine where Ollama is running — the exact case TASK-21
added it for — while CI, which has no such variable, stayed pinned. The
asymmetry the pin exists to remove, running the other way round, invisibly.

Ambient configuration must not be able to switch off hermeticity. The override
is still there and is now unambiguous: ``KB_INTEGRATION=1`` says "let this
suite reach real services", which cannot be confused with an environment
variable that also has a legitimate production meaning.
"""
from __future__ import annotations

import os
import socket
import threading

#: Blijft leven zolang het proces leeft; module-globaal zodat de socket niet
#: door de garbage collector wordt gesloten zodra de functie terugkeert.
_DEAD_SERVER = None
#: Waar de pin naar wijst, zodat een test de aanname kan METEN in plaats van
#: hem te geloven (zie test_hermetic_pin.py).
DEAD_ENDPOINT = "http://127.0.0.1:1"


def _start_dead_listener() -> str:
    """Luister op een vrije poort en verbreek elke verbinding meteen.

    Fail-soft: lukt binden niet, dan valt de pin terug op de oude dichte
    poort. Trager, maar nog steeds hermetisch -- en hermetisch is de eis,
    snelheid is de winst.
    """
    global _DEAD_SERVER
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        srv.listen(64)
    except OSError:
        return "http://127.0.0.1:1"

    def _accepteer_en_sluit():
        while True:
            try:
                conn, _adres = srv.accept()
            except OSError:
                return  # socket dicht: proces stopt
            try:
                conn.close()
            except OSError:
                pass

    threading.Thread(target=_accepteer_en_sluit, daemon=True).start()
    _DEAD_SERVER = srv
    return f"http://127.0.0.1:{srv.getsockname()[1]}"


if os.environ.get("KB_INTEGRATION") != "1":
    DEAD_ENDPOINT = _start_dead_listener()
    # Toewijzen, niet setdefault: zie de uitleg hierboven. Een ambient
    # KB_LLM_ENDPOINT uit de gebruikersinstellingen zette de pin anders stil uit.
    os.environ["KB_EMBED_ENDPOINT"] = DEAD_ENDPOINT
    os.environ["KB_LLM_ENDPOINT"] = DEAD_ENDPOINT
