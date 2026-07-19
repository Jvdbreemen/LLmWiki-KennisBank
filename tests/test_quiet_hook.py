import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
QUIET_HOOK = REPO_ROOT / "scripts" / "quiet-hook.py"


def test_quiet_hook_suppresses_no_change_output_and_fails_open(tmp_path):
    child = tmp_path / "build-embed-index.py"
    child.write_text(
        "print('embed-index: 110 wiki files, 0 (re)embedded, "
        "0 failed, backend=local')\n"
        "raise SystemExit(7)\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(QUIET_HOOK), str(child)],
        input="hook payload",
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_quiet_hook_returns_changed_report_as_client_context(tmp_path):
    child = tmp_path / "build-activity-index.py"
    child.write_text(
        "print('activity-index: 20 events, 8 sources, 3 changed, "
        "5 unchanged, 0.2s')\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(QUIET_HOOK),
            "--client",
            "claude",
            "--event",
            "SessionStart",
            str(child),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert result.stderr == ""
    assert payload["suppressOutput"] is True
    report = payload["hookSpecificOutput"]["additionalContext"]
    assert "3 changed" in report
    assert "Briefly report this to the user" in report


def test_quiet_hook_uses_copilot_session_context_shape(tmp_path):
    child = tmp_path / "build-kb-index.py"
    child.write_text(
        "print('kb-index: 10 files, 2 (re)indexed, 8 ongewijzigd, "
        "0 verwijderd, 0 failed, backend=local')\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(QUIET_HOOK),
            "--client",
            "copilot",
            "--event",
            "sessionStart",
            str(child),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert set(payload) == {"additionalContext"}
    assert "2 (re)indexed" in payload["additionalContext"]
