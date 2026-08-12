"""De sessiestart moet ALTIJD melden waar je aan toe bent.

Een stille sessiestart is niet te onderscheiden van een kapotte: beide leveren
niets op. Deze tests leggen vast dat de statusregel er altijd is, dat hij een
aflezing blijft (geen berekening op de hot path), en dat elk onleesbaar
onderdeel wordt overgeslagen in plaats van de melding te breken.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script


class StatusLineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-status-"))
        (self.tmp / ".claude").mkdir(parents=True)
        (self.tmp / "graphify-out").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.tmp)
        self.mod = load_script("kb-session-start.py")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _index(self, docs=3, fingerprint=None):
        db = self.tmp / ".claude" / "kb-index.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE docs (doc_id INTEGER PRIMARY KEY, path TEXT)")
        conn.executemany("INSERT INTO docs(path) VALUES (?)",
                         [(f"09-memory/{i}.md",) for i in range(docs)])
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()
        conn.close()
        # Sinds TASK-75 woont de vingerafdruk in kb-graph.db. Het argument blijft
        # hier staan zodat de tests leesbaar blijven, maar het schrijft elders.
        if fingerprint is not None:
            self._graphdb(fingerprint)

    def _graphdb(self, fingerprint=None):
        """De graafindex als EIGEN bestand -- de kern van TASK-75."""
        db = self.tmp / ".claude" / "kb-graph.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        if fingerprint is not None:
            conn.execute("INSERT INTO meta VALUES ('graph_fingerprint', ?)", (fingerprint,))
        conn.commit()
        conn.close()

    def _graph(self, inhoud=b'{"nodes":[],"links":[]}'):
        g = self.tmp / "graphify-out" / "graph.json"
        g.write_bytes(inhoud)
        return g

    # --- altijd een melding -------------------------------------------------

    def test_lege_vault_geeft_toch_een_regel(self):
        regel = self.mod.status_line(self.tmp, worker_running=False)
        self.assertTrue(regel.startswith("KennisBank:"))
        self.assertIn("onderhoud gestart", regel)

    def test_draaiende_worker_wordt_zo_benoemd(self):
        regel = self.mod.status_line(self.tmp, worker_running=True)
        self.assertIn("draait al", regel)
        self.assertNotIn("gestart op de achtergrond", regel)

    # --- inhoud -------------------------------------------------------------

    def test_documenttelling_komt_uit_de_index(self):
        self._index(docs=7)
        self.assertIn("index 7 documenten", self.mod.status_line(self.tmp, worker_running=False))

    def test_actuele_graaf_wordt_gemeld(self):
        g = self._graph()
        st = g.stat()
        self._index(fingerprint=f"{int(st.st_mtime)}:{st.st_size}")
        self.assertIn("graaf actueel", self.mod.status_line(self.tmp, worker_running=False))

    def test_verouderde_graaf_wordt_gemeld(self):
        self._graph()
        self._index(fingerprint="0:0")
        self.assertIn("graaf verouderd", self.mod.status_line(self.tmp, worker_running=False))

    def test_niet_lege_rebuildvlag_wordt_gemeld(self):
        (self.tmp / "graphify-out" / ".needs-rebuild").write_text("02-wiki/x.md\n", encoding="utf-8")
        self.assertIn("rebuild staat klaar", self.mod.status_line(self.tmp, worker_running=False))

    def test_lege_rebuildvlag_meldt_niets(self):
        (self.tmp / "graphify-out" / ".needs-rebuild").write_text("", encoding="utf-8")
        self.assertNotIn("rebuild", self.mod.status_line(self.tmp, worker_running=False))

    # --- koud embedding-model ------------------------------------------------

    def _embed(self, resident, warming=False):
        """Vervang de embeddings-module door een dubbel met een bekende staat."""
        gezien = {}

        class Dubbel:
            def is_resident(_self, timeout=0.1):
                gezien["timeout"] = timeout
                if isinstance(resident, Exception):
                    raise resident
                return resident

            def warm_in_progress(_self):
                return warming

        self.mod._embeddings_module = lambda _vault: Dubbel()
        return gezien

    def test_modelprobe_krijgt_een_hot_path_plafond(self):
        """De probe is een netwerkstap in een functie met een 250ms-budget.

        Zonder expliciet plafond erft hij de default van is_resident (500ms), en
        dat is op een machine waar een dichte poort uittimet in plaats van
        weigert al meer dan twee keer het hele budget."""
        gezien = self._embed(resident=True)
        self.mod.status_line(self.tmp, worker_running=False)
        self.assertLessEqual(gezien["timeout"], 0.1)

    def test_warm_model_wordt_niet_genoemd(self):
        """Alleen de misser hoort op te vallen; een werkend model is geen nieuws."""
        self._embed(resident=True)
        self.assertNotIn("embedding-model", self.mod.status_line(self.tmp, worker_running=False))

    def test_koud_model_wordt_gemeld(self):
        self._embed(resident=False)
        self.assertIn("embedding-model koud", self.mod.status_line(self.tmp, worker_running=False))

    def test_koud_model_meldt_de_lopende_opwarming(self):
        self._embed(resident=False, warming=True)
        self.assertIn("wordt geladen", self.mod.status_line(self.tmp, worker_running=False))

    def test_onbekende_staat_zwijgt(self):
        """Een andere provider of een onbereikbare Ollama levert None. Daarop
        'koud' melden zou een gok zijn die de gebruiker naar VRAM stuurt die
        niets mankeert."""
        self._embed(resident=None)
        self.assertNotIn("embedding-model", self.mod.status_line(self.tmp, worker_running=False))

    def test_kapotte_probe_breekt_de_regel_niet(self):
        self._embed(resident=RuntimeError("stuk"))
        regel = self.mod.status_line(self.tmp, worker_running=False)
        self.assertTrue(regel.startswith("KennisBank:"))
        self.assertNotIn("embedding-model", regel)

    def test_telling_krijgt_voorbehoud_tijdens_onderhoud(self):
        """Een tabel die gevuld wordt levert een momentopname. Het getal zonder
        voorbehoud tonen is stelliger dan de werkelijkheid toestaat."""
        self._index(docs=258)
        self.assertIn("index 258 documenten (bijwerken)",
                      self.mod.status_line(self.tmp, worker_running=True))
        self.assertNotIn("(bijwerken)",
                         self.mod.status_line(self.tmp, worker_running=False))

    def test_graaf_op_schijf_maar_niet_in_de_index_wordt_gemeld(self):
        """Zwijgen hierover is hoe de graaftabellen ongemerkt uit kb-index.db
        verdwenen (TASK-75). De statusregel hoort dat zichtbaar te maken."""
        self._graph()
        self._index(fingerprint=None)
        self.assertIn("graaf niet geladen",
                      self.mod.status_line(self.tmp, worker_running=False))

    def test_graafstatus_overleeft_een_verdwenen_embedindex(self):
        """TASK-75, AC #3. Tijdens een herbouw kan kb-index.db weg zijn of half
        gevuld. De graafstatus zat eerder GENEST in die tak en viel dan stil --
        precies op het moment dat je wilt weten of de graaf er nog is."""
        g = self._graph()
        st = g.stat()
        self._graphdb(f"{int(st.st_mtime)}:{st.st_size}")
        self.assertFalse((self.tmp / ".claude" / "kb-index.db").exists())
        regel = self.mod.status_line(self.tmp, worker_running=True)
        self.assertIn("graaf actueel", regel)
        self.assertNotIn("niet geladen", regel)

    def test_geen_graaf_op_schijf_meldt_niets_over_de_graaf(self):
        self._index(fingerprint=None)
        self.assertNotIn("graaf", self.mod.status_line(self.tmp, worker_running=False))

    # --- leeft de worker echt? ----------------------------------------------

    def _lock(self, leeftijd_sec: float, pid: int | None = None):
        lock = self.tmp / ".claude" / ".kb-index-worker.lock"
        if pid is None:
            pid = os.getpid()
        lock.write_text(str(pid), encoding="utf-8")
        t = time.time() - leeftijd_sec
        os.utime(lock, (t, t))
        return lock

    def test_verse_lock_telt_als_draaiend(self):
        self._lock(leeftijd_sec=5)
        self.assertTrue(self.mod.worker_is_alive(self.tmp))

    def test_verweesde_lock_telt_niet_als_draaiend(self):
        """Gemeten geval: lock met PID 31772 bleef liggen terwijl de levende
        worker 22552 was. Zonder deze regel zegt de statusregel voor altijd
        'onderhoud draait al' zonder dat er iets draait."""
        il = load_script("index-launch.py")
        self._lock(leeftijd_sec=il.STALE_SEC + 60)
        self.assertFalse(self.mod.worker_is_alive(self.tmp))

    def test_geen_lock_telt_niet_als_draaiend(self):
        self.assertFalse(self.mod.worker_is_alive(self.tmp))

    def test_vervaltijd_komt_uit_index_launch(self):
        """Twee losse antwoorden op 'leeft de houder nog' lopen onvermijdelijk
        uiteen. Deze test faalt zodra kb-session-start een eigen grens krijgt."""
        il = load_script("index-launch.py")
        self._lock(leeftijd_sec=il.STALE_SEC - 30)
        self.assertTrue(self.mod.worker_is_alive(self.tmp))
        self._lock(leeftijd_sec=il.STALE_SEC + 30)
        self.assertFalse(self.mod.worker_is_alive(self.tmp))

    # --- fail-open ----------------------------------------------------------

    def test_kapotte_index_breekt_de_melding_niet(self):
        (self.tmp / ".claude" / "kb-index.db").write_text("dit is geen sqlite", encoding="utf-8")
        regel = self.mod.status_line(self.tmp, worker_running=False)
        self.assertTrue(regel.startswith("KennisBank:"))
        self.assertNotIn("index", regel)

    def test_index_zonder_meta_tabel_breekt_niet(self):
        db = self.tmp / ".claude" / "kb-index.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE docs (doc_id INTEGER PRIMARY KEY, path TEXT)")
        conn.commit()
        conn.close()
        self.assertIn("index 0 documenten",
                     self.mod.status_line(self.tmp, worker_running=False))

    def test_onbestaande_vault_breekt_niet(self):
        regel = self.mod.status_line(self.tmp / "bestaat-niet", worker_running=False)
        self.assertTrue(regel.startswith("KennisBank:"))

    def test_statusregel_is_cp1252_veilig(self):
        """_emit schrijft met ensure_ascii=False naar stdout. Op Windows is die
        stdout standaard cp1252; een teken daarbuiten gooit UnicodeEncodeError,
        die de brede except in main() opslokt -> LEGE sessiestart, exitcode 0.
        Precies het stille falen dat deze statusregel moest wegnemen. Dit is
        echt gebeurd met een bullet (U+00B7) als scheidingsteken."""
        self._index(docs=42)
        self._graph()
        (self.tmp / "graphify-out" / ".needs-rebuild").write_text("x\n", encoding="utf-8")
        regel = self.mod.status_line(self.tmp, worker_running=True)
        regel.encode("cp1252")   # faalt hard bij een niet-cp1252 teken
        self.assertTrue(regel.isascii(), f"niet-ASCII in statusregel: {regel!r}")

    def test_emit_overleeft_niet_ascii_uit_een_kindscript(self):
        """_emit geeft de uitvoer van ALLE kindscripts door. Een accent in een
        bestandsnaam mag niet het hele sessierapport laten verdwijnen."""
        import io
        rapport = "memory-notify.py: café-notitie · 3 stuks — klaar"
        buf = io.StringIO()
        oud = sys.stdout
        sys.stdout = buf
        try:
            self.mod._emit("claude", rapport)
        finally:
            sys.stdout = oud
        uit = buf.getvalue()
        self.assertTrue(uit, "_emit schreef niets")
        uit.encode("cp1252")   # moet op een Windows-console te schrijven zijn
        # en de leeskant krijgt de tekens ongeschonden terug
        import json as _json
        terug = _json.loads(uit)["hookSpecificOutput"]["additionalContext"]
        self.assertIn(rapport, terug)

    # --- hot path -----------------------------------------------------------

    def test_blijft_binnen_het_budget(self):
        """Een aflezing, geen berekening. Loopt dit uit de hand, dan hoort het
        werk naar de achtergrondworker en niet naar de sessiestart.

        De modelprobe wordt hier bewust gestubd. Zonder stub doet deze test vijf
        echte /api/ps-calls, en dan meet hij of Ollama toevallig draait in plaats
        van wat status_line zelf kost -- op een machine waar een dichte poort
        uittimet in plaats van weigert kost dat seconden. Het plafond van de
        probe zelf is een aparte afspraak, bewaakt door
        test_modelprobe_krijgt_een_hot-path-plafond."""
        self._embed(resident=True)
        self._index(docs=500)
        self._graph()
        t = time.perf_counter()
        for _ in range(5):
            self.mod.status_line(self.tmp, worker_running=False)
        gemiddeld_ms = (time.perf_counter() - t) / 5 * 1000
        self.assertLess(gemiddeld_ms, self.mod.STATUS_BUDGET_MS,
                        f"statusregel kostte {gemiddeld_ms:.0f} ms")


if __name__ == "__main__":
    unittest.main()
