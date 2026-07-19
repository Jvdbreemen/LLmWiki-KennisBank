import importlib.util
import json
import sys
import threading
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "kb-session-end.py"


def _load():
    spec = importlib.util.spec_from_file_location("kb_session_end", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_claude_capture_finishes_before_usage_scan(tmp_path):
    module = _load()
    vault = tmp_path / "Kluis"
    (vault / ".claude" / "scripts").mkdir(parents=True)
    calls = []
    archived = threading.Event()

    def runner(job, _scripts, payload):
        assert payload == b'{"session_id":"one"}'
        calls.append(job.script)
        if job.script == "archive-transcript.py":
            time.sleep(0.02)
            archived.set()
        else:
            assert archived.is_set()
        return module.Result(job.script)

    assert module.coordinate(
        "claude", vault, b'{"session_id":"one"}', runner=runner
    ) == []
    assert calls == ["archive-transcript.py", "kb-usage-scan.py"]


def test_copilot_capture_precedes_parallel_import_and_usage(tmp_path):
    module = _load()
    vault = tmp_path / "Kluis"
    (vault / ".claude" / "scripts").mkdir(parents=True)
    capture_done = threading.Event()
    lock = threading.Lock()
    active = 0
    peak = 0

    def runner(job, _scripts, _payload):
        nonlocal active, peak
        if job.script == "kb-copilot-capture.py":
            capture_done.set()
        else:
            assert capture_done.is_set()
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.04)
            with lock:
                active -= 1
        return module.Result(job.script)

    assert module.coordinate("copilot", vault, b"{}", runner=runner) == []
    assert peak == 2


def test_exit_is_silent_and_writes_diagnostic_state(tmp_path, capsys, monkeypatch):
    module = _load()
    vault = tmp_path / "Kluis"
    (vault / ".claude" / "scripts").mkdir(parents=True)

    def runner(job, _scripts, _payload):
        if job.script == "kb-usage-scan.py":
            return module.Result(job.script, returncode=3, stderr="broken")
        return module.Result(job.script)

    issues = module.coordinate("codex", vault, b"{}", runner=runner)
    state = json.loads(
        (vault / ".claude" / module.STATE_NAME).read_text(encoding="utf-8")
    )
    assert issues == ["kb-usage-scan.py: exited with status 3: broken"]
    assert state["ok"] is False
    assert capsys.readouterr().out == ""

    warning = module.Result("archive-transcript.py", stderr="source missing")
    assert module._issue(warning) == "archive-transcript.py: source missing"

    monkeypatch.setattr(module, "coordinate", lambda *_args, **_kwargs: 1 / 0)
    assert module.main(["--client", "codex"]) == 0
    assert capsys.readouterr().out == ""
