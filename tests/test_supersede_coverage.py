"""Superseding without full coverage is how a vault loses knowledge.

Hand-labelling all 237 historic supersessions (TASK-161) put numbers on it:
61% were duplicate cleanups, only 11% genuinely replaced substance, and 27%
NARROWED — the successor dropped facts whose only carrier was the memory it
closed. `recall_hits` filters on status=current, so a narrowed-away fact is not
ranked lower, it is unreachable. Measured: 30 eval questions whose correct
answer is a narrowed-away memory score 0.000 in every ranking arm.

TASK-169 therefore makes full coverage a condition of closing, in BOTH judges
that can close a memory: the write-time reconcile and the maintenance
supersede pass. These tests pin the promise the prompts now make, the version
bumps that make closures traceable to it, and the wire values that must not
move.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _maintenance  # noqa: E402
import _reconcile  # noqa: E402


class CoverageConditionTest(unittest.TestCase):
    def test_reconcile_supersede_requires_full_coverage(self):
        """Question 2 may only close the old memory when nothing is dropped."""
        s = _reconcile.RECONCILE_SYSTEM
        q2 = s.split("2.")[1].split("3.")[0]
        self.assertIn("SUPERSEDE", q2)
        self.assertIn("blijvende waarde", q2)
        self.assertIn("ADD", q2, "partial coverage must route to ADD, not close")

    def test_reconcile_names_the_cost(self):
        """The prompt says WHY: a closed carrier means the facts are gone.

        Prompts that state consequences measurably outperform bare rules on
        the destructive actions here (TASK-144's NOOP fix used the same move).
        """
        self.assertIn("kennisverlies", _reconcile.RECONCILE_SYSTEM)

    def test_maintenance_supersede_requires_full_coverage(self):
        s = _maintenance.SUPERSEDE_SYSTEM
        q2 = s.split("2.")[1].split("3.")[0]
        self.assertIn("blijvende waarde", q2)
        self.assertIn("supersede: false", q2,
                      "partial coverage must keep the older memory open")

    def test_both_prompts_moved_to_version_3(self):
        """Closures are stamped with the prompt version; a changed prompt with
        an unmoved version would make the closed-log lie about causes."""
        self.assertGreaterEqual(_reconcile.RECONCILE_PROMPT_VERSION, 3)
        self.assertGreaterEqual(_maintenance.SUPERSEDE_PROMPT_VERSION, 3)

    def test_the_wire_values_are_untouched(self):
        self.assertEqual(_reconcile.ACTIONS, ("ADD", "SUPERSEDE", "NOOP"))

    def test_the_question_order_survives(self):
        """TASK-144's fix — destructive actions last — must not regress while
        adding the coverage condition."""
        s = _reconcile.RECONCILE_SYSTEM
        self.assertLess(s.index("1. Gaan ze"), s.index("2. Zegt het nieuwe"))
        self.assertLess(s.index("2. Zegt het nieuwe"), s.index("3. Staat alles"))
        m = _maintenance.SUPERSEDE_SYSTEM
        self.assertLess(m.index("1. Gaan ze"), m.index("2. Geeft de nieuwere"))


if __name__ == "__main__":
    unittest.main()
