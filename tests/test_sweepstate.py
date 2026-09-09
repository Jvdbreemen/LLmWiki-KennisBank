"""Tests voor scripts/_sweepstate.py - watermark + transcript-reader."""
from __future__ import annotations

import gc
import json
import os
import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _sweepstate as ss  # noqa: E402


class SweepStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-sweep-"))
        self.vault = self.tmp / "vault"
        self.tdir = self.vault / "01-raw" / "transcripts"
        self.tdir.mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _t(self, name, records):
        p = self.tdir / name
        p.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
        return p

    def test_pending_excludes_marked(self):
        self._t("a.jsonl", [{"type": "user", "message": {"role": "user", "content": "hoi"}}])
        self._t("b.jsonl", [{"type": "user", "message": {"role": "user", "content": "hoi"}}])
        self.assertEqual({p.stem for p in ss.pending()}, {"a", "b"})
        ss.mark(["a"])
        self.assertEqual({p.stem for p in ss.pending()}, {"b"})

    def test_mark_is_idempotent(self):
        self._t("a.jsonl", [{"type": "user", "message": {"role": "user", "content": "x"}}])
        ss.mark(["a"])
        ss.mark(["a"])
        self.assertEqual(ss.pending(), [])

    def test_transcript_text_reduces_messages(self):
        p = self._t("c.jsonl", [
            {"type": "user", "message": {"role": "user", "content": "Repareer de bug"}},
            {"type": "assistant", "message": {"role": "assistant",
                "content": [{"type": "text", "text": "Token-expiry fix"}]}},
        ])
        txt = ss.transcript_text(p)
        self.assertIn("Repareer de bug", txt)
        self.assertIn("Token-expiry fix", txt)

    def test_transcript_text_failsoft(self):
        bad = self.tdir / "bad.jsonl"
        bad.write_text("{ kapot json", encoding="utf-8")
        self.assertEqual(ss.transcript_text(bad), "")

    def test_block_text_none_content(self):
        """COVERAGE: _block_text(None) → lege string."""
        self.assertEqual(ss._block_text(None), "")

    def test_block_text_mixed_list_only_text_extracted(self):
        """COVERAGE: gemengde content-lijst → alleen text-blokken worden geëxtraheerd."""
        content = [
            {"type": "tool_use", "id": "some-tool-id"},
            {"type": "text", "text": "hello"},
            {"type": "image", "source": {"type": "base64", "data": "..."}},
            {"type": "text", "text": "world"},
        ]
        result = ss._block_text(content)
        self.assertIn("hello", result)
        self.assertIn("world", result)
        # Niet-tekst-blokken mogen NIET in de output belanden
        self.assertNotIn("tool_use", result)
        self.assertNotIn("base64", result)


if __name__ == "__main__":
    unittest.main()


