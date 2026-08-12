"""Tests voor scripts/kb-mcp.py - recall-tool core (zonder mcp-pakket/model)."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("kb_mcp", str(SCRIPTS_DIR / "kb-mcp.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class KbMcpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-mcp-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        sys.path.insert(0, str(SCRIPTS_DIR))
        self.m = _load()
        if getattr(self.m, "kb_recall", None) is None:
            self.skipTest("kb_recall niet beschikbaar (sqlite_vec ontbreekt?)")
        import _embeddings as emb
        self._orig_embed = emb.embed
        emb.embed = lambda text, timeout=30.0: [0.1, 0.2, 0.3]
        self.emb = emb
        self._orig_recall = self.m.kb_recall.recall_hits
        self.m.kb_recall.recall_hits = lambda *a, **k: [
            {"path": "/v/09-memory/x.md", "layer": "memory", "title": "Oude bug",
             "created": "2026-06-01", "score": 0.9, "snippet": "token expiry < ipv <="}]

    def tearDown(self):
        import shutil
        self.emb.embed = self._orig_embed
        self.m.kb_recall.recall_hits = self._orig_recall
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_recall_tool_formats_hits(self):
        out = self.m.recall_tool("token expiry bug")
        self.assertIn("Oude bug", out)
        self.assertIn("geheugen", out)

    def test_recall_tool_empty_query(self):
        self.assertEqual(self.m.recall_tool("").strip(), "")

    def test_recall_tool_no_hits(self):
        self.m.kb_recall.recall_hits = lambda *a, **k: []
        out = self.m.recall_tool("iets")
        self.assertIn("geen", out.lower())

    def test_recall_tool_embed_fail_is_soft(self):
        self.emb.embed = lambda *a, **k: None
        self.assertIn("geen", self.m.recall_tool("iets").lower())

    def test_build_server_registers_eight_annotated_tools(self):
        """Vervangt test_build_server_none_without_mcp, dat op 'MCPServer is None'
        aftakte en in BEIDE takken slaagde: die kon niets bewijzen.

        Deze test bouwt de server met een stub-SDK, dus hij draait ook zonder het
        mcp-pakket en faalt echt wanneer een tool zijn annotatie verliest. De
        annotaties zijn niet cosmetisch: Claude Code leidt isReadOnly() en
        isConcurrencySafe() af uit readOnlyHint en zet beide op false als de hint
        ontbreekt, dus een read-only tool zonder hint vraagt bevestiging en
        draait serieel."""
        registered = {}

        class StubServer:
            def __init__(self, name, **kw):
                self.name, self.kwargs = name, kw

            def tool(self, **kw):
                def deco(fn):
                    registered[fn.__name__] = kw
                    return fn
                return deco

            def resource(self, _uri):
                def deco(fn):
                    return fn
                return deco

        class StubAnn(dict):
            def __init__(self, **kw):
                super().__init__(**kw)

        orig_srv, orig_ann = self.m.MCPServer, self.m.ToolAnnotations
        self.m.MCPServer = StubServer
        self.m.ToolAnnotations = StubAnn
        try:
            srv = self.m.build_server()
        finally:
            self.m.MCPServer, self.m.ToolAnnotations = orig_srv, orig_ann

        self.assertIsNotNone(srv)
        self.assertEqual(set(registered), {
            "recall", "capture", "review_pending", "review_decide",
            "what_did_i_do", "timeline", "weeklog", "topic_timeline"})

        read_only = {"recall", "review_pending", "what_did_i_do", "timeline",
                     "weeklog", "topic_timeline"}
        for name in read_only:
            ann = registered[name]["annotations"]
            self.assertTrue(ann["readOnlyHint"], f"{name} hoort read-only te zijn")
            self.assertFalse(ann["openWorldHint"], f"{name} bevraagt een gesloten wereld")
        self.assertFalse(registered["capture"]["annotations"]["readOnlyHint"])
        self.assertFalse(registered["capture"]["annotations"]["destructiveHint"],
                         "capture maakt alleen een NIEUW bestand aan")
        self.assertTrue(registered["review_decide"]["annotations"]["destructiveHint"],
                        "review_decide flipt een status die daarna niet terug kan")
        for name, kw in registered.items():
            self.assertIn("title", kw["annotations"], f"{name} mist een leesbaar label")

    def test_build_server_survives_an_sdk_without_instructions_kwarg(self):
        """Een SDK die instructions= niet kent mag de server niet onderuit halen."""
        class PickyServer:
            def __init__(self, name, **kw):
                if kw:
                    raise TypeError("unexpected keyword argument")
                self.name = name

            def tool(self, **_kw):
                return lambda fn: fn

            def resource(self, _uri):
                return lambda fn: fn

        orig = self.m.MCPServer
        self.m.MCPServer = PickyServer
        try:
            self.assertIsNotNone(self.m.build_server())
        finally:
            self.m.MCPServer = orig


class KbMcpSdkFailureModeTest(unittest.TestCase):
    """Een ontbrekend mcp-pakket en een kapotte mcp-installatie zijn NIET
    hetzelfde. Het eerste is een keuze van de gebruiker (stil, exit 0), het
    tweede een defect (luid, exit non-zero). Tot deze test vielen ze samen en
    was een stil dode MCP-server niet van succes te onderscheiden."""

    def setUp(self):
        self.m = _load()

    def _main_with_stderr(self):
        import io
        from contextlib import redirect_stderr
        buf = io.StringIO()
        with redirect_stderr(buf):
            rc = self.m.main()
        return rc, buf.getvalue()

    def test_absent_package_exits_zero_and_names_the_package(self):
        self.m.MCPServer = None
        self.m.SDK_ABSENT = True
        self.m.SDK_ERROR = "ModuleNotFoundError: No module named 'mcp'"
        rc, err = self._main_with_stderr()
        self.assertEqual(rc, 0)
        self.assertIn("mcp", err)
        self.assertIn("not installed", err)

    def test_incompatible_sdk_exits_nonzero_and_names_the_exception(self):
        self.m.MCPServer = None
        self.m.SDK_ABSENT = False
        self.m.SDK_ERROR = ("mcp.server.mcpserver -> ModuleNotFoundError: no module; "
                            "mcp.server.fastmcp -> ModuleNotFoundError: no module")
        rc, err = self._main_with_stderr()
        self.assertNotEqual(rc, 0, "een kapotte SDK mag niet als succes eindigen")
        self.assertIn("did NOT start", err)
        self.assertIn("ModuleNotFoundError", err,
                      "de echte exception hoort in de melding te staan")

    def test_the_two_failure_paths_differ(self):
        self.m.MCPServer = None
        self.m.SDK_ABSENT, self.m.SDK_ERROR = True, "x"
        absent = self._main_with_stderr()
        self.m.SDK_ABSENT, self.m.SDK_ERROR = False, "y: broken"
        broken = self._main_with_stderr()
        self.assertNotEqual(absent[0], broken[0])
        self.assertNotEqual(absent[1], broken[1])

    def test_import_state_is_internally_consistent(self):
        """Precies een van de drie uitkomsten geldt, wat er ook geinstalleerd is.

        Deze assert kan niet vacuum slagen: hij dwingt dat het importblok zijn
        uitkomst ECHT vastlegt in plaats van alles tot None samen te vouwen."""
        m = _load()
        usable = m.MCPServer is not None
        if usable:
            self.assertFalse(m.SDK_ABSENT)
            self.assertEqual(m.SDK_ERROR, "")
        elif m.SDK_ABSENT:
            self.assertNotEqual(m.SDK_ERROR, "", "afwezigheid hoort ook vastgelegd")
        else:
            self.assertNotEqual(m.SDK_ERROR, "",
                                "onbruikbare SDK zonder reden = de oude stille fout")

    def test_module_is_importable_without_writing_to_stdout(self):
        """stdio-contract: de server MAG niets op stdout zetten dat geen MCP-bericht
        is. Het importvenster is het onze; een print() in een geimporteerde module
        corrumpeert de JSON-RPC-stroom."""
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            _load()
        self.assertEqual(buf.getvalue(), "", f"stdout vervuild bij import: {buf.getvalue()!r}")


class KbMcpTemporalToolTest(unittest.TestCase):
    def setUp(self):
        self.m = _load()
        self.orig = self.m.activity

        class FakeActivity:
            @staticmethod
            def what_did_i_do(*_a, **_k):
                return {"ok": True, "mode": "what_did_i_do", "events": [{"id": "e1", "source_ref": "x#L1"}]}

            @staticmethod
            def timeline(*_a, **_k):
                return {"ok": True, "mode": "timeline", "events": []}

            @staticmethod
            def weeklog(*_a, **_k):
                return {"ok": True, "mode": "weeklog", "rollup": {"event_count": 0}, "events": []}

            @staticmethod
            def topic_timeline(*_a, **_k):
                return {"ok": True, "mode": "topic_timeline", "events": []}

        self.m.activity = FakeActivity

    def tearDown(self):
        self.m.activity = self.orig

    def test_temporal_tool_wrappers_preserve_structured_results_by_default(self):
        """MCP migration step 3: the four tools return dict[str, Any] directly
        (activity.*()'s own return value, unwrapped) so structuredContent comes
        free from the SDK's return-annotation auto-detection."""
        expected = {"ok": True, "mode": "what_did_i_do",
                    "events": [{"id": "e1", "source_ref": "x#L1"}]}
        out = self.m.what_did_i_do_tool("2026-07-03")
        self.assertIsInstance(out, dict)
        self.assertEqual(out, expected)
        self.assertTrue(out["ok"])
        self.assertEqual(out["events"][0]["source_ref"], "x#L1")
        # Pins the migration's byte-identity claim: the SDK derives `content`
        # from the returned dict via these exact json.dumps kwargs, so the
        # dict must stay serialisable under them without loss or reordering.
        self.assertEqual(
            json.dumps(out, indent=2, ensure_ascii=False),
            json.dumps(expected, indent=2, ensure_ascii=False),
        )
        self.assertEqual(self.m.timeline_tool("vorige week")["mode"], "timeline")
        self.assertEqual(self.m.weeklog_tool()["mode"], "weeklog")
        self.assertEqual(self.m.topic_timeline_tool("Codex MCP")["mode"], "topic_timeline")

    def test_temporal_tool_wrappers_compact_results_for_interactive_clients(self):
        self.m.activity.what_did_i_do = lambda *_a, **_k: {
            "ok": True,
            "period": {"label": "2026-07-03"},
            "summary": {"event_count": 4},
            "events": [
                {
                    "title": "First event",
                    "summary": "A useful result.",
                    "source_ref": "09-memory/first.md#file",
                },
                {
                    "title": "Second event",
                    "summary": "Another useful result.",
                    "source_ref": "09-memory/second.md#file",
                },
                {
                    "title": "Third event",
                    "summary": "A third useful result.",
                    "source_ref": "09-memory/third.md#file",
                },
                {
                    "title": "Fourth event",
                    "summary": "This one is omitted.",
                    "source_ref": "09-memory/fourth.md#file",
                },
            ],
        }
        previous = os.environ.get("KENNISBANK_MCP_COMPACT_OUTPUT")
        os.environ["KENNISBANK_MCP_COMPACT_OUTPUT"] = "1"
        try:
            out = self.m.what_did_i_do_tool("2026-07-03")
        finally:
            if previous is None:
                os.environ.pop("KENNISBANK_MCP_COMPACT_OUTPUT", None)
            else:
                os.environ["KENNISBANK_MCP_COMPACT_OUTPUT"] = previous
        self.assertIsInstance(out, str)
        self.assertIn("First event", out)
        self.assertIn("Third event", out)
        self.assertIn("1 additional event(s) omitted.", out)
        self.assertNotIn("Fourth event", out)


if __name__ == "__main__":
    unittest.main()
