"""TASK-27.10 DoD #2: the Atlas doctor reports readiness and exits sensibly."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DOCTOR = REPO / "atlas" / "doctor.py"


def test_doctor_runs_and_summarises(tmp_path):
    # Point at an empty vault: stores are absent (warnings, not hard failures),
    # so the doctor still exits 0 and prints a summary.
    r = subprocess.run(
        [sys.executable, str(DOCTOR)],
        capture_output=True, text=True,
        env={"KENNISBANK_VAULT": str(tmp_path), "PATH": __import__("os").environ.get("PATH", "")},
    )
    assert "samenvatting" in r.stdout
    # cargo is optional -> its absence must not be a hard failure
    assert "cargo (Tauri bundle)" in r.stdout


def test_doctor_reports_missing_vault_store_as_warning(tmp_path):
    r = subprocess.run(
        [sys.executable, str(DOCTOR)],
        capture_output=True, text=True,
        env={"KENNISBANK_VAULT": str(tmp_path), "PATH": __import__("os").environ.get("PATH", "")},
    )
    assert "vault: kb-index" in r.stdout
