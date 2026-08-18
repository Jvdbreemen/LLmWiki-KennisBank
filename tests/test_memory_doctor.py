"""Tests voor scripts/memory-doctor.py - no-cloud + quarantaine-rot checks."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import importlib.util


def _load():
    spec = importlib.util.spec_from_file_location("memory_doctor", str(SCRIPTS_DIR / "memory-doctor.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class MemoryDoctorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-doc-"))
        self.vault = self.tmp / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = {k: os.environ.get(k) for k in
                       ("KENNISBANK_VAULT", "KB_LLM_PROVIDERS", "KB_LLM_ENDPOINT")}
        for k in ("KB_LLM_PROVIDERS", "KB_LLM_ENDPOINT"):
            os.environ.pop(k, None)
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.m = _load()

    def tearDown(self):
        import shutil
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mem(self, name, status, created):
        (self.vault / "09-memory" / name).write_text(
            f"---\ntitle: T\ntype: memory\nstatus: {status}\ncreated: {created}\n---\n\nbody",
            encoding="utf-8")

    def test_nocloud_clean_default(self):
        self.assertEqual(self.m.cloud_warnings(), [])  # default ollama localhost

    def test_nocloud_flags_cloud_provider(self):
        os.environ["KB_LLM_PROVIDERS"] = "ollama, openrouter"
        w = self.m.cloud_warnings()
        self.assertTrue(any("openrouter" in x for x in w))

    def test_nocloud_flags_remote_ollama(self):
        os.environ["KB_LLM_ENDPOINT"] = "http://192.168.1.50:11434"
        w = self.m.cloud_warnings()
        self.assertTrue(any("endpoint" in x.lower() for x in w))

    def test_rot_counts_old_unverified(self):
        old = (date.today() - timedelta(days=3)).isoformat()
        new = date.today().isoformat()
        self._mem("a.md", "unverified", old)   # rot
        self._mem("b.md", "unverified", new)   # vers, geen rot
        self._mem("c.md", "current", old)      # current, geen rot
        self.assertEqual(self.m.rot_count(hours=48), 1)

    def test_rot_breakdown_separates_waiting_from_undecided(self):
        """Two rotting memories are not the same problem (TASK-198).

        One has never been judged -- that points at the sweep or the model.
        The other was judged and came back undecidable, which no automatic
        path can resolve and only a person can. A single count told the owner
        to check Ollama for a state Ollama had nothing to do with.
        """
        old = (date.today() - timedelta(days=3)).isoformat()
        self._mem("waiting.md", "unverified", old)
        self._mem("judged.md", "unverified", old)
        self._mem("fresh.md", "unverified", date.today().isoformat())
        import _groundcheck
        _groundcheck.record_attempt(
            _groundcheck.attempt_key(self.vault / "09-memory" / "judged.md"),
            "partial")

        br = self.m.rot_breakdown(hours=48)
        self.assertEqual(br["total"], 2, "fresh.md is below the cutoff")
        self.assertEqual(br["waiting"], 1)
        self.assertEqual(br["undecided"], 1)

    def test_undecided_means_what_the_pass_actually_does(self):
        """De bucket moet dezelfde vraag beantwoorden als de kandidaatkeuze.

        `undecided` belooft de lezer dat geen automatisch pad de memory nog
        verplaatst. Een verdict van een OUDERE promptversie wordt door
        `candidates()` juist wel weer opgepakt, dus dat is geen undecided --
        anders zegt de melding 'beslis met de hand' over werk dat de volgende
        sweep zelf oppakt.
        """
        old = (date.today() - timedelta(days=3)).isoformat()
        self._mem("stale_version.md", "unverified", old)
        import _groundcheck
        _groundcheck.record_attempt(
            _groundcheck.attempt_key(self.vault / "09-memory" / "stale_version.md"),
            "partial",
            prompt_version=_groundcheck.VERIFY_PROMPT_VERSION - 1)
        br = self.m.rot_breakdown(hours=48)
        self.assertEqual(br["waiting"], 1)
        self.assertEqual(br["undecided"], 0)

    def test_a_broken_transcript_is_not_a_human_decision(self):
        """Een inconclusief resultaat is geen oordeel over de memory.

        `no_transcript` zegt dat de bron stuk is, niet dat de claim
        onbeslisbaar is. Dat in de undecided-bak gooien stuurt de eigenaar
        naar een beslissing die hij niet kan nemen.
        """
        old = (date.today() - timedelta(days=3)).isoformat()
        self._mem("broken.md", "unverified", old)
        import _groundcheck
        _groundcheck.record_attempt(
            _groundcheck.attempt_key(self.vault / "09-memory" / "broken.md"),
            "no_transcript")
        br = self.m.rot_breakdown(hours=48)
        self.assertEqual(br["waiting"], 1)
        self.assertEqual(br["undecided"], 0)

    def test_rot_breakdown_total_still_equals_rot_count(self):
        old = (date.today() - timedelta(days=3)).isoformat()
        self._mem("a.md", "unverified", old)
        self._mem("b.md", "unverified", old)
        import _groundcheck
        _groundcheck.record_attempt(
            _groundcheck.attempt_key(self.vault / "09-memory" / "a.md"),
            "not_found")
        self.assertEqual(self.m.rot_breakdown(hours=48)["total"],
                         self.m.rot_count(hours=48))

    def _status(self, name):
        import re
        txt = (self.vault / "09-memory" / name).read_text(encoding="utf-8")
        mm = re.search(r"^status:\s*(\w+)", txt, re.MULTILINE)
        return mm.group(1) if mm else None

    def test_rejudge_promotes_on_current_verdict(self):
        d = date.today().isoformat()
        self._mem("a.md", "unverified", d)
        self._mem("b.md", "unverified", d)
        r = self.m.rejudge_pass(judge_fn=lambda body: {"verdict": "current"})
        self.assertEqual(r["promoted"], 2)
        self.assertEqual(self._status("a.md"), "current")

    def test_rejudge_keeps_on_unverified_verdict(self):
        d = date.today().isoformat()
        self._mem("a.md", "unverified", d)
        r = self.m.rejudge_pass(judge_fn=lambda body: {"verdict": "unverified"})
        self.assertEqual(r, {"promoted": 0, "kept": 1, "failed": 0})
        self.assertEqual(self._status("a.md"), "unverified")

    def test_rejudge_dry_run_writes_nothing(self):
        d = date.today().isoformat()
        self._mem("a.md", "unverified", d)
        r = self.m.rejudge_pass(judge_fn=lambda body: {"verdict": "current"}, dry_run=True)
        self.assertEqual(r["promoted"], 1)
        self.assertEqual(self._status("a.md"), "unverified")  # niet geschreven

    def test_rejudge_hours_filter_only_old(self):
        old = (date.today() - timedelta(days=3)).isoformat()
        new = date.today().isoformat()
        self._mem("old.md", "unverified", old)
        self._mem("new.md", "unverified", new)
        r = self.m.rejudge_pass(judge_fn=lambda body: {"verdict": "current"}, hours=48)
        self.assertEqual(r["promoted"], 1)          # alleen de oude
        self.assertEqual(self._status("new.md"), "unverified")

    def test_rejudge_failsafe_on_judge_exception(self):
        d = date.today().isoformat()
        self._mem("a.md", "unverified", d)
        def boom(body):
            raise RuntimeError("model down")
        r = self.m.rejudge_pass(judge_fn=boom)
        self.assertEqual(r, {"promoted": 0, "kept": 0, "failed": 1})
        self.assertEqual(self._status("a.md"), "unverified")

    def test_nocloud_localhost_evil_com_is_flagged(self):
        """Bypass via http://localhost.evil.com — naive substring match misses this; parse-based must catch it."""
        os.environ["KB_LLM_ENDPOINT"] = "http://localhost.evil.com:11434"
        w = self.m.cloud_warnings()
        self.assertTrue(any("endpoint" in x.lower() for x in w),
                        f"Expected endpoint warning for localhost.evil.com, got: {w}")

    def test_nocloud_ollama_not_first_in_chain_still_checked(self):
        """KB_LLM_PROVIDERS='foo, ollama' + remote endpoint must still warn (ollama not at chain[0])."""
        os.environ["KB_LLM_PROVIDERS"] = "foo, ollama"
        os.environ["KB_LLM_ENDPOINT"] = "http://192.168.1.50:11434"
        w = self.m.cloud_warnings()
        self.assertTrue(any("endpoint" in x.lower() for x in w),
                        f"Expected endpoint warning for ollama-not-first, got: {w}")


