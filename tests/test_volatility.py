"""The update rule belongs in the structure, not in a model's judgement.

`memory_type` says what a memory is ABOUT. None of its four values says
"replace me when the value changes", so every reconcile and supersede decision
re-derived that from prose. Measured against the vault's own supersede
decisions, that derivation scored 7/20 (qwen3.5:4b), 5/20 (qwen3.5:9b) and
4/20 (claude haiku) — a question no model should be asked three times a day.

`volatility` answers it once, at write time: state may be replaced, an event
never is. These tests hold the ordering that makes the safe default safe
(TASK-146).
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _extract  # noqa: E402
import _maintenance  # noqa: E402
import _memory  # noqa: E402
import _reconcile  # noqa: E402


class ConfigShapeTest(unittest.TestCase):
    """The three bodies that decide whether the fallback is trustworthy."""

    def test_a_setting_assignment_is_config_shaped(self):
        for body in (
            "num_ctx = 8192 zodat het antwoord in het venster past.",
            "RECONCILE_THRESHOLD: 0.75 na de A/B-meting.",
            "De judge draait op qwen3.5:4b sinds de VRAM-meting.",
            "retrieve_top_n staat op 3.",
            "memory_capture staat op true in kennisbank-settings.json.",
        ):
            self.assertTrue(_memory.looks_like_config(body), body)

    def test_a_past_tense_fix_carrying_a_version_is_not(self):
        """The failure mode the narrow pattern exists to avoid.

        "Fixed in v0.29.0" is an event that happens to name a version. Reading
        it as a setting would make history supersedable — the one irreversible
        error this whole axis is meant to prevent.
        """
        for body in (
            "De prune-bug is opgelost in v0.29.0; de guard stond op kolom 0.",
            "Bug in de embed-cache gevonden en gefixt, zie scripts/_embeddings.py.",
            "Robert is een ontwikkelaar die van retro-computing houdt.",
        ):
            self.assertFalse(_memory.looks_like_config(body), body)

    def test_a_dated_decision_is_not_config_shaped(self):
        body = ("Op 2026-08-12 besloten om de Atlas-app op Tauri te bouwen "
                "in plaats van Electron, vanwege de bundelgrootte.")
        self.assertFalse(_memory.looks_like_config(body))

    def test_a_setting_stated_with_a_copula_counts(self):
        """Gevonden op de levende vault, niet bedacht.

        "de standaardwaarde voor 'policy.network_allowed' is 'false'" is
        onmiskenbaar een instelling, en werd gemist zolang alleen `=` en `:`
        als toekenning golden.
        """
        self.assertTrue(_memory.looks_like_config(
            "De standaardwaarde voor 'policy.network_allowed' is 'false'."))

    def test_prose_with_a_colon_is_not_a_setting(self):
        """De ALL-CAPS-tak mag geen willekeurig woord worden.

        Onder re.IGNORECASE matchte `[A-Z][A-Z0-9_]{2,}` elk woord van drie
        letters, waardoor `grid-column: 1 / -1` in een CSS-uitleg als
        instelling las. Dat was op de levende vault de enige reden dat een
        layout-memory als state werd geclassificeerd.
        """
        self.assertFalse(_memory.looks_like_config(
            "Elementen in `.settings-group-body` die volledige breedte nodig "
            "hebben, moeten `grid-column: 1 / -1` gebruiken."))
        self.assertFalse(_memory.looks_like_config(
            "De conclusie was helder: 3 van de 4 pogingen mislukten."))

    def test_a_screaming_constant_still_counts(self):
        """... maar de tak zelf moet blijven werken, hoofdlettergevoelig."""
        self.assertTrue(_memory.looks_like_config("RECONCILE_THRESHOLD: 0.75"))
        self.assertTrue(_memory.looks_like_config("TOP_K = 3"))

    def test_a_boolean_hiding_inside_a_dutch_word_is_not_a_setting(self):
        """Vijf valse instellingen op de levende vault, allemaal deze fout.

        'aan' zit in "aangepast", 'uit' in "uitgebreid", 'on' in "ontworpen",
        'off' in "officieel". Zonder woordgrens las "FreeRTOS is officieel
        afgerond" als `RTOS is off` -- een gebeurtenis die daarmee vervangbaar
        werd, precies wat deze as moet voorkomen.
        """
        for body in (
            "De sectie in `vault-CLAUDE.md` is aangepast naar de actieve stijl.",
            "De transitie naar ESP32-S3 async en FreeRTOS is officieel afgerond.",
            "`build.bat` is ontworpen om de volledige toolchain te draaien.",
            "De parser in scripts/_activity.py is uitgebreid met meer talen.",
            "Als een geheugenlek ook optreedt wanneer NTP is uitgeschakeld, "
            "kan het lek daar niet aan liggen.",
        ):
            self.assertFalse(_memory.looks_like_config(body), body)

    def test_a_real_boolean_setting_still_counts(self):
        """De keerzijde: de grens mag de echte waarde niet wegsnijden."""
        self.assertTrue(_memory.looks_like_config("memory_capture staat op true."))
        self.assertTrue(_memory.looks_like_config("`AUTO_LOGIN=true` stopt de server."))
        self.assertTrue(_memory.looks_like_config("sat_onboarded=false is de default."))


class CoerceOrderingTest(unittest.TestCase):
    """Label beats pattern; pattern beats nothing. In that order."""

    def test_an_explicit_state_label_wins(self):
        self.assertEqual(_memory.coerce_volatility("state", "wat dan ook"), "state")

    def test_an_explicit_event_label_is_never_overridden(self):
        """Even for a body that looks exactly like a setting.

        The deterministic check rescues the cases where the model hesitated;
        it is not a second opinion on a label the model did give.
        """
        self.assertEqual(
            _memory.coerce_volatility("event", "num_ctx = 8192"), "event")

    def test_an_absent_label_falls_back_to_the_config_shape(self):
        self.assertEqual(_memory.coerce_volatility("", "num_ctx = 8192"), "state")
        self.assertEqual(_memory.coerce_volatility(None, "we hebben X besloten"), "event")

    def test_a_garbled_label_degrades_to_the_default_and_never_raises(self):
        self.assertEqual(_memory.coerce_volatility("STATE_MAYBE?", "los verhaal"), "event")
        self.assertEqual(_memory.coerce_volatility(42, "los verhaal"), "event")


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-vol-"))
        (self.tmp / "09-memory").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.tmp)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_field_is_persisted(self):
        text = _memory.render("T", "num_ctx = 8192", volatility="state")
        self.assertIn("volatility: state", text)

    def test_a_garbled_label_does_not_crash_the_write(self):
        """render() RAISES on a bad memory_type. Do not copy that here.

        A malformed label from the extractor must cost the label, never the
        capture: the transcript is marked swept either way, so a raise here
        loses the knowledge permanently.
        """
        text = _memory.render("T", "een gebeurtenis", volatility="!!broken!!")
        self.assertIn("volatility: event", text)

    def test_an_unlabelled_config_claim_lands_as_state(self):
        text = _memory.render("T", "De judge draait op qwen3.5:4b.")
        self.assertIn("volatility: state", text)


class ReconcileTest(unittest.TestCase):
    def _judge(self, verdict):
        return lambda new, old: verdict

    def test_an_event_candidate_is_always_added(self):
        items = [{"body": "iets", "vec": [1.0], "status": "current", "volatility": "state"}]
        r = _reconcile.reconcile("nieuw", "2026-08-13", [1.0], items,
                                 judge_fn=self._judge("SUPERSEDE"),
                                 new_volatility="event")
        self.assertEqual(r, {"action": "ADD", "supersedes": []})

    def test_an_event_candidate_is_not_swallowed_by_noop_either(self):
        """NOOP would discard a second, genuinely different event.

        Dedup at 0.92 already absorbs re-captures, so what reaches this band
        is two distinct things that read alike. Both belong in the log.
        """
        items = [{"body": "iets", "vec": [1.0], "status": "current", "volatility": "state"}]
        r = _reconcile.reconcile("nieuw", "2026-08-13", [1.0], items,
                                 judge_fn=self._judge("NOOP"),
                                 new_volatility="event")
        self.assertEqual(r["action"], "ADD")

    def test_an_existing_event_is_never_closed_by_a_state_candidate(self):
        items = [{"body": "gebeurd", "vec": [1.0], "status": "current",
                  "valid_from": "2026-01-01", "volatility": "event"}]
        r = _reconcile.reconcile("nieuwe waarde", "2026-08-13", [1.0], items,
                                 judge_fn=self._judge("SUPERSEDE"),
                                 new_volatility="state")
        self.assertEqual(r["supersedes"], [])

    def test_two_states_still_reconcile_normally(self):
        """The inverse: the guard must not turn the whole seam off."""
        items = [{"body": "oude waarde", "vec": [1.0], "status": "current",
                  "valid_from": "2026-01-01", "volatility": "state"}]
        r = _reconcile.reconcile("nieuwe waarde", "2026-08-13", [1.0], items,
                                 judge_fn=self._judge("SUPERSEDE"),
                                 new_volatility="state")
        self.assertEqual(len(r["supersedes"]), 1)


class MaintenanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-vol-m-"))
        (self.tmp / "09-memory").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.tmp)
        # No index, no embed backend: the vector source is injected.
        self._vecs = {}

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mem(self, name, body, vec, volatility="", created="2026-01-01"):
        p = _memory.write(name, body, status="current", created=created,
                          volatility=volatility)
        self._vecs[str(p)] = vec
        return p

    def _get_cached(self, path, cache, recompute=True):
        return self._vecs.get(str(path))

    def test_current_items_carries_the_axis(self):
        """Without this the guard reads 'event' for everything and skips all.

        That zero would mean "the guard is broken", not "nothing to do" — the
        exact ambiguity TASK-148 removed one level up.
        """
        self._mem("Config", "num_ctx = 8192", [1.0, 0.0])
        self._mem("Gebeurtenis", "Bug opgelost na drie uur zoeken.", [0.0, 1.0])
        items = _maintenance.current_items(get_cached_fn=self._get_cached)
        got = {Path(i["path"]).stem.split("-", 3)[-1]: i["volatility"] for i in items}
        self.assertEqual(got, {"config": "state", "gebeurtenis": "event"})

    def test_supersede_pass_skips_a_pair_of_events(self):
        self._mem("Sessie A", "Vandaag de sweep gedraaid en 3 memories gezien.",
                  [1.0, 0.0], created="2026-01-01")
        self._mem("Sessie B", "Vandaag de sweep gedraaid en 4 memories gezien.",
                  [1.0, 0.0], created="2026-02-01")
        n = _maintenance.supersede_pass(threshold=0.5,
                                        judge_fn=lambda new, old: True,
                                        get_cached_fn=self._get_cached)
        self.assertEqual(n, 0, "een gebeurtenis wordt nooit gesloten")

    def test_supersede_pass_still_closes_a_pair_of_states(self):
        old = self._mem("Judge oud", "De judge draait op gemma3:4b.",
                        [1.0, 0.0], created="2026-01-01")
        self._mem("Judge nieuw", "De judge draait op qwen3.5:4b.",
                  [1.0, 0.0], created="2026-02-01")
        n = _maintenance.supersede_pass(threshold=0.5,
                                        judge_fn=lambda new, old: True,
                                        get_cached_fn=self._get_cached)
        self.assertEqual(n, 1)
        self.assertEqual(_memory.read_status(old), "superseded")


class ExtractTest(unittest.TestCase):
    def test_the_candidate_carries_the_field_through(self):
        saved = _extract._llm.generate
        self.addCleanup(lambda: setattr(_extract._llm, "generate", saved))
        _extract._llm.generate = lambda *a, **kw: (
            '[{"title": "T", "body": "num_ctx = 8192", "type": "feit", '
            '"volatility": "state"}]')
        cands = _extract.extract_candidates("wat tekst")
        self.assertEqual(cands[0]["volatility"], "state")

    def test_a_candidate_without_the_field_still_parses(self):
        saved = _extract._llm.generate
        self.addCleanup(lambda: setattr(_extract._llm, "generate", saved))
        _extract._llm.generate = lambda *a, **kw: (
            '[{"title": "T", "body": "iets", "type": "feit"}]')
        cands = _extract.extract_candidates("wat tekst")
        self.assertEqual(cands[0]["volatility"], "")


if __name__ == "__main__":
    unittest.main()
