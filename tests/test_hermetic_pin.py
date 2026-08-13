"""The hermeticity pin has to be fast, and that has to be measured.

`tests/__init__.py` used to pin `127.0.0.1:1` and assert in a comment that a
closed port refuses instantly. On this machine it does not: every closed
loopback port drops the connection and the caller waits out its full timeout —
2012 ms measured, on port 1, on port 9, and on a freshly released ephemeral
port alike. It is a firewall rule, not a property of port 1.

That made every network-touching test pay a timeout it did not need, and made
any wall-clock assertion a latent flake that behaves differently on Linux CI
than on Windows. A comment cannot catch that regressing; a measurement can
(TASK-141).
"""
from __future__ import annotations

import os
import socket
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

import tests as _suite


class HermeticPinTest(unittest.TestCase):
    def test_the_pin_is_actually_set(self):
        self.assertEqual(os.environ.get("KB_EMBED_ENDPOINT"), _suite.DEAD_ENDPOINT)
        self.assertEqual(os.environ.get("KB_LLM_ENDPOINT"), _suite.DEAD_ENDPOINT)

    def test_ambient_configuration_cannot_switch_hermeticity_off(self):
        """Found by this test failing: the pin was off on this machine.

        `~/.claude/settings.json` exports KB_LLM_ENDPOINT=http://localhost:11434
        for every session, because the KennisBank scripts need it for real work.
        With `setdefault`, the pin therefore never fired for the LLM seam on the
        machine where Ollama actually runs — the exact case it was written for —
        while CI, which has no such variable, stayed pinned.
        """
        self.assertNotIn("11434", os.environ.get("KB_LLM_ENDPOINT", ""),
                         "de suite mag een echt model nooit kunnen bereiken")

    def test_the_pin_points_at_loopback(self):
        """Hermetic first: whatever else changes, it must not leave the machine."""
        host = urllib.parse.urlparse(_suite.DEAD_ENDPOINT).hostname
        self.assertEqual(host, "127.0.0.1")

    def test_connecting_fails_fast_instead_of_timing_out(self):
        """The premise the old comment asserted, now measured.

        250 ms is generous for loopback and far below the 2 s a dropped
        connection costs, so this separates "refused" from "waited" without
        being sensitive to a slow machine.
        """
        parsed = urllib.parse.urlparse(_suite.DEAD_ENDPOINT)
        start = time.monotonic()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        try:
            s.connect((parsed.hostname, parsed.port))
        except OSError:
            pass  # geweigerd is ook goed; het gaat om de TIJD
        finally:
            s.close()
        verstreken = time.monotonic() - start
        self.assertLess(verstreken, 0.25,
                        f"de pin wachtte {verstreken * 1000:.0f} ms in plaats van "
                        f"meteen te falen; dan betaalt elke netwerk-test dat weer")

    def test_an_http_call_to_the_pin_fails_fast_too(self):
        """What the seams actually do: urlopen, not a bare socket."""
        start = time.monotonic()
        with self.assertRaises((urllib.error.URLError, OSError)):
            urllib.request.urlopen(_suite.DEAD_ENDPOINT + "/api/tags", timeout=2.0)
        verstreken = time.monotonic() - start
        self.assertLess(verstreken, 0.5,
                        f"urlopen deed {verstreken * 1000:.0f} ms over een dood "
                        f"endpoint; dat telt op over de hele suite")

    def test_the_embed_seam_gives_up_quickly(self):
        """End to end: the fail-soft path is fast, not merely correct."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import _embeddings as emb
        start = time.monotonic()
        self.assertIsNone(emb.embed("ping"))
        verstreken = time.monotonic() - start
        self.assertLess(verstreken, 1.0,
                        f"emb.embed deed {verstreken * 1000:.0f} ms over een dood "
                        f"endpoint")


if __name__ == "__main__":
    unittest.main()