if __name__ == "__main__":
    unittest.main()


class RotJsonCliTest(MemoryDoctorTest):
    """The waiting/undecided split has to reach a shell, not just Python.

    rot_breakdown() existed since v0.34.0 but no CLI exposed it, so doctor.sh
    read the total and invented a cause for it (TASK-200).
    """

    def _rot_cli(self, *args):
        import subprocess
        out = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "memory-doctor.py"), "rot", *args],
            capture_output=True, text=True,
            env={**os.environ, "KENNISBANK_VAULT": str(self.vault)},
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout.strip()

    def test_rot_json_reports_both_buckets(self):
        import json
        old = (date.today() - timedelta(days=3)).isoformat()
        self._mem("waiting.md", "unverified", old)
        self._mem("judged.md", "unverified", old)
        import _groundcheck
        _groundcheck.record_attempt(
            _groundcheck.attempt_key(self.vault / "09-memory" / "judged.md"), "partial")

        data = json.loads(self._rot_cli("--json"))
        self.assertEqual(data, {"total": 2, "waiting": 1, "undecided": 1})

    def test_bare_rot_still_prints_only_the_total(self):
        """The old contract stays: a caller asking 'is there rot?' need not parse JSON."""
        old = (date.today() - timedelta(days=3)).isoformat()
        self._mem("a.md", "unverified", old)
        self.assertEqual(self._rot_cli(), "1")

    def test_rot_json_honours_hours(self):
        import json
        self._mem("recent.md", "unverified", date.today().isoformat())
        self.assertEqual(json.loads(self._rot_cli("--json", "--hours", "48"))["total"], 0)


