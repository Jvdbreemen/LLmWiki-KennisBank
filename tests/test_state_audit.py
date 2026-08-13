"""A zero is not a clean bill of health.

The `second-brain-audit` skill ships a deterministic scanner. Run against this
vault it reported zero contradictions while four were demonstrably present: it
compares monetary values, and this vault holds none. Its own guidance says so
out loud, and prints a coverage warning when it knows it was blind.

`kb-state-audit.py` does the same trick for the value types this vault actually
carries — model tags, thresholds, toggles — with one advantage the skill's
script cannot have: an authority to compare against instead of a second
opinion. These tests hold it to the part that matters, which is not the count
but the coverage line beside it (TASK-149).
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import _memory  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location(
        "kb_state_audit", str(REPO / "scripts" / "kb-state-audit.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class StateAuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-audit-"))
        (self.tmp / "09-memory").mkdir(parents=True)
        (self.tmp / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.tmp)
        (self.tmp / ".claude" / "kennisbank-embed.json").write_text(json.dumps({
            "_comment": "examples are NOT the authority",
            "provider": "ollama",
            "model": "qwen3-embedding:4b",
            "retrieve_top_n": 3,
            "retrieve_threshold": 0.5,
            "_switching": {"openai": {"model": "text-embedding-3-small"}},
        }), encoding="utf-8")
        (self.tmp / ".claude" / "kennisbank-llm.json").write_text(json.dumps({
            "providers": ["ollama"], "model": "qwen3.5:4b",
            "_switching": {"ollama_pinned": {"model": "gemma4:12b"}},
        }), encoding="utf-8")
        self.m = _load()

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mem(self, title, body, status="current", volatility="state"):
        return _memory.write(title, body, status=status, created="2026-01-01",
                             volatility=volatility)

    def _piles(self):
        return self.m.audit()["piles"]

    # -- the four piles -----------------------------------------------------
    def test_a_stale_model_tag_is_contradicted(self):
        self._mem("Embedding", "Use `qwen3-embedding:8b` as the default model.")
        p = self._piles()
        self.assertEqual(len(p["contradicted"]), 1)
        self.assertEqual(p["contradicted"][0]["claim"], "qwen3-embedding:8b")
        self.assertEqual(p["contradicted"][0]["authority"], "qwen3-embedding:4b")

    def test_a_matching_claim_is_reported_as_confirmed_not_omitted(self):
        """Silence about agreement makes the report unreadable as evidence."""
        self._mem("Embedding", "The vault runs on `qwen3-embedding:4b`.")
        p = self._piles()
        self.assertEqual(p["contradicted"], [])
        self.assertEqual(len(p["confirmed"]), 1)

    def test_a_model_no_authority_pins_is_unsupported(self):
        self._mem("Default", "Always use `claude-opus-4-8` as the default model.")
        p = self._piles()
        self.assertEqual(len(p["unsupported"]), 1)
        self.assertIn("claude-opus", p["unsupported"][0]["why"])

    def test_a_memory_without_a_checkable_value_lands_in_coverage(self):
        """The pile that stops a zero from reading as a clean bill of health."""
        self._mem("Lesson", "Always ask again before building on an assumption.")
        p = self._piles()
        self.assertEqual(len(p["coverage"]), 1)
        self.assertEqual(p["contradicted"], [])

    def test_the_report_always_states_what_it_could_not_see(self):
        self._mem("Lesson", "Something with no checkable value.")
        text = self.m.report(self.m.audit())
        self.assertIn("COVERAGE", text)
        self.assertIn("not an approval", text)

    # -- what IS and IS NOT the authority -----------------------------------
    def test_switching_examples_are_not_the_authority(self):
        """`_switching` names other models on purpose; they are documentation.

        Counting them would turn every stale claim into a confirmed one, which
        is the failure mode this audit exists to prevent.
        """
        self._mem("Old", "The judge runs on `gemma4:12b`.")
        p = self._piles()
        self.assertEqual(p["confirmed"], [],
                         "gemma4:12b only appears in _switching, so it is not an authority")

    def test_a_key_that_is_also_an_ordinary_word_is_not_compared(self):
        """Eight of twelve findings were this, measured on the live vault.

        `endpoint` is an English word and this vault is full of memories about
        REST endpoints of firmware. Comparing on it produced claims like
        "endpoint=2" against "http://localhost:11434".
        """
        self.assertFalse(self.m._looks_like_key("endpoint"))
        self.assertFalse(self.m._looks_like_key("model"))
        self.assertTrue(self.m._looks_like_key("retrieve_top_n"))
        self.assertTrue(self.m._looks_like_key("RECONCILE_THRESHOLD"))

    def test_a_command_or_a_source_reference_is_not_a_model(self):
        """`family:tag` matches far more than models.

        On the live vault it read `adr-kit:adr`, `file:line`, `f1:ab` and
        `_kbindex.py:41` as model claims — more false ones than real.
        """
        for text in ("Use `/kennisbank:settings` to set toggles.",
                     "The variable in `_kbindex.py:41` must be renamed.",
                     "Report findings as file:line."):
            self.assertEqual(self.m.model_tokens(text, {"qwen3-embedding"}), [],
                             text)

    def test_a_numeric_setting_is_compared_against_the_config(self):
        self._mem("Retrieval", "The value retrieve_top_n is set to 7.")
        p = self._piles()
        self.assertEqual(len(p["contradicted"]), 1)
        self.assertIn("retrieve_top_n", p["contradicted"][0]["key"])

    # -- the TASK-146 mitigation --------------------------------------------
    def test_a_checkable_claim_that_can_never_be_corrected_is_listed(self):
        """The safe default may cost something, as long as the cost is visible.

        An `event` is never superseded. A memory that carries a model tag and
        is labelled event will therefore keep its stale value forever, and
        nothing else in the system would ever say so.
        """
        self._mem("Embedding", "Use `qwen3-embedding:8b`.", volatility="event")
        p = self._piles()
        self.assertEqual(len(p["self_correction_off"]), 1)

    def test_a_state_labelled_claim_is_not_in_that_pile(self):
        self._mem("Embedding", "Use `qwen3-embedding:8b`.", volatility="state")
        self.assertEqual(self._piles()["self_correction_off"], [])

    # -- boundaries ---------------------------------------------------------
    def test_only_current_memories_are_audited(self):
        """Exactly the set the recall hook can inject; nothing else is loaded."""
        self._mem("Old", "Use `qwen3-embedding:8b`.", status="superseded")
        p = self._piles()
        self.assertEqual(p["contradicted"], [])
        self.assertEqual(p["coverage"], [])

    def test_the_audit_never_writes(self):
        """Read-only is a promise, so it gets a test rather than a comment."""
        self._mem("Embedding", "Use `qwen3-embedding:8b`.")
        self._mem("Lesson", "Something with no value.")
        before = {p: (p.stat().st_mtime_ns, p.read_bytes())
                for p in sorted(self.tmp.rglob("*")) if p.is_file()}
        self.m.audit()
        after = {p: (p.stat().st_mtime_ns, p.read_bytes())
              for p in sorted(self.tmp.rglob("*")) if p.is_file()}
        self.assertEqual(before, after, "the audit touched the vault")

    def test_json_output_carries_the_counts_for_the_heartbeat(self):
        self._mem("Embedding", "Use `qwen3-embedding:8b`.")
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.m.main(["--json"])
        data = json.loads(buf.getvalue())
        self.assertEqual(len(data["contradicted"]), 1)
        self.assertIn("coverage", data)

    def test_a_nonzero_exit_only_when_the_caller_asks(self):
        self._mem("Embedding", "Use `qwen3-embedding:8b`.")
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.m.main([]), 0)
            self.assertEqual(self.m.main(["--fail-on-contradiction"]), 1)


if __name__ == "__main__":
    unittest.main()
