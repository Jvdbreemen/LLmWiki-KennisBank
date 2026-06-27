import importlib.util
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("_hooks_manifest", SCRIPTS / "_hooks_manifest.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class HooksManifestTest(unittest.TestCase):
    def setUp(self):
        self.m = _load()

    def test_contains_memory_hooks(self):
        scripts = {s for _, s, _ in self.m.hooks()}
        for need in ("build-kb-index.py", "sweep-launch.py", "memory-notify.py",
                     "kb-presearch.py", "build-embed-index.py", "kb-retrieve.py",
                     "archive-transcript.py", "distill-notify.py"):
            self.assertIn(need, scripts)

    def test_presearch_has_matcher(self):
        for event, script, matcher in self.m.hooks():
            if script == "kb-presearch.py":
                self.assertEqual(event, "PreToolUse")
                self.assertEqual(matcher, "WebSearch|WebFetch")
                break
        else:
            self.fail("kb-presearch.py niet in manifest")

    def test_hooks_returns_copy(self):
        self.m.hooks().append(("X", "y.py", None))
        self.assertNotIn(("X", "y.py", None), self.m.hooks())


if __name__ == "__main__":
    unittest.main()
