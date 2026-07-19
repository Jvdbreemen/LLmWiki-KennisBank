import importlib.util
import sys
import threading
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "kb-session-log.py"


def _load():
    spec = importlib.util.spec_from_file_location("kb_session_log", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_post_save_jobs_are_parallel_and_notices_follow(tmp_path):
    module = _load()
    vault = tmp_path / "Kluis"
    scripts = vault / ".claude" / "scripts"
    sessions = vault / "01-raw" / "sessies"
    scripts.mkdir(parents=True)
    sessions.mkdir(parents=True)
    log = sessions / "raw-sessie-2026-07-19-test.md"
    log.write_text("# session", encoding="utf-8")
    lock = threading.Lock()
    active = 0
    peak = 0
    indexed = set()

    def runner(job, _scripts):
        nonlocal active, peak
        if job in module.INDEX_JOBS:
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.04)
            with lock:
                active -= 1
                indexed.add(job.script)
        else:
            assert indexed == {item.script for item in module.INDEX_JOBS}
        return module.Result(job.script)

    assert module.coordinate(vault, str(log), runner=runner) == ""
    assert peak == len(module.INDEX_JOBS)


def test_rejects_paths_outside_session_log_directory(tmp_path):
    module = _load()
    vault = tmp_path / "Kluis"
    outside = tmp_path / "outside.md"
    outside.write_text("x", encoding="utf-8")
    try:
        module.coordinate(vault, str(outside))
    except ValueError as exc:
        assert "01-raw/sessies" in str(exc)
    else:
        raise AssertionError("outside session log path was accepted")
