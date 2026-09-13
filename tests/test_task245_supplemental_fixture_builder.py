"""Keep the private supplemental TASK-245 fixture builder source-grounded."""
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "task245_supplement_builder",
    ROOT / "scripts" / "build-task245-supplemental-fixture.py",
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class SupplementalFixtureBuilderTest(unittest.TestCase):
    def test_builds_exact_private_refs_without_opening_holdout(self):
        with self.subTest("fixture"):
            from tempfile import TemporaryDirectory

            with TemporaryDirectory() as root_text:
                root = Path(root_text)
                vault = root / "vault"
                raw = vault / "01-raw" / "transcripts"
                raw.mkdir(parents=True)
                evaluations = vault / "06-claude" / "evaluations"
                evaluations.mkdir(parents=True)
                event = {
                    "sessionId": "00000000-0000-0000-0000-000000000001",
                    "message": {
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "content": "Observed exact evidence: runner child kept the page responsive.",
                        }],
                    },
                }
                source = raw / "2026-09-10-fixture.jsonl"
                source.write_text(json.dumps(event) + "\n", encoding="utf-8")
                spec_data = {
                    "id": "T01",
                    "domain": "fixture",
                    "source_file": source.name,
                    "situation": "A slow operation exists.",
                    "goal": "Keep the page responsive.",
                    "approach": "Use a child.",
                    "action": "Run the child.",
                    "observed_result": "The page stayed responsive.",
                    "lesson": "Long work belongs outside the request.",
                    "applicability": "Questions about the runner child.",
                    "attempt_state": "success",
                    "resolution_state": "fix_validated",
                    "outcome_state": "success",
                    "assertion": "The runner child kept the page responsive.",
                    "evidence": [{
                        "line": 1,
                        "block": 0,
                        "begin": "Observed exact evidence",
                        "end": "",
                        "contains": ["runner child", "responsive"],
                    }],
                    "positive": ["Why use a runner child?", "What stayed responsive?", "What was the lesson?"],
                    "negative": [
                        ["What was the GPU temperature?", "unobserved", "No GPU temperature was recorded."],
                        ["Which database index was used?", "different", "No database index was recorded."],
                        ["What was the release price?", "unobserved", "No price was recorded."],
                    ],
                }
                spec_path = root / "spec.json"
                spec_path.write_text(json.dumps([spec_data]), encoding="utf-8")
                output = evaluations / "probe"

                builder.build(spec_path, output, vault)

                cases = (output / "cases.jsonl").read_text(encoding="utf-8").splitlines()
                records = json.loads((output / "records.json").read_text(encoding="utf-8"))
                provenance = json.loads((output / "provenance.json").read_text(encoding="utf-8"))
                self.assertEqual(len(cases), 6)
                self.assertEqual(len(records), 1)
                self.assertFalse(provenance["holdout_opened"])
                ref = records[0]["source_refs"][0]
                resolved = builder._source_ref.resolve_source_ref(vault, ref)
                self.assertEqual(resolved["status"], "valid")
                self.assertIn("runner child", resolved["passage"])

    def test_output_must_stay_below_private_evaluations_root(self):
        with self.assertRaises(ValueError):
            builder._private_output(Path("C:/outside"), Path("C:/vault"))


if __name__ == "__main__":
    unittest.main()
