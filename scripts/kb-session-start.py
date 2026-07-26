#!/usr/bin/env python3
"""Coordinate KennisBank SessionStart work behind one client hook.

Independent maintenance jobs run concurrently. Work with a data dependency runs
in deterministic phases, and all actionable results are folded into one
client-native context payload. The coordinator is stdlib-only and always fails
open.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _hooks_manifest  # noqa: E402
from _vaultpath import vault_root  # noqa: E402


FRESHNESS_SECONDS = 300
# Afgeleid van het gedeclareerde plafond in plaats van een los getal: een
# afgebroken cyclus herstelt zo binnen één plafond in plaats van binnen een
# waarde die niemand meer met het budget verbindt.
LOCK_STALE_SECONDS = _hooks_manifest.timeout("kb-session-start.py")
STATE_NAME = "kb-session-start-state.json"
LOCK_NAME = ".kb-session-start.lock"


@dataclass(frozen=True)
class Job:
    script: str
    args: tuple[str, ...] = ()
    timeout: int = 180


@dataclass
class Result:
    script: str
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    error: str = ""


# Indexonderhoud draait NIET meer blokkerend. index-launch.py neemt een lock,
# spawnt een losgekoppelde worker die de bouwers plus de geheugensweep
# sequentieel afwerkt, en keert direct terug. Daarmee valt het blokkerende deel
# van SessionStart terug van ~210s (Claude/Codex) en ~300s (Copilot) naar de
# paar seconden die de launcher zelf kost. Zie TASK-63.
MAINTENANCE = (
    Job("index-launch.py", timeout=15),
)
NOTIFICATIONS = (
    Job("memory-notify.py", timeout=30),
    Job("distill-notify.py", timeout=30),
    # Waarschuwt als de git-repo in de sessie-cwd achter zijn upstream loopt.
    # cwd-aware + fail-open: stil buiten een repo of als alles up-to-date is.
    # Erft de 300s freshness-gate van de coordinator, dus geen fetch-spam.
    Job("git-upstream-check.py", timeout=15),
)


def _vault() -> Path:
    return vault_root()


def _prewarm_embed_model(vault: Path) -> None:
    """Fire a detached warm of the embedding model at session start so the first
    prompt's retrieval hook (kb-retrieve) is hot.

    The incremental index build does NOT load the model when nothing changed, so
    without this the first prompt of an otherwise-'fresh' session pays the full
    cold-load (tens of seconds for an 8GB model) and the retrieval hook times
    out. Non-blocking, fail-open, sentinel-guarded (see _embeddings.warm_async).
    Fires from main(), not coordinate(), so it is independent of the freshness
    gate and never runs inside the unit tests that drive coordinate() directly."""
    try:
        scripts = vault / ".claude" / "scripts"
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        import _embeddings as emb
        emb.warm_async()
    except Exception:
        pass


def _changed_count(text: str, pattern: str) -> int:
    match = re.search(pattern, text, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _context_text(text: str) -> str:
    """Extract useful text from a child hook's structured output."""
    stripped = text.strip()
    if not stripped:
        return ""
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped
    if not isinstance(payload, dict):
        return stripped
    direct = payload.get("additionalContext")
    if isinstance(direct, str):
        return direct.strip()
    nested = payload.get("hookSpecificOutput")
    if isinstance(nested, dict) and isinstance(nested.get("additionalContext"), str):
        return nested["additionalContext"].strip()
    return stripped


