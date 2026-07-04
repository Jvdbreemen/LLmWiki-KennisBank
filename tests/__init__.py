"""Test-suite package init — hermeticity guard (TASK-21).

Plain ``python -m unittest discover -s tests`` imports this package BEFORE any
test module, so it is the single place that runs for the whole suite. (pytest's
conftest.py is NOT loaded by plain unittest, so a conftest cannot carry this.)

We pin the embed + LLM endpoints to a dead address so no test can ever reach a
real model server. The confirmed failure this prevents: the subprocess test in
test_kb_retrieve_memory hitting the real Ollama qwen3-embedding:8b (cold-load),
which hung the whole suite (>3 min, exit 143) on machines where Ollama is up,
and only "passed" on CI because Ollama was absent (connection-refused ->
fail-soft) — i.e. green for the WRONG reason. With the endpoints dead, that path
fails fast (instant connection-refused -> fail-soft) and the suite is identical
and quick on CI and locally, Ollama up or down.

127.0.0.1:1 is used because nothing listens on port 1: the OS returns RST
immediately (connection refused), so there is no timeout wait.

Tests that must exercise the model-REACHABLE branch mock ``emb.embed`` / the
``hits_fn`` locally, so the dead pin does not interfere with them.

The opt-in integration tier (KB_INTEGRATION=1) deliberately skips the pin so it
can drive the real embed->index->retrieval pipeline.

setdefault (not hard assignment) is used so an explicit endpoint exported by the
caller still wins — hermeticity by default, override by intent.
"""
from __future__ import annotations

import os

if os.environ.get("KB_INTEGRATION") != "1":
    os.environ.setdefault("KB_EMBED_ENDPOINT", "http://127.0.0.1:1")
    os.environ.setdefault("KB_LLM_ENDPOINT", "http://127.0.0.1:1")
