"""Meta-guard: elke test in tests/ moet daadwerkelijk verzameld worden.

Aanleiding (TASK-53): CI draaide `unittest discover`, dat losse `test_*`-functies
op moduleniveau niet verzamelt. Zes bestanden waren zo geschreven -- samen 21
tests die nooit hebben gedraaid, waaronder `test_integration_documentation.py`,
de doc-guard die verouderde documentatieclaims had moeten tegenhouden. Dat is de
onderliggende oorzaak van de doc-drift die elders in deze opruiming is
gecorrigeerd: er stond een poort, maar niemand liep erlangs.

CI draait nu pytest, dus die tests draaien. Deze guard voorkomt de terugval naar
een bestand dat onder *beide* runners stil overgeslagen kan worden, en houdt de
suite leesbaar voor wie hem met `unittest` draait.

Bewust AST en niet een stringcheck op "unittest.TestCase": zo'n check slaagt op
een bestand dat de basisklasse ergens gebruikt maar er daarnaast een dode
module-level testfunctie in heeft staan -- precies het geval dat hier fout ging.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

# Bestanden die nog module-level testfuncties bevatten. De lijst hoort te
# krimpen, nooit te groeien: een nieuw bestand toevoegen betekent dat er weer
# tests zijn die onder `unittest discover` onzichtbaar zijn.
KNOWN_FUNCTION_STYLE = {
    "test_integration_documentation.py",
    "test_kb_retrieve_memory.py",
    "test_quiet_hook.py",
    "test_session_end.py",
    "test_session_log.py",
    "test_session_start.py",
}


def _module_level_test_functions(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test")
    ]


class SuiteCollectionTest(unittest.TestCase):
    def _test_files(self):
        return sorted(p for p in TESTS_DIR.glob("test_*.py") if p.name != Path(__file__).name)

    def test_no_new_function_style_test_files(self):
        offenders = {
            p.name: _module_level_test_functions(p)
            for p in self._test_files()
            if _module_level_test_functions(p) and p.name not in KNOWN_FUNCTION_STYLE
        }
        self.assertEqual(
            offenders, {},
            "nieuwe testbestanden met module-level test_*-functies: die worden "
            "door `unittest discover` niet verzameld. Zet ze in een "
            "unittest.TestCase, of voeg ze bewust toe aan KNOWN_FUNCTION_STYLE:\n"
            + "\n".join(f"  {k}: {v}" for k, v in offenders.items()))

    def test_known_list_has_no_stale_entries(self):
        """De lijst moet krimpen als bestanden worden omgezet."""
        actual = {p.name for p in self._test_files() if _module_level_test_functions(p)}
        stale = KNOWN_FUNCTION_STYLE - actual
        self.assertEqual(
            stale, set(),
            f"KNOWN_FUNCTION_STYLE noemt bestanden die geen module-level tests "
            f"meer hebben; haal ze uit de lijst: {sorted(stale)}")

    def test_every_test_file_contributes_at_least_one_test(self):
        empty = []
        for p in self._test_files():
            tree = ast.parse(p.read_text(encoding="utf-8"))
            has_case = any(
                isinstance(node, ast.ClassDef)
                and any(isinstance(item, ast.FunctionDef) and item.name.startswith("test")
                        for item in node.body)
                for node in ast.walk(tree)
            )
            if not has_case and not _module_level_test_functions(p):
                empty.append(p.name)
        self.assertEqual(empty, [], f"testbestanden zonder enige test: {empty}")


if __name__ == "__main__":
    unittest.main()
