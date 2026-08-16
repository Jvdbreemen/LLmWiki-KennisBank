"""Tests voor scripts/context-budget.py — select_layers() pure functie.

Unit-tests voor select_layers(level, state) met geïnjecteerde state.
Geen netwerk, geen Ollama, geen filesystem-afhankelijkheden.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from tests._loader import load_script

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "context-budget.py"


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


class TestEnvIntFailSoft(unittest.TestCase):
    """Subprocess-tests: garbage env vars mogen nooit een crash opleveren."""

    def _run(self, extra_env: dict, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
        # KB_CONTEXT_MAX_TOKENS gepind: een plafond uit de omgeving van de
        # ontwikkelaar zou hier een _budget-blok toevoegen en de sleutel-
        # assertie hieronder laten vallen om een reden die niets met de test
        # te maken heeft.
        env = {**os.environ, "KENNISBANK_VAULT": "/nonexistent/vault/path",
               "KB_CONTEXT_MAX_TOKENS": "0", **extra_env}
        cmd = [sys.executable, str(SCRIPT)] + (extra_args or [])
        return subprocess.run(cmd, capture_output=True, text=True, env=env)

    def test_garbage_kb_context_level_exits_zero(self):
        """KB_CONTEXT_LEVEL='abc' mag geen ValueError-traceback geven; exit 0."""
        result = self._run({"KB_CONTEXT_LEVEL": "abc"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_garbage_kb_context_level_outputs_valid_json(self):
        """Output bij garbage KB_CONTEXT_LEVEL moet parseerbare JSON zijn."""
        result = self._run({"KB_CONTEXT_LEVEL": "abc"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        parsed = json.loads(result.stdout)
        self.assertIsInstance(parsed, dict)

    def test_garbage_kb_retrieve_top_n_exits_zero(self):
        """KB_RETRIEVE_TOP_N='xyz' mag geen ValueError geven; exit 0."""
        result = self._run({"KB_RETRIEVE_TOP_N": "xyz"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_garbage_kb_retrieve_top_n_outputs_valid_json(self):
        """Output bij garbage KB_RETRIEVE_TOP_N moet parseerbare JSON zijn."""
        result = self._run({"KB_RETRIEVE_TOP_N": "xyz"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        parsed = json.loads(result.stdout)
        self.assertIsInstance(parsed, dict)

    def test_level0_missing_vault_exits_zero(self):
        """--level 0 tegen een ontbrekende vault moet exit 0 geven."""
        result = self._run({}, extra_args=["--level", "0"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_level0_missing_vault_contains_identity_key(self):
        """--level 0 tegen een ontbrekende vault geeft JSON met 'identity'-sleutel (leeg of afwezig is ook goed)."""
        result = self._run({}, extra_args=["--level", "0"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        parsed = json.loads(result.stdout)
        self.assertIsInstance(parsed, dict)
        # identity mag ontbreken (vault bestaat niet) maar de output is altijd een dict
        # en bevat in ieder geval de sleutel als CLAUDE.md aanwezig was
        # Hier controleren we dat er geen ongeldige sleutels zijn
        allowed = {"identity", "active", "relevant", "bodies"}
        self.assertTrue(set(parsed.keys()).issubset(allowed))


# ---------------------------------------------------------------------------
# Token-plafond (--max-tokens / KB_CONTEXT_MAX_TOKENS)
# ---------------------------------------------------------------------------

def _budget_state(n_results: int = 3, body_chars: int = 400) -> dict:
    """Level-3 output met voorspelbare, aflopend gerankte inhoud."""
    relevant = [
        {"path": f"02-wiki/art{i}.md", "score": 1.0 - i / 10, "snippet": "s" * 20}
        for i in range(n_results)
    ]
    bodies = {item["path"]: "b" * body_chars for item in relevant}
    return {
        "identity": "vault-eigenaar Jim",
        "active": {"open_loops": ["loop-a"], "recent_sessions": ["2026-06-20"]},
        "relevant": relevant,
        "bodies": bodies,
    }


class TestEstimateTokens(unittest.TestCase):
    """Schatting is deterministisch en rondt naar boven af."""

    def setUp(self):
        self.cb = _cb()

    def test_none_costs_nothing(self):
        self.assertEqual(self.cb.estimate_tokens(None), 0)

    def test_empty_string_costs_nothing(self):
        self.assertEqual(self.cb.estimate_tokens(""), 0)

    def test_four_chars_is_one_token(self):
        self.assertEqual(self.cb.estimate_tokens("abcd"), 1)

    def test_rounds_up(self):
        """Vijf tekens passen niet in één token; naar boven afronden."""
        self.assertEqual(self.cb.estimate_tokens("abcde"), 2)

    def test_structured_value_is_measured_serialised(self):
        value = {"a": "x" * 100}
        expected = -(-len(json.dumps(value, ensure_ascii=False)) // 4)
        self.assertEqual(self.cb.estimate_tokens(value), expected)


class TestFitToBudgetNoCeiling(unittest.TestCase):
    """Zonder plafond blijft alles exact zoals het was."""

    def setUp(self):
        self.cb = _cb()

    def test_none_returns_output_unchanged(self):
        state = _budget_state()
        fitted, report = self.cb.fit_to_budget(state, None)
        self.assertEqual(fitted, state)

    def test_none_returns_no_report(self):
        _, report = self.cb.fit_to_budget(_budget_state(), None)
        self.assertIsNone(report)

    def test_zero_returns_output_unchanged(self):
        state = _budget_state()
        fitted, report = self.cb.fit_to_budget(state, 0)
        self.assertEqual(fitted, state)
        self.assertIsNone(report)

    def test_negative_returns_output_unchanged(self):
        state = _budget_state()
        fitted, report = self.cb.fit_to_budget(state, -100)
        self.assertEqual(fitted, state)
        self.assertIsNone(report)


class TestFitToBudgetFits(unittest.TestCase):
    """Plafond ruim genoeg: niets weg, maar wél een rapport."""

    def setUp(self):
        self.cb = _cb()
        self.state = _budget_state()
        self.fitted, self.report = self.cb.fit_to_budget(self.state, 100_000)

    def test_content_untouched(self):
        self.assertEqual(self.fitted, self.state)

    def test_report_present_even_when_nothing_dropped(self):
        self.assertIsNotNone(self.report)

    def test_nothing_recorded_as_dropped(self):
        self.assertEqual(self.report["dropped"], {})

    def test_within_budget(self):
        self.assertTrue(self.report["within_budget"])

    def test_estimate_matches_content(self):
        expected = sum(self.cb.estimate_tokens(v) for v in self.fitted.values())
        self.assertEqual(self.report["estimated_tokens"], expected)


class TestFitToBudgetTrims(unittest.TestCase):
    """Plafond te krap: trimvolgorde en rapportage."""

    def setUp(self):
        self.cb = _cb()

    def test_result_respects_ceiling(self):
        state = _budget_state()
        fitted, report = self.cb.fit_to_budget(state, 120)
        total = sum(self.cb.estimate_tokens(v) for v in fitted.values())
        self.assertLessEqual(total, 120)
        self.assertTrue(report["within_budget"])

    def test_bodies_go_before_relevant(self):
        """Bodies zijn herleidbaar uit relevant, dus die sneuvelen eerst."""
        state = _budget_state()
        # Plafond dat identity + active + relevant net toelaat maar bodies niet.
        ceiling = sum(
            self.cb.estimate_tokens(state[k]) for k in ("identity", "active", "relevant")
        )
        fitted, report = self.cb.fit_to_budget(state, ceiling)
        self.assertNotIn("bodies", fitted)
        self.assertEqual(len(fitted["relevant"]), len(state["relevant"]))

    def test_lowest_ranked_body_drops_first(self):
        """relevant is score-gesorteerd en bodies volgt die volgorde: staart eerst."""
        state = _budget_state(n_results=3, body_chars=400)
        # Ruimte voor precies twee van de drie bodies.
        base = sum(self.cb.estimate_tokens(state[k]) for k in ("identity", "active", "relevant"))
        two_bodies = {k: state["bodies"][k] for k in list(state["bodies"])[:2]}
        fitted, report = self.cb.fit_to_budget(
            state, base + self.cb.estimate_tokens(two_bodies))
        self.assertEqual(list(fitted["bodies"]), ["02-wiki/art0.md", "02-wiki/art1.md"])
        self.assertEqual(report["dropped"], {"bodies": 1})

    def test_lowest_ranked_result_drops_first(self):
        """Zelfde regel één laag hoger: de zwakste match verdwijnt, niet de beste."""
        state = _budget_state(n_results=3, body_chars=4000)
        # Ruimte voor precies één van de drie treffers, en geen enkele body.
        ceiling = (self.cb.estimate_tokens(state["identity"])
                   + self.cb.estimate_tokens(state["active"])
                   + self.cb.estimate_tokens(state["relevant"][:1]))
        fitted, report = self.cb.fit_to_budget(state, ceiling)
        self.assertEqual([r["path"] for r in fitted["relevant"]], ["02-wiki/art0.md"])
        self.assertEqual(report["dropped"]["relevant"], 2)

    def test_emptied_layer_is_removed_not_left_empty(self):
        state = _budget_state()
        fitted, _ = self.cb.fit_to_budget(state, 10)
        self.assertNotIn("bodies", fitted)
        self.assertNotIn("relevant", fitted)

    def test_dropped_counts_are_accurate(self):
        state = _budget_state(n_results=3, body_chars=4000)
        fitted, report = self.cb.fit_to_budget(state, 10)
        self.assertEqual(report["dropped"]["bodies"], 3)
        self.assertEqual(report["dropped"]["relevant"], 3)

    def test_identity_survives_every_trim(self):
        state = _budget_state()
        fitted, _ = self.cb.fit_to_budget(state, 1)
        self.assertEqual(fitted["identity"], state["identity"])

    def test_identity_over_ceiling_is_reported_not_truncated(self):
        """Niets meer te trimmen: eerlijk melden i.p.v. het contract halveren."""
        state = {"identity": "x" * 4000}
        fitted, report = self.cb.fit_to_budget(state, 10)
        self.assertEqual(fitted["identity"], state["identity"])
        self.assertFalse(report["within_budget"])
        self.assertEqual(report["dropped"], {})

    def test_input_is_not_mutated(self):
        state = _budget_state()
        before = json.dumps(state, sort_keys=True)
        self.cb.fit_to_budget(state, 10)
        self.assertEqual(json.dumps(state, sort_keys=True), before)


class TestBudgetCLI(unittest.TestCase):
    """CLI-contract: _budget alleen bij een gevraagd plafond."""

    def _run(self, extra_env: dict, extra_args: list[str] | None = None):
        env = {**os.environ, "KENNISBANK_VAULT": "/nonexistent/vault/path",
               "KB_CONTEXT_MAX_TOKENS": "0", **extra_env}
        cmd = [sys.executable, str(SCRIPT)] + (extra_args or [])
        return subprocess.run(cmd, capture_output=True, text=True, env=env)

    def test_no_ceiling_emits_no_budget_key(self):
        result = self._run({}, extra_args=["--level", "0"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn("_budget", json.loads(result.stdout))

    def test_ceiling_emits_budget_key(self):
        result = self._run({}, extra_args=["--level", "0", "--max-tokens", "500"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        parsed = json.loads(result.stdout)
        self.assertIn("_budget", parsed)
        self.assertEqual(parsed["_budget"]["max_tokens"], 500)

    def test_ceiling_via_environment(self):
        result = self._run({"KB_CONTEXT_MAX_TOKENS": "500"}, extra_args=["--level", "0"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(json.loads(result.stdout)["_budget"]["max_tokens"], 500)

    def test_garbage_ceiling_env_exits_zero(self):
        """Onleesbare KB_CONTEXT_MAX_TOKENS mag geen traceback geven."""
        result = self._run({"KB_CONTEXT_MAX_TOKENS": "abc"}, extra_args=["--level", "0"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn("_budget", json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
