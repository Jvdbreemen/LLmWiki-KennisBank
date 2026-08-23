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
    # Een barrier in plaats van een sleep. De oude vorm telde hoeveel jobs
    # binnen een venster van 40 ms toevallig tegelijk actief waren, en dat is
    # geen eigenschap van de code maar van de scheduler: op een belaste machine
    # faalde hij 3 van de 5 runs. De barrier maakt de assertie hard -- komen
    # niet alle jobs samen, dan blokkeert hij en valt de test op de timeout in
    # plaats van op een toevallige piek.
    barrier = threading.Barrier(len(module.INDEX_JOBS), timeout=30)
    lock = threading.Lock()
    indexed = set()
    samen = []

    def runner(job, _scripts):
        if job in module.INDEX_JOBS:
            if job.script == "build-karpathy-index.py":
                assert job.args == ("--force",)
            try:
                barrier.wait()
                samen.append(job.script)
            except threading.BrokenBarrierError:
                pass  # laat de assertie hieronder het verschil melden
            with lock:
                indexed.add(job.script)
        else:
            assert indexed == {item.script for item in module.INDEX_JOBS}
        return module.Result(job.script)

    assert module.coordinate(vault, str(log), runner=runner) == ""
    assert len(samen) == len(module.INDEX_JOBS), (
        "niet alle indexjobs bereikten de barrier, dus ze liepen niet parallel")


def test_reports_unwrap_notices_and_ignore_routine_progress():
    module = _load()
    progress = module.Result(
        "build-activity-index.py",
        stdout="activity-index: 20 events, 8 sources, 0 changed, 8 unchanged",
        stderr="activity-index: 8/8 sources, 0 events indexed, 8 unchanged",
    )
    assert module.relevant_report(progress) == ""

    notice = module.Result(
        "memory-notify.py",
        stdout='{"hookSpecificOutput":{"additionalContext":"13 memories need review"}}',
    )
    assert module.relevant_report(notice) == (
        "memory-notify.py: 13 memories need review"
    )


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


def test_job_timeout_is_configurable(monkeypatch):
    """180s is fixed while build-kb-index.py scales with the corpus.

    Its corrective pass hashes every indexed document, so the run time grows
    with the vault instead of with what changed. Measured on a vault of 4320
    indexed documents: 165 re-indexed took over 8.5 minutes, so the job was
    killed every single session. The work survives (_kbindex.upsert commits per
    record) but the signal does not: `timed out` becomes a permanent line and a
    real index failure is no longer distinguishable from the routine one.
    """
    module = _load()
    assert module.Job("x").timeout == 180, "default must stay 180"

    monkeypatch.setenv("KB_SESSION_LOG_TIMEOUT", "900")
    reloaded = _load()
    assert reloaded.Job("x").timeout == 900
    assert reloaded.Job("x", timeout=30).timeout == 30, "explicit wins over env"

    monkeypatch.setenv("KB_SESSION_LOG_TIMEOUT", "onzin")
    assert _load().Job("x").timeout == 180, "malformed value falls back"


def test_timeout_message_names_the_knob(tmp_path):
    """Een teller zonder knop laat de lezer met een probleem zonder oplossing.

    Op een grote vault is dit de regel die elke sessie terugkomt, dus hij moet
    zeggen wat de lezer eraan kan doen. Dwingt een echte timeout af in plaats
    van te asserten onder een if: een test die ook zonder de fix slaagt bewaakt
    niets.
    """
    module = _load()
    (tmp_path / "sleeper.py").write_text(
        "import time\ntime.sleep(30)\n", encoding="utf-8")
    result = module.run_child(module.Job("sleeper.py", timeout=1), tmp_path)
    assert "timed out" in result.error, result
    assert "KB_SESSION_LOG_TIMEOUT" in result.error, result


def test_timeout_never_drops_below_one(monkeypatch):
    """env_int is fail-open op onzin, maar niet op een geldige 0 of negatief.

    Beide maken dat subprocess.run elke job direct afkapt, waarna elke regel in
    het rapport "timed out" leest -- een zelf toegebrachte permanente storing.
    """
    for waarde in ("0", "-5"):
        monkeypatch.setenv("KB_SESSION_LOG_TIMEOUT", waarde)
        assert _load().Job("x").timeout >= 1, waarde