def relevant_report(result: Result) -> str:
    """Keep changes, warnings and failures; discard routine no-change output."""
    out = _context_text(result.stdout)
    err = result.stderr.strip()
    if result.error:
        return f"{result.script}: {result.error}"

    actionable_err = bool(re.search(
        r"\b(?:error|failed|failure|warning|warn|fout|mislukt|traceback|"
        r"timed out)\b",
        err,
        re.IGNORECASE,
    ))
    relevant = actionable_err or result.returncode != 0
    if result.script == "build-embed-index.py":
        relevant = relevant or _changed_count(out, r"(\d+)\s+\(re\)embedded") > 0
        relevant = relevant or _changed_count(out, r"(\d+)\s+failed") > 0
    elif result.script == "build-kb-index.py":
        relevant = relevant or _changed_count(out, r"(\d+)\s+\(re\)indexed") > 0
        relevant = relevant or _changed_count(out, r"(\d+)\s+verwijderd") > 0
        relevant = relevant or _changed_count(out, r"(\d+)\s+removed") > 0
        relevant = relevant or _changed_count(out, r"(\d+)\s+failed") > 0
    elif result.script == "build-activity-index.py":
        relevant = relevant or _changed_count(out, r"(\d+)\s+changed") > 0
        relevant = relevant or _changed_count(out, r"(\d+)\s+failed") > 0
    elif result.script in {"import-copilot.py", "kb-copilot-capture.py",
                           "sweep-launch.py", "index-launch.py"}:
        # These are side-effect jobs; successful routine output is not context.
        relevant = relevant or result.returncode != 0
    else:
        relevant = relevant or bool(out) or result.returncode != 0

    if not relevant:
        return ""
    parts = [part for part in (out, err if actionable_err else "") if part]
    if result.returncode:
        parts.append(f"exited with status {result.returncode}")
    details = "\n".join(parts)
    return f"{result.script}: {details}".strip()


def run_child(job: Job, scripts: Path, payload: bytes) -> Result:
    try:
        proc = subprocess.run(
            [sys.executable, str(scripts / job.script), *job.args],
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=job.timeout,
            check=False,
        )
        return Result(
            script=job.script,
            stdout=proc.stdout.decode("utf-8", errors="replace"),
            stderr=proc.stderr.decode("utf-8", errors="replace"),
            returncode=proc.returncode,
        )
    except subprocess.TimeoutExpired:
        return Result(job.script, error=f"timed out after {job.timeout}s")
    except (OSError, subprocess.SubprocessError) as exc:
        return Result(job.script, error=f"could not run: {exc}")


def run_parallel(
    jobs: tuple[Job, ...],
    scripts: Path,
    payload: bytes,
    runner: Callable[[Job, Path, bytes], Result] = run_child,
) -> list[Result]:
    if not jobs:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = [pool.submit(runner, job, scripts, payload) for job in jobs]
        # Preserve declared order even though execution is concurrent.
        return [future.result() for future in futures]


def _read_state(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def is_fresh(state_path: Path, now: float | None = None) -> bool:
    state = _read_state(state_path)
    completed = state.get("completed_at")
    if not isinstance(completed, (int, float)):
        return False
    return (time.time() if now is None else now) - float(completed) < FRESHNESS_SECONDS


def acquire_lock(path: Path, now: float | None = None) -> bool:
    current = time.time() if now is None else now
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            age = current - path.stat().st_mtime
            # age < 0 = mtime in de toekomst (klokverzetting, of een bestand van
            # een machine met scheve klok). Zonder die clausule verloopt zo'n
            # lock nooit en ligt het onderhoud permanent stil.
            if 0 <= age <= LOCK_STALE_SECONDS:
                return False
            path.unlink()
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except (FileExistsError, FileNotFoundError, OSError):
            return False
    except OSError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"pid": os.getpid(), "started_at": current}, handle)
    return True


