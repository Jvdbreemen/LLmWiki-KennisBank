"""Numeric env vars may tune, never kill (TASK-185).

An import-time ``int()`` over an env var turns one typo into a module-wide
ImportError. Measured blast radius: ``KB_EMBED_NUM_CTX=4k`` killed
``import _embeddings`` for all 26 importers, and the fail-open retrieval
hook swallowed the error and injected nothing — retrieval silently off for
every session. The fix is one shared fail-soft reader (_common.env_int /
env_float); the guard test at the bottom keeps the class extinct.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from tests._loader import load_script  # noqa: E402

from _common import env_float, env_int  # noqa: E402


class TestEnvHelpers(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("KB_TEST_NUM")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KB_TEST_NUM", None)
        else:
            os.environ["KB_TEST_NUM"] = self._saved

    def _with(self, value):
        if value is None:
            os.environ.pop("KB_TEST_NUM", None)
        else:
            os.environ["KB_TEST_NUM"] = value

    def test_env_int_parses_and_falls_back(self):
        for value, expect in ((None, 7), ("", 7), ("   ", 7), ("17", 17),
                              (" 17 ", 17), ("4k", 7), ("3.5", 7), ("1O", 7)):
            self._with(value)
            self.assertEqual(env_int("KB_TEST_NUM", 7), expect, repr(value))

    def test_env_float_parses_and_falls_back(self):
        for value, expect in ((None, 0.45), ("0.5", 0.5), ("high", 0.45),
                              ("", 0.45)):
            self._with(value)
            self.assertEqual(env_float("KB_TEST_NUM", 0.45), expect, repr(value))


#: (script, env var, module attribute, default) — every site the outage class
#: covered. Each module must LOAD with a malformed value and carry the default,
#: and must still honor a valid override.
SITES = [
    ("_embeddings.py", "KB_EMBED_NUM_CTX", "OLLAMA_NUM_CTX", 2048),
    ("_llm.py", "KB_LLM_NUM_CTX", "OLLAMA_NUM_CTX", 4096),
    ("_groundcheck.py", "KB_VERIFY_CAP", "VERIFY_PASS_CAP", 40),
    ("memory-sweep.py", "KB_SWEEP_MAX_CHUNKS", "MAX_CHUNKS", 40),
    ("memory-sweep.py", "KB_SWEEP_MAX_MEMORIES", "MAX_MEMORIES_PER_TRANSCRIPT", 60),
    ("memory-sweep.py", "KB_SWEEP_CHUNK_BUDGET", "CHUNK_BUDGET", 150),
]


class TestImportSurvivesMalformedEnv(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._saved = {k: os.environ.get(k) for k in
                       {"KENNISBANK_VAULT", *(s[1] for s in SITES),
                        "KB_MEMORY_THRESHOLD"}}
        os.environ["KENNISBANK_VAULT"] = self.tmp.name
        for _, var, _, _ in SITES:
            os.environ.pop(var, None)
        os.environ.pop("KB_MEMORY_THRESHOLD", None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def test_malformed_value_loads_with_the_default(self):
        for script, var, attr, default in SITES:
            with self.subTest(site=f"{script}:{var}"):
                os.environ[var] = "4k"
                try:
                    mod = load_script(script)
                finally:
                    os.environ.pop(var, None)
                self.assertEqual(getattr(mod, attr), default)

    def test_valid_override_is_still_honored(self):
        for script, var, attr, _default in SITES:
            with self.subTest(site=f"{script}:{var}"):
                os.environ[var] = "7"
                try:
                    mod = load_script(script)
                finally:
                    os.environ.pop(var, None)
                self.assertEqual(getattr(mod, attr), 7)

    def test_recall_threshold_survives_a_malformed_float(self):
        os.environ["KB_MEMORY_THRESHOLD"] = "high"
        try:
            mod = load_script("kb-recall.py")
        finally:
            os.environ.pop("KB_MEMORY_THRESHOLD", None)
        self.assertEqual(mod.MEMORY_MIN_COS, 0.45)


class TestNoRawEnvCastGuard(unittest.TestCase):
    def test_no_script_casts_env_vars_without_a_net(self):
        """int()/float() straight over os.environ is the outage pattern; use
        _common.env_int/env_float. Searched on full file text, not per line —
        the MAX_MEMORIES site spanned two lines and would evade a line-based
        scan."""
        pattern = re.compile(r"(?:\bint|\bfloat)\(\s*os\.environ")
        offenders = []
        for f in sorted(SCRIPTS_DIR.glob("*.py")):
            if f.name == "_common.py":  # the owning module
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            for m in pattern.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                offenders.append(f"{f.name}:{line}")
        self.assertEqual(
            offenders, [],
            "raw int()/float() over an env var; use _common.env_int/env_float: "
            + ", ".join(offenders))


if __name__ == "__main__":
    unittest.main()
