"""Wire-level tests voor scripts/kb-mcp.py: echte JSON-RPC over stdio.

Waarom een subprocess en niet build_server() aanroepen: de bugklasse die hier
telt zit NIET in de tool-functies (die zijn elders al gedekt) maar in het
transport. Een test die op ``MCPServer is None`` aftakt en in beide gevallen
slaagt bewijst niets -- dat was de oude test_build_server_none_without_mcp.
Deze tests praten daarom echt met het proces zoals een MCP-client dat doet:
newline-gescheiden JSON-RPC op stdin/stdout.

Skippt netjes wanneer het mcp-pakket ontbreekt: dan is er geen server om tegen
te praten, en dat is een geldige installatie.

Bewust GEEN embedding-afhankelijke tool in de call-assertie: ``review_pending``
leest alleen de memory-map, dus het harnas draait ook zonder Ollama (CI).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
SERVER = SCRIPTS_DIR / "kb-mcp.py"

# De acht tools die de server sinds v0.19 aanbiedt. Namen zijn een CONTRACT:
# ze staan in uitgerolde client-configuraties, dus een rename hoort hier te
# falen en niet stil door te glippen.
EXPECTED_TOOLS = {
    "recall", "capture", "review_pending", "review_decide",
    "what_did_i_do", "timeline", "weeklog", "topic_timeline",
}

LEGACY_PROTOCOL = "2025-06-18"


def _sdk_available() -> "tuple[bool, str]":
    """(bruikbaar, reden) volgens het importblok van de server zelf."""
    spec = importlib.util.spec_from_file_location("kb_mcp_probe", str(SERVER))
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:                       # pragma: no cover
        return False, f"kb-mcp.py niet importeerbaar: {exc}"
    if getattr(mod, "MCPServer", None) is None:
        return False, f"mcp-SDK onbruikbaar: {getattr(mod, 'SDK_ERROR', '?')}"
    return True, ""


class WireClient:
    """Minimale JSON-RPC-client over de stdio van een gespawnde server."""

    def __init__(self, vault: Path, timeout: float = 30.0):
        env = dict(os.environ)
        env["KENNISBANK_VAULT"] = str(vault)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, text=True, encoding="utf-8", errors="replace", bufsize=1)
        self.timeout = timeout
        self._next_id = 0
        self.raw_lines: list[str] = []

    def send(self, method: str, params=None, notify: bool = False):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if not notify:
            self._next_id += 1
            msg["id"] = self._next_id
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        return None if notify else self._next_id

    def read_result(self, want_id: int):
        """Lees tot het antwoord met dit id. Elke regel MOET geldige JSON zijn:
        dat is de stdout-hygiene-eis uit het stdio-transport."""
        import time
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            line = self.proc.stdout.readline()
            if not line:
                raise AssertionError(
                    f"server sloot stdout voor antwoord {want_id}; "
                    f"stderr: {self._drain_stderr()[:2000]}")
            self.raw_lines.append(line)
            stripped = line.strip()
            if not stripped:
                continue
            try:
                msg = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise AssertionError(
                    f"niet-JSON op stdout ({exc}): {stripped[:300]!r}") from None
            if msg.get("id") == want_id:
                return msg
        raise AssertionError(f"timeout op antwoord {want_id}; "
                             f"stderr: {self._drain_stderr()[:2000]}")

    def _drain_stderr(self) -> str:
        try:
            self.proc.stderr.flush()
        except Exception:
            pass
        return ""

    def close(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


class KbMcpWireTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ok, reason = _sdk_available()
        if not ok:
            raise unittest.SkipTest(reason)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-mcp-wire-"))
        vault = self.tmp / "vault"
        (vault / ".claude").mkdir(parents=True)
        (vault / "09-memory").mkdir(parents=True)
        self.client = WireClient(vault)
        self.addCleanup(self.client.close)
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def _handshake_legacy(self):
        rid = self.client.send("initialize", {
            "protocolVersion": LEGACY_PROTOCOL,
            "capabilities": {},
            "clientInfo": {"name": "kb-wire-test", "version": "1"},
        })
        reply = self.client.read_result(rid)
        self.assertNotIn("error", reply, f"initialize faalde: {reply}")
        self.client.send("notifications/initialized", {}, notify=True)
        return reply

    def test_legacy_initialize_succeeds(self):
        reply = self._handshake_legacy()
        self.assertIn("result", reply)
        self.assertIn("serverInfo", reply["result"])

    def test_tools_list_returns_the_expected_tool_set(self):
        self._handshake_legacy()
        rid = self.client.send("tools/list", {})
        reply = self.client.read_result(rid)
        self.assertNotIn("error", reply, f"tools/list faalde: {reply}")
        names = {t["name"] for t in reply["result"]["tools"]}
        self.assertEqual(names, EXPECTED_TOOLS,
                         "de tool-namen zijn een contract in uitgerolde client-configs")

    def test_tools_call_returns_content(self):
        self._handshake_legacy()
        rid = self.client.send("tools/call",
                               {"name": "review_pending", "arguments": {"k": 1}})
        reply = self.client.read_result(rid)
        self.assertNotIn("error", reply, f"tools/call faalde: {reply}")
        content = reply["result"].get("content") or []
        self.assertTrue(content, f"leeg content-veld: {reply}")
        self.assertTrue(any(c.get("type") == "text" for c in content))

    def test_annotations_reach_the_wire(self):
        """De annotaties moeten in tools/list staan, niet alleen in onze code.

        Dit is het verschil tussen 'kwarg gezet' en 'client ziet het': Claude Code
        leest readOnlyHint uit het tools/list-antwoord en leidt daar isReadOnly()
        en isConcurrencySafe() uit af."""
        self._handshake_legacy()
        rid = self.client.send("tools/list", {})
        reply = self.client.read_result(rid)
        tools = {t["name"]: t for t in reply["result"]["tools"]}
        read_only = {"recall", "review_pending", "what_did_i_do", "timeline",
                     "weeklog", "topic_timeline"}
        for name in read_only:
            ann = tools[name].get("annotations") or {}
            self.assertTrue(ann.get("readOnlyHint"),
                            f"{name} komt zonder readOnlyHint over de lijn: {ann}")
        self.assertFalse((tools["capture"].get("annotations") or {}).get("readOnlyHint", False))
        self.assertTrue((tools["review_decide"].get("annotations") or {}).get("destructiveHint"),
                        "review_decide hoort als destructief over de lijn te komen")

    def test_every_tool_has_a_distinct_english_description(self):
        """De beschrijving is het selectiesignaal dat een model leest. Twee tools
        met bijna dezelfde tekst maken de keuze een muntworp; timeline en weeklog
        waren precies dat geval en verwijzen nu expliciet naar elkaar."""
        self._handshake_legacy()
        rid = self.client.send("tools/list", {})
        tools = {t["name"]: (t.get("description") or "")
                 for t in self.client.read_result(rid)["result"]["tools"]}
        for name, desc in tools.items():
            self.assertTrue(desc.strip(), f"{name} heeft geen beschrijving")

        def words(text):
            import re
            return {w for w in re.findall(r"[a-z]{4,}", text.lower())}

        a, b = words(tools["timeline"]), words(tools["weeklog"])
        overlap = len(a & b) / max(len(a | b), 1)
        self.assertLess(overlap, 0.6,
                        f"timeline en weeklog lezen te gelijk (overlap {overlap:.2f})")
        self.assertIn("weeklog", tools["timeline"].lower(),
                      "timeline hoort naar weeklog te verwijzen voor de andere keuze")
        self.assertIn("timeline", tools["weeklog"].lower(),
                      "weeklog hoort naar timeline te verwijzen voor de andere keuze")

    def test_server_advertises_instructions(self):
        """De pull-nudge hoort op protocolniveau mee te komen, zodat een client
        zonder resource-ondersteuning hem alsnog krijgt."""
        reply = self._handshake_legacy()
        instructions = reply["result"].get("instructions") or ""
        self.assertIn("KennisBank", instructions,
                      f"initialize droeg geen instructions: {reply['result'].keys()}")

    def test_stdout_carries_only_json_rpc(self):
        """Elke regel die de server op stdout zet moet een MCP-bericht zijn.
        read_result() faalt al op niet-JSON; deze test maakt de eis expliciet
        en controleert de volledige geschiedenis van de sessie."""
        self._handshake_legacy()
        rid = self.client.send("tools/list", {})
        self.client.read_result(rid)
        self.assertTrue(self.client.raw_lines, "geen enkele regel ontvangen")
        for line in self.client.raw_lines:
            if not line.strip():
                continue
            msg = json.loads(line)          # faalt hard bij vervuiling
            self.assertEqual(msg.get("jsonrpc"), "2.0", f"geen JSON-RPC: {line[:200]!r}")


if __name__ == "__main__":
    unittest.main()