def _write_state(path: Path, client: str) -> None:
    temp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    try:
        temp.write_text(
            json.dumps(
                {"completed_at": time.time(), "client": client},
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(temp, path)
    except OSError:
        try:
            temp.unlink()
        except OSError:
            pass


#: Bovengrens voor de statusregel. Puur een leesactie op al bestaande state;
#: zodra dit meer kost dan een handvol milliseconden hoort het niet meer op de
#: hot path en moet het naar de achtergrondworker.
STATUS_BUDGET_MS = 250


def worker_is_alive(vault: Path) -> bool:
    """Draait het achtergrondonderhoud nog echt?

    Het BESTAAN van de lock is geen antwoord. Een verweesde lock blijft gewoon
    liggen -- gemeten: een lock met PID 31772 terwijl de levende worker 22552
    was -- en dan zou de statusregel voor altijd "onderhoud draait al" beweren
    terwijl er niets draait. Precies het stille falen dat deze regel wegneemt.

    index-launch heeft die vraag al beantwoord: leeftijd ten opzichte van
    STALE_SEC, afgeleid uit de job-timeouts en bewaakt door een eigen test. Dat
    antwoord lenen we hier. Een tweede, PID-gebaseerd antwoord zou onvermijdelijk
    op een ander moment "verlopen" dan de partij die de lock echt beheert.
    """
    try:
        import importlib.util
        pad = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index-launch.py")
        spec = importlib.util.spec_from_file_location("index_launch", pad)
        il = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(il)
        lock = vault / ".claude" / il.LOCK_NAME
        return lock.exists() and not il.is_stale(lock)
    except Exception:
        return False


def status_line(vault: Path, *, worker_running: bool) -> str:
    """Eenregelig statusbericht, afgelezen uit bestaande state.

    Bewust een AFLEZING en geen berekening: alles hier komt uit bestanden die
    de vorige achtergrondrun al heeft achtergelaten, of uit een enkele
    SQLite-telling. Geen embed-calls, geen vault-scan, geen LLM. Een sessiestart
    hoort te melden waar je aan toe bent, niet het te gaan uitzoeken.

    Fail-open per onderdeel: elk stuk dat niet leesbaar is wordt overgeslagen,
    zodat een ontbrekende index nooit de melding (of de sessie) breekt.
    """
    delen = []
    delen.append("onderhoud draait al" if worker_running else "onderhoud gestart op de achtergrond")

    # Embedding-index: een telling. Read-only, geen schrijfrechten nodig.
    try:
        import sqlite3
        db = vault / ".claude" / "kb-index.db"
        if db.exists():
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=0.5)
            try:
                docs = conn.execute("SELECT count(*) FROM docs").fetchone()[0]
                deel = f"index {docs} documenten"
                # Draait er onderhoud, dan is deze telling een momentopname van
                # een tabel die op dit moment gevuld wordt. Gemeten: 258 -> 262
                # -> 266 in drie runs, terwijl de vault er 1268 heeft. Het getal
                # zonder voorbehoud tonen is een verkeerd getal met stellige toon.
                if worker_running:
                    deel += " (bijwerken)"
                delen.append(deel)
            finally:
                conn.close()
    except Exception:
        pass

    # Graaf: een EIGEN bestand en dus een eigen aflezing. Bewust niet genest in
    # de tak hierboven: sinds TASK-75 kan kb-index.db weg zijn of half herbouwd
    # worden terwijl de graaf ongeschonden is. De graafstatus aan het bestaan van
    # de embedding-index koppelen zou hem juist stil maken op het moment dat je
    # hem het hardst nodig hebt.
    try:
        import sqlite3
        gpath = vault / "graphify-out" / "graph.json"
        gdb = vault / ".claude" / "kb-graph.db"
        if gpath.exists():
            if not gdb.exists():
                delen.append("graaf niet geladen")
            else:
                conn = sqlite3.connect(f"file:{gdb}?mode=ro", uri=True, timeout=0.5)
                try:
                    row = conn.execute(
                        "SELECT value FROM meta WHERE key='graph_fingerprint'").fetchone()
                    if row:
                        st = gpath.stat()
                        actueel = row[0] == f"{int(st.st_mtime)}:{st.st_size}"
                        delen.append("graaf " + ("actueel" if actueel else "verouderd"))
                    else:
                        # Wel een graaf op schijf, maar de graafindex kent hem
                        # niet. Zwijgen hierover is precies hoe de graaftabellen
                        # ongemerkt verdwenen (TASK-75).
                        delen.append("graaf niet geladen")
                except sqlite3.Error:
                    delen.append("graaf niet geladen")
                finally:
                    conn.close()
    except Exception:
        pass

    # Staat er werk klaar voor de graaf? Een niet-lege vlag betekent ja.
    try:
        flag = vault / "graphify-out" / ".needs-rebuild"
        if flag.exists() and flag.stat().st_size > 0:
            delen.append("graaf-rebuild staat klaar")
    except OSError:
        pass

    # ASCII-only scheiding, bewust. _emit escapet inmiddels naar ASCII, dus dit
    # is niet meer strikt nodig -- maar de statusregel is het laatste wat stil
    # mag falen, en twee onafhankelijke waarborgen kosten hier niets. Een bullet
    # (U+00B7) leverde eerder een LEGE sessiestart met exitcode 0 op.
    # test_statusregel_is_cp1252_veilig bewaakt dit.
    return "KennisBank: " + " | ".join(delen)


def _emit(client: str, report: str) -> None:
    if not report:
        return
    context = (
        "KennisBank session report (only changes or actions):\n"
        f"{report}\n"
        "Briefly tell the user what changed or what action is useful. Do not "
        "repeat routine hook or implementation details."
    )
    if client == "claude":
        payload = {
            "suppressOutput": True,
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": context,
            },
        }
    elif client == "copilot":
        payload = {"additionalContext": context}
    else:
        payload = {"suppressOutput": True, "additionalContext": context}
    # ensure_ascii=True (de default) is hier bewust: deze hook geeft de uitvoer
    # van ALLE kindscripts door. Een enkel niet-cp1252 teken -- een accent in een
    # bestandsnaam, een typografisch aanhalingsteken -- gooit op Windows een
    # UnicodeEncodeError die main() opslokt, en dan verdwijnt het HELE
    # sessierapport zonder spoor. \uXXXX-escapes decoderen aan de leeskant naar
    # exact hetzelfde teken, dus dit kost niets.
    sys.stdout.write(json.dumps(payload))


