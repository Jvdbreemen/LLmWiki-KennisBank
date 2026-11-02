"""TASK-261: the recall read path must not import numpy.

Two tests, one per layer of the bug:

* ``ReadPathImportsTest`` (portable, runs in CI): opening the index read-only
  through kb-recall must not pull ``sqlite_vec``/``numpy`` into the process.
  ``_kbindex.vec0_extension()`` already loads the vec0 extension without
  executing the ``sqlite_vec`` package (TASK-120); kb-recall's read-only opens
  bypassed it with ``import sqlite_vec``, whose ``__init__`` imports numpy.

* ``RecallOverStdioTest`` (Windows only): the user-visible failure. The MCP
  stdio transport keeps a synchronous ``ReadFile`` pending on stdin in a worker
  thread. Loading numpy's native DLLs during a request blocks behind that read
  until the client sends another message, which it does not do before it has
  the answer: ``recall`` hangs forever. Measured before the fix: 3.8 s
  in-process, >120 s over stdio from Hermes, >45 s from the bare mcp SDK client.
  A watchdog kills the server so a regression fails instead of hanging CI.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

try:
    from tests.test_kb_mcp_wire import LEGACY_PROTOCOL, WireClient, _sdk_available
except ImportError:  # pragma: no cover - when tests/ itself is on sys.path
    from test_kb_mcp_wire import LEGACY_PROTOCOL, WireClient, _sdk_available

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
HAVE_SQLITE_VEC = importlib.util.find_spec("sqlite_vec") is not None

_PROBE = r"""
import importlib.util, json, sys
sys.path.insert(0, sys.argv[1])
import _kbindex
_kbindex.connect().close()
spec = importlib.util.spec_from_file_location("kb_recall", sys.argv[1] + "/kb-recall.py")
kr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kr)
kr._open_ro_checked(_kbindex.index_path()).close()
conn = kr._open_ro(_kbindex.index_path())
ok = conn is not None
conn.close()
print(json.dumps({"opened": ok, "numpy": "numpy" in sys.modules,
                  "sqlite_vec": "sqlite_vec" in sys.modules}))
"""


_PROBE_MISSING = r"""
import importlib.util, json, sys
sys.path.insert(0, sys.argv[1])
import _kbindex
_kbindex.connect().close()
spec = importlib.util.spec_from_file_location("kb_recall", sys.argv[1] + "/kb-recall.py")
kr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kr)
_kbindex._VEC0_PATH = None
real = importlib.util.find_spec
importlib.util.find_spec = lambda name, *a: None if name == "sqlite_vec" else real(name, *a)
try:
    kr._open_ro_checked(_kbindex.index_path())
    code = "opened"
except _kbindex.IndexUnavailable as exc:
    code = exc.code
print(json.dumps({"code": code, "ro": kr._open_ro(_kbindex.index_path()) is None}))
"""


@unittest.skipUnless(HAVE_SQLITE_VEC, "sqlite-vec not installed")
class ReadPathImportsTest(unittest.TestCase):
    def test_read_only_open_does_not_import_numpy(self):
        tmp = Path(tempfile.mkdtemp(prefix="kb-readpath-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        env = dict(os.environ, KENNISBANK_VAULT=str(tmp), PYTHONIOENCODING="utf-8")
        r = subprocess.run([sys.executable, "-c", _PROBE, str(SCRIPTS_DIR)],
                           capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        state = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertTrue(state["opened"], "read-only open must still load vec0")
        self.assertFalse(state["sqlite_vec"],
                         "kb-recall executed the sqlite_vec package; use _kbindex.vec0_extension()")
        self.assertFalse(state["numpy"], "numpy reached the recall read path")


    def test_missing_sqlite_vec_still_reports_sqlite_vec_missing(self):
        tmp = Path(tempfile.mkdtemp(prefix="kb-readpath-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        env = dict(os.environ, KENNISBANK_VAULT=str(tmp), PYTHONIOENCODING="utf-8")
        r = subprocess.run([sys.executable, "-c", _PROBE_MISSING, str(SCRIPTS_DIR)],
                           capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        state = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(state["code"], "sqlite_vec_missing")
        self.assertTrue(state["ro"], "_open_ro must degrade to None, not raise")


class _FakeEmbedHandler(BaseHTTPRequestHandler):
    """Minimal stand-in for Ollama's /api/embeddings: CI and dev boxes need no model."""

    def do_POST(self):  # noqa: N802 - http.server API
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        body = json.dumps({"embedding": [0.1] * 8}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@unittest.skipUnless(os.name == "nt", "the stdin/DLL-load deadlock is Windows-specific")
@unittest.skipUnless(HAVE_SQLITE_VEC, "sqlite-vec not installed")
class RecallOverStdioTest(unittest.TestCase):
    WATCHDOG_S = 45.0  # cold server start on Windows takes ~15 s

    @classmethod
    def setUpClass(cls):
        ok, reason = _sdk_available()
        if not ok:
            raise unittest.SkipTest(reason)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-mcp-stdio-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        vault = self.tmp / "vault"
        (vault / ".claude").mkdir(parents=True)
        (vault / "09-memory").mkdir(parents=True)
        # An existing (empty) index file is enough to reach the extension load.
        sqlite3.connect(vault / ".claude" / "kb-index.db").close()

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _FakeEmbedHandler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

        endpoint = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        with mock.patch.dict(os.environ, {"KB_EMBED_PROVIDER": "ollama",
                                          "KB_EMBED_ENDPOINT": endpoint}):
            self.client = WireClient(vault, timeout=self.WATCHDOG_S)
        self.addCleanup(self.client.close)
        # readline() blocks without a deadline; killing the server turns a
        # hang into EOF, so the test fails instead of stalling the suite.
        self.watchdog = threading.Timer(self.WATCHDOG_S, self.client.proc.kill)
        self.watchdog.start()
        self.addCleanup(self.watchdog.cancel)

    def test_recall_answers_over_stdio(self):
        rid = self.client.send("initialize", {
            "protocolVersion": LEGACY_PROTOCOL, "capabilities": {},
            "clientInfo": {"name": "kb-stdio-deadlock-test", "version": "1"}})
        self.assertNotIn("error", self.client.read_result(rid))
        self.client.send("notifications/initialized", {}, notify=True)

        rid = self.client.send("tools/call", {"name": "recall",
                                              "arguments": {"query": "deadlock probe", "k": 3}})
        reply = self.client.read_result(rid)  # EOF here == watchdog fired == deadlock
        self.assertNotIn("error", reply, f"recall failed: {reply}")
        self.assertIn("result", reply)


if __name__ == "__main__":
    unittest.main()
