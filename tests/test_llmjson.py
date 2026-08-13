"""A model that keeps talking after its JSON must not cost us the JSON.

Every seam sliced `raw[raw.find("{"):raw.rfind("}") + 1]` — the WIDEST possible
span. When a model adds a sentence after the object and that sentence contains
a brace, the slice runs to the end of the commentary and the parse fails. Every
seam is fail-safe, so the failure is silent: extract returns [], reconcile
returns ADD, the judge returns unverified. Measured in the TASK-142 sweep,
qwen3.5:9b did this twice in twenty calls (TASK-144).

The fix is narrower, not wider: take the FIRST complete object or array.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import unittest  # noqa: E402

import _extract  # noqa: E402
import _judge  # noqa: E402
import _llmjson  # noqa: E402
import _maintenance  # noqa: E402
import _reconcile  # noqa: E402


class FirstObjectTest(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(_llmjson.first_object('{"a": 1}'), {"a": 1})

    def test_prose_after_the_object_with_a_brace_in_it(self):
        """The exact shape that broke the old slice."""
        raw = ('{"action": "ADD", "reason": "nieuw"}\n'
               'Ik koos hiervoor omdat {var} niet van toepassing was.')
        self.assertEqual(_llmjson.first_object(raw)["action"], "ADD")

    def test_prose_before_the_object(self):
        raw = 'Even nadenken... Hier is mijn oordeel:\n{"action": "NOOP"}'
        self.assertEqual(_llmjson.first_object(raw), {"action": "NOOP"})

    def test_a_brace_in_the_leading_prose_does_not_win(self):
        """The mirror of the trailing case, and just as silent.

        Taking only the FIRST opening brace picks `{even}`, fails to parse,
        falls back to the wide slice which also fails, and the seam returns its
        fail-safe as if the model had said nothing.
        """
        raw = 'Ik denk {even} na. {"action": "ADD", "reason": "nieuw"}'
        self.assertEqual(_llmjson.first_object(raw)["action"], "ADD")

    def test_several_false_starts_before_the_real_object(self):
        raw = '{a} {b} {c} {"action": "SUPERSEDE"}'
        self.assertEqual(_llmjson.first_object(raw)["action"], "SUPERSEDE")

    def test_a_bracket_in_the_leading_prose_does_not_win_either(self):
        raw = 'Zie [dit] eerst. [{"title": "T", "body": "B"}]'
        self.assertEqual(_llmjson.first_array(raw), [{"title": "T", "body": "B"}])

    def test_a_brace_inside_a_string_does_not_close_the_object(self):
        raw = '{"reason": "gebruik {var} niet", "action": "ADD"}'
        self.assertEqual(_llmjson.first_object(raw)["action"], "ADD")

    def test_an_escaped_quote_inside_a_string(self):
        raw = r'{"reason": "hij zei \"nee\"", "action": "ADD"} en verder...'
        self.assertEqual(_llmjson.first_object(raw)["action"], "ADD")

    def test_nested_objects(self):
        raw = '{"a": {"b": 2}} daarna nog wat tekst}'
        self.assertEqual(_llmjson.first_object(raw), {"a": {"b": 2}})

    def test_nothing_parseable(self):
        for raw in ("", None, "geen json hier", "{kapot"):
            self.assertIsNone(_llmjson.first_object(raw), repr(raw))

    def test_an_array_is_not_an_object(self):
        self.assertIsNone(_llmjson.first_object('[1, 2]'))


class FirstArrayTest(unittest.TestCase):
    def test_prose_after_the_array(self):
        raw = ('[{"title": "T", "body": "B"}]\n'
               'Dit zijn de kandidaten [voor zover ik kon zien].')
        self.assertEqual(_llmjson.first_array(raw), [{"title": "T", "body": "B"}])

    def test_a_bracket_inside_a_string(self):
        raw = '[{"body": "zie [1] voor details"}] klaar]'
        self.assertEqual(len(_llmjson.first_array(raw)), 1)

    def test_empty_array(self):
        self.assertEqual(_llmjson.first_array("[]"), [])


class SeamsTest(unittest.TestCase):
    """The point is not the helper but that every seam actually uses it."""

    def setUp(self):
        import _llm
        self._llm = _llm
        self._orig = _llm.generate
        self.addCleanup(lambda: setattr(self._llm, "generate", self._orig))

    def _answers(self, text):
        self._llm.generate = lambda *a, **k: text

    def test_extract_survives_trailing_prose(self):
        self._answers('[{"title": "T", "body": "B", "type": "feit"}]\n'
                      'Meer kon ik er niet uit halen [helaas].')
        self.assertEqual(len(_extract.extract_candidates("tekst")), 1)

    def test_judge_survives_trailing_prose(self):
        self._answers('{"verdict": "current", "importance": 4}\n'
                      'Ik twijfelde tussen {current} en unverified.')
        self.assertEqual(_judge.judge("iets")["verdict"], "current")

    def test_reconcile_survives_trailing_prose(self):
        self._answers('{"action": "SUPERSEDE", "reason": "nieuwer"}\n'
                      'Toelichting: het oude {feit} klopt niet meer.')
        self.assertEqual(_reconcile.judge_reconcile("nieuw", "oud"), "SUPERSEDE")

    def test_supersede_judge_survives_trailing_prose(self):
        self._answers('{"supersede": true, "reason": "vervangt"}\n'
                      'Let op: {oud} was al achterhaald.')
        self.assertTrue(_maintenance.judge_supersede("nieuw", "oud"))

    def test_recheck_judge_survives_trailing_prose(self):
        self._answers('{"retract": false, "reason": "prima"}\n'
                      'Geen reden tot {intrekken}.')
        self.assertFalse(_maintenance.judge_recheck("iets"))

    def test_the_failsafe_still_holds_on_garbage(self):
        """Parsing more robustly must not replace the fail-safe."""
        self._answers("ik weet het niet")
        self.assertEqual(_reconcile.judge_reconcile("n", "o"), "ADD")
        self.assertEqual(_judge.judge("iets")["verdict"], "unverified")
        self.assertFalse(_maintenance.judge_supersede("n", "o"))
        self.assertEqual(_extract.extract_candidates("tekst"), [])


class ReconcilePromptTest(unittest.TestCase):
    """Both local models used NOOP to mean "unrelated" — the opposite of its
    definition, and the one action that discards the new memory."""

    def test_the_first_question_routes_no_overlap_to_add(self):
        systeem = _reconcile.RECONCILE_SYSTEM
        eerste = systeem.split("2.")[0]
        self.assertIn("HETZELFDE onderwerp", eerste)
        self.assertIn("ADD", eerste)
        self.assertNotIn("NOOP: het nieuwe voegt niets toe", eerste)

    def test_noop_is_the_last_option_and_says_what_it_costs(self):
        systeem = _reconcile.RECONCILE_SYSTEM
        self.assertGreater(systeem.index('3. Staat alles'), systeem.index('1. Gaan ze'))
        self.assertIn("WEGGEGOOID", systeem)

    def test_the_wire_values_are_untouched(self):
        """The prompt may change; stored data and callers may not have to."""
        self.assertEqual(_reconcile.ACTIONS, ("ADD", "SUPERSEDE", "NOOP"))

    def test_the_prompt_version_moved_with_the_prompt(self):
        self.assertGreaterEqual(_reconcile.RECONCILE_PROMPT_VERSION, 2)


if __name__ == "__main__":
    unittest.main()