def coordinate(
    client: str,
    vault: Path,
    payload: bytes,
    *,
    runner: Callable[[Job, Path, bytes], Result] = run_child,
    now: float | None = None,
) -> str:
    """Run one deterministic SessionStart cycle and return an aggregate report."""
    scripts = vault / ".claude" / "scripts"
    runtime = vault / ".claude"
    state_path = runtime / STATE_NAME
    lock_path = runtime / LOCK_NAME

    # Het source-veld ("startup"|"resume"|"clear"|"compact"|"fork") stuurt de
    # checkpoint-melding: na een compaction is die urgent en specifiek.
    source = ""
    try:
        parsed = json.loads(payload.decode("utf-8", errors="replace")) if payload.strip() else {}
        if isinstance(parsed, dict):
            source = str(parsed.get("source") or "")
    except ValueError:
        pass

    always: list[Result] = []
    # Checkpoint-melding draait VÓÓR de freshness-gate: een SessionStart met
    # source=compact valt vrijwel altijd binnen 300s na de vorige start, en dan
    # zou de melding in NOTIFICATIONS precies op het moment suprême wegvallen
    # (TASK-79). Puur een state-file-lezing, dus goedkoop genoeg voor elk event.
    always.extend(run_parallel(
        (Job("kb-checkpoint.py", ("--notify", "--source", source), 15),),
        scripts,
        payload,
        runner,
    ))
    if client == "copilot":
        always.extend(run_parallel(
            (Job("kb-copilot-capture.py", ("--event", "sessionStart"), 30),),
            scripts,
            payload,
            runner,
        ))

    if is_fresh(state_path, now=now):
        return "\n".join(filter(None, (relevant_report(r) for r in always)))
    if not acquire_lock(lock_path, now=now):
        return "\n".join(filter(None, (relevant_report(r) for r in always)))

    results = list(always)
    try:
        if client == "copilot":
            results.extend(run_parallel(
                (Job("import-copilot.py", timeout=60),),
                scripts,
                payload,
                runner,
            ))
        results.extend(run_parallel(MAINTENANCE, scripts, payload, runner))
        # Notifications observe the maintenance phase's completed state.
        results.extend(run_parallel(NOTIFICATIONS, scripts, payload, runner))
        _write_state(state_path, client)
    finally:
        try:
            lock_path.unlink()
        except OSError:
            pass
    return "\n".join(filter(None, (relevant_report(r) for r in results)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--client", choices=("claude", "codex", "copilot"), default="codex")
    try:
        args, _unknown = parser.parse_known_args(argv)
        try:
            payload = sys.stdin.buffer.read()
        except OSError:
            payload = b""
        vault = _vault()
        _prewarm_embed_model(vault)
        report = coordinate(args.client, vault, payload)
        # De statusregel gaat VOOROP en verschijnt altijd, ook als er verder
        # niets te melden viel. Zonder die regel is een stille sessiestart niet
        # te onderscheiden van een kapotte: beide leveren niets op.
        try:
            regel = status_line(vault, worker_running=worker_is_alive(vault))
            report = f"{regel}\n{report}" if report else regel
        except Exception:
            pass
        _emit(args.client, report)
    except Exception:
        # Session startup and agent operation must never depend on KennisBank.
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