class SweepLockOwnershipTest(unittest.TestCase):
    """De sweep-lock als bezit, niet als leeftijdsstempel.

    Twee defecten die deze tests bewaken, beide gevonden in review nadat de
    lease-versie al gemerged was:

    1. run_sweep startte onvoorwaardelijk een lease en gaf het slot
       onvoorwaardelijk vrij, ook als het proces het nooit verwierf. Er zijn
       drie aanroepers en twee daarvan slaan sweep-launch over
       (commands/kennisbank/rebuild-memory.md, scripts/index-launch.py), dus
       die verwijderden het slot van een sweep die nog draaide.
    2. De lease tikte door zolang het proces leefde. Een vastgelopen sweep hield
       daarmee zijn slot voor onbepaalde tijd, waar de oude leeftijdslogica na
       STALE_SEC vanzelf herstelde.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-lock-"))
        (self.tmp / ".claude").mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_tweede_verwerving_faalt_en_release_geeft_vrij(self):
        tok = ss.acquire_lock(self.tmp)
        self.assertIsNotNone(tok)
        self.assertIsNone(ss.acquire_lock(self.tmp), "single-flight")
        self.assertTrue(ss.release_lock(self.tmp, tok))
        self.assertIsNotNone(ss.acquire_lock(self.tmp), "na vrijgave weer te nemen")

    def test_release_verwijdert_het_slot_van_een_ander_niet(self):
        """De regressie. Een sweep die het slot nooit nam mag het niet weggooien."""
        eigenaar = ss.acquire_lock(self.tmp)
        vreemde = "999999:deadbeefdeadbeef"
        self.assertFalse(ss.release_lock(self.tmp, vreemde),
                         "een vreemd token mag niets vrijgeven")
        self.assertTrue(ss.lock_path(self.tmp).exists(),
                        "het slot van de eigenaar staat er nog")
        self.assertTrue(ss.release_lock(self.tmp, eigenaar))

    def test_stale_lock_wordt_heroverd(self):
        ss.acquire_lock(self.tmp)
        lock = ss.lock_path(self.tmp)
        oud = time.time() - ss.STALE_SEC - 10
        os.utime(lock, (oud, oud))
        self.assertIsNotNone(ss.acquire_lock(self.tmp), "verweesd slot is herbruikbaar")

    def test_context_manager_geeft_altijd_vrij(self):
        """Elke vroege return en elke exception moet door de finally lopen."""
        with ss.sweep_lock(self.tmp) as owned:
            self.assertTrue(owned)
            self.assertTrue(ss.lock_path(self.tmp).exists())
        self.assertFalse(ss.lock_path(self.tmp).exists(), "vrijgegeven bij nette exit")

        with self.assertRaises(RuntimeError):
            with ss.sweep_lock(self.tmp) as owned:
                self.assertTrue(owned)
                raise RuntimeError("boem")
        self.assertFalse(ss.lock_path(self.tmp).exists(),
                         "ook vrijgegeven na een exception")

    def test_tweede_sweep_krijgt_false_en_raakt_het_slot_niet(self):
        buiten = ss.acquire_lock(self.tmp)
        with ss.sweep_lock(self.tmp) as owned:
            self.assertFalse(owned, "er draait al een sweep")
        self.assertEqual(ss._read_token(ss.lock_path(self.tmp)), buiten,
                         "het slot is nog van de eerste houder")

    def test_lease_houdt_het_slot_levend(self):
        origineel = ss.LEASE_REFRESH_SEC
        ss.LEASE_REFRESH_SEC = 0.05
        try:
            with ss.sweep_lock(self.tmp) as owned:
                self.assertTrue(owned)
                lock = ss.lock_path(self.tmp)
                oud = time.time() - ss.STALE_SEC - 600
                os.utime(lock, (oud, oud))
                self.assertTrue(ss.is_stale(lock), "opzet: nu is hij stale")
                deadline = time.time() + 5
                while time.time() < deadline and ss.is_stale(lock):
                    time.sleep(0.05)
                self.assertFalse(ss.is_stale(lock),
                                 "een draaiende sweep houdt zijn slot")
        finally:
            ss.LEASE_REFRESH_SEC = origineel

    def test_lease_stopt_bij_het_plafond(self):
        """Een tikkende thread bewijst dat het proces leeft, niet dat er voortgang is."""
        r, m = ss.LEASE_REFRESH_SEC, ss.LEASE_MAX_SEC
        ss.LEASE_REFRESH_SEC, ss.LEASE_MAX_SEC = 0.05, 0.15
        try:
            with ss.sweep_lock(self.tmp):
                lock = ss.lock_path(self.tmp)
                time.sleep(0.5)          # ruim voorbij het plafond
                gestopt = lock.stat().st_mtime
                time.sleep(0.4)
                self.assertEqual(lock.stat().st_mtime, gestopt,
                                 "voorbij het plafond mag de lease niet meer tikken")
        finally:
            ss.LEASE_REFRESH_SEC, ss.LEASE_MAX_SEC = r, m

    def test_lease_volgt_geen_gewijzigde_vault(self):
        """De thread bindt het vault-pad een keer.

        Resolveerde hij vault_root() per tik, dan schreef een thread die een test
        overleeft daarna in de vault waar KENNISBANK_VAULT naartoe is hersteld.
        Gemeten gedrag van de vorige versie; de tests gebruiken juist een
        tijdelijke vault om productie nooit te raken.
        """
        ander = Path(tempfile.mkdtemp(prefix="kb-ander-"))
        (ander / ".claude").mkdir(parents=True)
        origineel = ss.LEASE_REFRESH_SEC
        ss.LEASE_REFRESH_SEC = 0.05
        bewaard = os.environ.get("KENNISBANK_VAULT")
        try:
            with ss.sweep_lock(self.tmp):
                os.environ["KENNISBANK_VAULT"] = str(ander)
                time.sleep(0.4)
                self.assertFalse((ander / ".claude" / ss.LOCK_NAME).exists(),
                                 "de lease hoort bij de vault waar hij begon")
        finally:
            ss.LEASE_REFRESH_SEC = origineel
            if bewaard is None:
                os.environ.pop("KENNISBANK_VAULT", None)
            else:
                os.environ["KENNISBANK_VAULT"] = bewaard
            import shutil
            shutil.rmtree(ander, ignore_errors=True)


class VerweesdeLockTest(unittest.TestCase):
    """Een lock van een proces dat niet meer bestaat (TASK-247).

    De tijdlease is met opzet niet op PID gebaseerd: PIDs worden hergebruikt,
    dus "dit PID bestaat" bewijst niet dat de sweep leeft. De omkering kent die
    beperking niet, en dat is het hele gat dat hier gedicht wordt. Bestaat het
    genoemde PID niet, dan is de houder dood en hoeft niemand een uur te wachten.

    Aanleiding, gemeten: twee weeslocks in twee dagen in dezelfde vault. Op
    2026-09-08 noemde er een PID 17192, op 2026-09-09 om 19:51 PID 30968; geen
    van beide bestond nog. Beide moesten met de hand weg om een sweep te laten
    starten, want de lease liep pas na 3600 s af.
    """

    #: Staat voor een houder die er niet meer is. Het getal zelf doet niets; de
    #: geinjecteerde probe bepaalt of hij leeft.
    DOOD_PID = 424242

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-orphan-"))
        (self.tmp / ".claude").mkdir(parents=True)
        self.lock = ss.lock_path(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _probe(self, *levend: int) -> None:
        """Laat de probe precies deze PIDs levend noemen.

        Een ECHT dood PID is geen reproduceerbare fixture. Windows hergebruikt
        PID-nummers, en OpenProcess opent een afgelopen proces zolang er nog een
        handle op staat. Gemeten op 2026-09-10: hetzelfde zojuist beeindigde PID
        las in de ene run False en even later in een andere True, en een test die
        erop bouwde faalde en slaagde afwisselend zonder codewijziging.

        De probe zelf hoort niet bij deze module -- het is `_common.pid_alive`,
        gedekt in test_common.py. Wat hier getoetst wordt is het BELEID eromheen:
        wanneer telt een dode houder als wees, en wanneer juist niet.
        """
        echt = ss.pid_alive
        ss.pid_alive = lambda pid: pid in levend
        self.addCleanup(lambda: setattr(ss, "pid_alive", echt))

    def _leg_lock(self, token: str, leeftijd: float = 6.0) -> None:
        """Een lock met dit token, standaard net voorbij PID_GRACE_SEC.

        De leeftijd blijft ver binnen STALE_SEC, dus wat deze tests aantonen is
        altijd het PID-pad en nooit de tijdlease. De kerntests bevestigen dat met
        een assertie op is_stale.
        """
        self.lock.write_text(token, encoding="utf-8")
        if leeftijd:
            toen = time.time() - leeftijd
            os.utime(self.lock, (toen, toen))

    def _mijn(self, pid: int) -> str:
        return f"{socket.gethostname()}:{pid}:deadbeefdeadbeef"

    # -- de twee richtingen -------------------------------------------------

    def test_een_lock_van_een_verdwenen_proces_is_meteen_over_te_nemen(self):
        """De kernclaim. Voor TASK-247 wachtte dit STALE_SEC uit."""
        self._probe()
        self._leg_lock(self._mijn(self.DOOD_PID))
        self.assertFalse(ss.is_stale(self.lock),
                         "opzet: de lease is nog lang niet verlopen")
        # Alleen de gedrags-assertie. is_orphaned hierboven laat deze test tegen
        # de oude implementatie falen op een ontbrekende functie in plaats van op
        # het defect, en eronder kijkt hij naar het verkeerde bestand:
        # acquire_lock heeft het token dan al vervangen door dat van dit proces.
        self.assertIsNotNone(ss.acquire_lock(self.tmp),
                             "een dode houder mag niemand ophouden")

    def test_is_orphaned_herkent_een_verdwenen_houder(self):
        """Dezelfde claim een laag lager, zonder de lock over te nemen."""
        self._probe()
        self._leg_lock(self._mijn(self.DOOD_PID))
        self.assertFalse(ss.is_stale(self.lock), "opzet: niet via de tijdlease")
        self.assertTrue(ss.is_orphaned(self.lock))

    def test_een_lock_van_een_levend_proces_blijft_liggen(self):
        """De tegenwaarborg: PID-hergebruik mag geen levende lock vrijgeven."""
        self._probe(os.getpid())
        self._leg_lock(self._mijn(os.getpid()))
        self.assertIsNone(ss.acquire_lock(self.tmp),
                          "single-flight geldt zolang de houder leeft")
        self.assertFalse(ss.is_orphaned(self.lock))

    # -- alles wat onzeker is, respecteert de lock --------------------------

    def test_een_kersverse_lock_wordt_niet_op_de_pid_afgeschreven(self):
        """De grace.

        De probe geeft geen "weet ik niet" terug maar valt bij twijfel naar dood,
        en op Windows leest hij een zombie als levend zolang er een handle op
        staat. Zonder ondergrens geeft een probe die zich vergist een levende
        lock meteen vrij. Onder PID_GRACE_SEC telt daarom alleen de tijd.
        """
        self._probe()
        self._leg_lock(self._mijn(self.DOOD_PID), leeftijd=0)
        self.assertFalse(ss.is_orphaned(self.lock))
        self.assertIsNone(ss.acquire_lock(self.tmp))

    def test_een_oud_tweedelig_token_krijgt_geen_pid_oordeel(self):
        """Zonder host in het token weet je niet over welke machine je oordeelt.

        Het paar met de eerste test is wat telt: hetzelfde dode PID wordt in het
        nieuwe formaat wel overgenomen en in het oude niet.
        """
        self._probe()
        self._leg_lock(f"{self.DOOD_PID}:deadbeefdeadbeef")
        self.assertIsNone(ss.acquire_lock(self.tmp))
        self.assertFalse(ss.is_orphaned(self.lock))

    def test_een_pid_van_een_andere_machine_krijgt_geen_oordeel(self):
        """Op een gedeelde vault zegt een vreemd PID hier niets.

        Zonder deze grens steelt de ene machine het slot van een sweep die op de
        andere gewoon draait, puur omdat dat nummer hier vrij is.
        """
        self._probe()
        self._leg_lock(f"eenanderemachine:{self.DOOD_PID}:deadbeefdeadbeef")
        self.assertIsNone(ss.acquire_lock(self.tmp))
        self.assertFalse(ss.is_orphaned(self.lock))

    def test_een_onleesbaar_token_krijgt_geen_oordeel(self):
        self._probe()
        self._leg_lock("rommel")
        self.assertIsNone(ss.acquire_lock(self.tmp))
        self.assertFalse(ss.is_orphaned(self.lock))

    def test_een_leeg_token_krijgt_geen_oordeel(self):
        """acquire_lock schrijft het token NA het aanmaken met O_EXCL.

        Tussen die twee stappen is het bestand leeg. Dat als dode houder lezen
        geeft het slot aan de verwerver die de race juist verloor.
        """
        self._probe()
        self._leg_lock("")
        self.assertIsNone(ss.acquire_lock(self.tmp))
        self.assertFalse(ss.is_orphaned(self.lock))

    def test_wie_te_laat_is_gooit_het_verse_slot_van_een_ander_niet_weg(self):
        """De race tussen beoordelen en opruimen.

        Twee verwervers zien dezelfde wees. De eerste ruimt op en neemt; de
        tweede mag dat verse slot niet alsnog weggooien. Hier gesimuleerd door
        het bestand te vervangen op het moment dat het oordeel valt.
        """
        self._probe()
        self._leg_lock(self._mijn(self.DOOD_PID))
        echte_is_free = ss.is_free

        def is_free_maar_een_ander_was_sneller(lock):
            uitkomst = echte_is_free(lock)
            lock.write_text("eenanderewinnaar:1:beef", encoding="utf-8")
            return uitkomst

        ss.is_free = is_free_maar_een_ander_was_sneller
        try:
            self.assertIsNone(ss.acquire_lock(self.tmp),
                              "het slot was al van een ander toen we opruimden")
        finally:
            ss.is_free = echte_is_free
        self.assertEqual(self.lock.read_text(encoding="utf-8"),
                         "eenanderewinnaar:1:beef",
                         "het verse slot van de winnaar staat er nog")

    # -- het token ----------------------------------------------------------

    def test_het_token_noemt_host_en_pid(self):
        host, pid = ss._owner(ss._new_token())
        self.assertEqual(host, socket.gethostname())
        self.assertEqual(pid, os.getpid())

    # -- de gate van de launcher -------------------------------------------

    def test_de_launcher_ziet_een_verweesd_slot_niet_meer_als_levend(self):
        """Dit was het zichtbare symptoom: "er draait al een sweep"."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "sweep_launch_orphan", str(SCRIPTS_DIR / "sweep-launch.py"))
        launch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launch)

        bewaard = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.tmp)
        try:
            self._probe()
            self._leg_lock(self._mijn(self.DOOD_PID))
            self.assertFalse(launch._lock_alive(),
                             "een dode houder is geen draaiende sweep")
            self._probe(os.getpid())
            self._leg_lock(self._mijn(os.getpid()))
            self.assertTrue(launch._lock_alive(),
                            "een levende houder houdt de gate dicht")
        finally:
            if bewaard is None:
                os.environ.pop("KENNISBANK_VAULT", None)
            else:
                os.environ["KENNISBANK_VAULT"] = bewaard