class DoctorQuarantineOutputTest(MemoryDoctorTest):
    """doctor.sh must not blame the sweep for memories the sweep already judged.

    This is the vault shape that exposed the bug: heartbeat clean, every
    memory judged, verdict `partial` -- and the old check still printed
    "(sweep/judge hangt?)" (TASK-200).
    """

    def _doctor_quarantine_lines(self):
        import shutil
        import subprocess
        # doctor.sh reads its helpers from $VAULT/.claude/scripts, so the test
        # vault needs the same deploy shape production has -- running it
        # against the repo tree would test a layout no user ever has.
        deployed = self.vault / ".claude" / "scripts"
        if not deployed.exists():
            shutil.copytree(SCRIPTS_DIR, deployed)
        # Reuse the cross-platform bash finder rather than growing a second
        # copy of the Git-Bash-vs-System32 logic (ADR-0002 portability).
        from tests.test_setup_deploy import _find_bash
        bash = _find_bash()
        out = subprocess.run(
            [bash, str(deployed / "doctor.sh")],
            capture_output=True, text=True,
            env={**os.environ, "KENNISBANK_VAULT": str(self.vault)},
        )
        return [ln for ln in (out.stdout + out.stderr).splitlines()
                if "quarantaine" in ln]

    def test_only_undecided_does_not_blame_the_sweep(self):
        old = (date.today() - timedelta(days=3)).isoformat()
        self._mem("judged.md", "unverified", old)
        import _groundcheck
        _groundcheck.record_attempt(
            _groundcheck.attempt_key(self.vault / "09-memory" / "judged.md"), "partial")

        lines = self._doctor_quarantine_lines()
        self.assertTrue(lines, "expected a quarantine line")
        joined = " ".join(lines)
        self.assertNotIn("sweep/judge hangt", joined)
        self.assertNotIn("sweep-launch", joined,
                         "no memory is waiting, so the sweep must not be named")
        self.assertIn("onbeslisbaar", joined)
        # The action named must be one that can actually move an unverified
        # memory. /kennisbank:review only offers demote/reopen and reads logs
        # this memory is in neither of.
        self.assertIn("memory-doctor.py decide", joined)
        self.assertNotIn("/kennisbank:review", joined)

    def test_only_waiting_still_points_at_the_sweep(self):
        old = (date.today() - timedelta(days=3)).isoformat()
        self._mem("waiting.md", "unverified", old)
        joined = " ".join(self._doctor_quarantine_lines())
        self.assertIn("sweep-launch", joined)
        self.assertNotIn("onbeslisbaar", joined)

    def test_clean_vault_passes(self):
        joined = " ".join(self._doctor_quarantine_lines())
        self.assertIn("geen rot", joined)
