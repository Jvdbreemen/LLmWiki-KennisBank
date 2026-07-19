import importlib.util
import json
import sys
import threading
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "kb-session-start.py"


def _load():
    spec = importlib.util.spec_from_file_location("kb_session_start", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_coordinator_runs_independent_work_concurrently_and_notifications_after(tmp_path):
    module = _load()
    vault = tmp_path / "Kluis"
    (vault / ".claude" / "scripts").mkdir(parents=True)
    lock = threading.Lock()
    active = 0
    peak = 0
    maintenance_done = set()

    def runner(job, _scripts, _payload):
        nonlocal active, peak
        if job in module.MAINTENANCE:
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.04)
            with lock:
                active -= 1
                maintenance_done.add(job.script)
        if job in module.NOTIFICATIONS:
            assert maintenance_done == {item.script for item in module.MAINTENANCE}
        return module.Result(job.script)

    assert module.coordinate("codex", vault, b"{}", runner=runner) == ""
    assert peak == len(module.MAINTENANCE)


def test_coordinator_aggregates_only_actionable_results(tmp_path):
    module = _load()
    vault = tmp_path / "Kluis"
    (vault / ".claude" / "scripts").mkdir(parents=True)

    def runner(job, _scripts, _payload):
        outputs = {
            "build-embed-index.py": (
                "embed-index: 110 wiki files, 0 (re)embedded, 0 failed"
            ),
            "build-kb-index.py": (
                "kb-index: 10 files, 2 (re)indexed, 8 ongewijzigd, "
                "0 verwijderd, 0 failed"
            ),
            "build-activity-index.py": (
                "activity-index: 20 events, 8 sources, 0 changed, 8 unchanged"
            ),
            "memory-notify.py": json.dumps({
                "additionalContext": "13 unverified memories need attention."
            }),
        }
        return module.Result(job.script, stdout=outputs.get(job.script, ""))

    report = module.coordinate("codex", vault, b"", runner=runner)
    assert "2 (re)indexed" in report
    assert "13 unverified memories" in report
    assert "110 wiki files" not in report
    assert "20 events" not in report


def test_freshness_skips_maintenance_but_keeps_copilot_capture(tmp_path):
    module = _load()
    vault = tmp_path / "Kluis"
    runtime = vault / ".claude"
    (runtime / "scripts").mkdir(parents=True)
    (runtime / module.STATE_NAME).write_text(
        json.dumps({"completed_at": 1000.0}),
        encoding="utf-8",
    )
    called = []

    def runner(job, _scripts, _payload):
        called.append(job.script)
        return module.Result(job.script)

    assert module.coordinate(
        "copilot", vault, b"{}", runner=runner, now=1100.0
    ) == ""
    assert called == ["kb-copilot-capture.py"]


def test_emit_uses_one_native_context_payload_per_client(capsys):
    module = _load()
    module._emit("claude", "action")
    claude = json.loads(capsys.readouterr().out)
    assert claude["suppressOutput"] is True
    assert "action" in claude["hookSpecificOutput"]["additionalContext"]

    module._emit("copilot", "action")
    copilot = json.loads(capsys.readouterr().out)
    assert set(copilot) == {"additionalContext"}

    module._emit("codex", "action")
    codex = json.loads(capsys.readouterr().out)
    assert codex["suppressOutput"] is True
    assert "action" in codex["additionalContext"]


def test_timeout_and_nonzero_exit_are_actionable_but_fail_open(tmp_path, monkeypatch):
    module = _load()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    slow = scripts / "slow.py"
    slow.write_text("import time\ntime.sleep(1)\n", encoding="utf-8")

    timed_out = module.run_child(module.Job("slow.py", timeout=0.01), scripts, b"")
    assert "timed out" in module.relevant_report(timed_out)

    failed = module.Result(
        "build-embed-index.py",
        stdout="embed-index: 1 wiki files, 0 (re)embedded, 0 failed",
        returncode=7,
    )
    assert "status 7" in module.relevant_report(failed)

    monkeypatch.setattr(module, "coordinate", lambda *_args, **_kwargs: 1 / 0)
    assert module.main(["--client", "codex"]) == 0
