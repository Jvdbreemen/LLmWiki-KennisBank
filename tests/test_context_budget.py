"""Tests voor scripts/context-budget.py — select_layers() pure functie.

Unit-tests voor select_layers(level, state) met geïnjecteerde state.
Geen netwerk, geen Ollama, geen filesystem-afhankelijkheden.
"""
from __future__ import annotations

import unittest

from tests._loader import load_script


def _cb():
    return load_script("context-budget.py")


FULL_STATE = {
    "identity": "vault-eigenaar Jim, actieve projecten: X, Y",
    "active": {"open_loops": ["loop-a"], "recent_sessions": ["2026-06-20"], "status_counts": {"actief": 5}},
    "relevant": [{"path": "02-wiki/foo.md", "score": 0.9, "snippet": "tekst"}],
    "bodies": {"02-wiki/foo.md": "Volledige tekst van het artikel."},
}


class TestSelectLayersL0(unittest.TestCase):
    """Level 0: alleen identity."""

    def setUp(self):
        self.cb = _cb()

    def test_identity_present(self):
        result = self.cb.select_layers(0, FULL_STATE)
        self.assertIn("identity", result)

    def test_active_absent(self):
        result = self.cb.select_layers(0, FULL_STATE)
        self.assertNotIn("active", result)

    def test_relevant_absent(self):
        result = self.cb.select_layers(0, FULL_STATE)
        self.assertNotIn("relevant", result)

    def test_bodies_absent(self):
        result = self.cb.select_layers(0, FULL_STATE)
        self.assertNotIn("bodies", result)

    def test_identity_value_matches(self):
        result = self.cb.select_layers(0, FULL_STATE)
        self.assertEqual(result["identity"], FULL_STATE["identity"])


class TestSelectLayersL1(unittest.TestCase):
    """Level 1: identity + active."""

    def setUp(self):
        self.cb = _cb()

    def test_identity_present(self):
        result = self.cb.select_layers(1, FULL_STATE)
        self.assertIn("identity", result)

    def test_active_present(self):
        result = self.cb.select_layers(1, FULL_STATE)
        self.assertIn("active", result)

    def test_relevant_absent(self):
        result = self.cb.select_layers(1, FULL_STATE)
        self.assertNotIn("relevant", result)

    def test_bodies_absent(self):
        result = self.cb.select_layers(1, FULL_STATE)
        self.assertNotIn("bodies", result)


class TestSelectLayersL2(unittest.TestCase):
    """Level 2: identity + active + relevant."""

    def setUp(self):
        self.cb = _cb()

    def test_identity_present(self):
        result = self.cb.select_layers(2, FULL_STATE)
        self.assertIn("identity", result)

    def test_active_present(self):
        result = self.cb.select_layers(2, FULL_STATE)
        self.assertIn("active", result)

    def test_relevant_present(self):
        result = self.cb.select_layers(2, FULL_STATE)
        self.assertIn("relevant", result)

    def test_bodies_absent(self):
        result = self.cb.select_layers(2, FULL_STATE)
        self.assertNotIn("bodies", result)


class TestSelectLayersL3(unittest.TestCase):
    """Level 3: volledig superset inclusief bodies."""

    def setUp(self):
        self.cb = _cb()

    def test_identity_present(self):
        result = self.cb.select_layers(3, FULL_STATE)
        self.assertIn("identity", result)

    def test_active_present(self):
        result = self.cb.select_layers(3, FULL_STATE)
        self.assertIn("active", result)

    def test_relevant_present(self):
        result = self.cb.select_layers(3, FULL_STATE)
        self.assertIn("relevant", result)

    def test_bodies_present(self):
        result = self.cb.select_layers(3, FULL_STATE)
        self.assertIn("bodies", result)

    def test_bodies_value_matches(self):
        result = self.cb.select_layers(3, FULL_STATE)
        self.assertEqual(result["bodies"], FULL_STATE["bodies"])


class TestSelectLayersClamping(unittest.TestCase):
    """Level buiten 0..3 wordt geclamped."""

    def setUp(self):
        self.cb = _cb()

    def test_level_9_behaves_as_3(self):
        result_9 = self.cb.select_layers(9, FULL_STATE)
        result_3 = self.cb.select_layers(3, FULL_STATE)
        self.assertEqual(set(result_9.keys()), set(result_3.keys()))

    def test_level_minus1_behaves_as_0(self):
        result_neg = self.cb.select_layers(-1, FULL_STATE)
        result_0 = self.cb.select_layers(0, FULL_STATE)
        self.assertEqual(set(result_neg.keys()), set(result_0.keys()))

    def test_level_high_includes_bodies(self):
        result = self.cb.select_layers(99, FULL_STATE)
        self.assertIn("bodies", result)

    def test_level_negative_excludes_active(self):
        result = self.cb.select_layers(-5, FULL_STATE)
        self.assertNotIn("active", result)


class TestSelectLayersMissingKeys(unittest.TestCase):
    """Ontbrekende state-sleutels mogen niet crashen."""

    def setUp(self):
        self.cb = _cb()

    def test_empty_state_level0_no_crash(self):
        result = self.cb.select_layers(0, {})
        self.assertIsInstance(result, dict)

    def test_empty_state_level3_no_crash(self):
        result = self.cb.select_layers(3, {})
        self.assertIsInstance(result, dict)

    def test_partial_state_level3_no_crash(self):
        partial = {"identity": "alleen dit"}
        result = self.cb.select_layers(3, partial)
        self.assertIn("identity", result)

    def test_missing_identity_level0_returns_dict(self):
        result = self.cb.select_layers(0, {})
        # mag identity weglaten of leeg geven, maar mag niet crashen
        self.assertIsInstance(result, dict)

    def test_missing_relevant_level2_returns_dict(self):
        state_no_relevant = {k: v for k, v in FULL_STATE.items() if k != "relevant"}
        result = self.cb.select_layers(2, state_no_relevant)
        self.assertIsInstance(result, dict)
        # relevant mag ontbreken of leeg zijn
        if "relevant" in result:
            # als het er is, moet het een lege/geldige waarde zijn
            self.assertIsNotNone(result["relevant"])


class TestSelectLayersReturnType(unittest.TestCase):
    """Returnwaarde is altijd een dict."""

    def setUp(self):
        self.cb = _cb()

    def test_returns_dict_at_all_levels(self):
        for level in range(4):
            with self.subTest(level=level):
                result = self.cb.select_layers(level, FULL_STATE)
                self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()
