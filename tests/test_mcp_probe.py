from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load():
    spec = importlib.util.spec_from_file_location("mcp_probe", SCRIPTS_DIR / "_mcp_probe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class McpProbeTest(unittest.TestCase):
    def test_real_probe_loads_vec0(self):
        module = _load()
        result = module.probe()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["vec0"])
        self.assertTrue(result["vec_version"].startswith("v"))

    def test_connection_without_extension_api_is_rejected_and_closed(self):
        module = _load()

        class Connection:
            closed = False

            def close(self):
                self.closed = True

        conn = Connection()
        result = module._probe_connection(conn, object())
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "extension_loading_unsupported")
        self.assertTrue(conn.closed)

    def test_connection_load_failure_is_classified(self):
        module = _load()

        class Connection:
            closed = False

            def enable_load_extension(self, _value):
                return None

            def load_extension(self, _value):
                return None

            def execute(self, _sql):
                if "vec_version" in _sql:
                    raise RuntimeError("no such module: vec0")
                raise AssertionError("unexpected SQL")

            def close(self):
                self.closed = True

        class Vector:
            @staticmethod
            def load(_conn):
                return None

        conn = Connection()
        result = module._probe_connection(conn, Vector)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "vec0_unavailable")
        self.assertTrue(conn.closed)


if __name__ == "__main__":
    unittest.main()
