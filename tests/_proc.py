"""Een subprocess-aanroep die zijn tijdbudget ECHT respecteert.

subprocess.run(timeout=N) belooft minder dan het lijkt. De timeout bewaakt het
directe kind, maar bij het aflopen roept run() communicate() aan, en die wacht
tot de pijpen dichtgaan. Een kleinkind dat stdout heeft geerfd houdt die pijp
open, dus de aanroeper blijft hangen tot HET kleinkind klaar is -- niet tot het
budget op is.

Gemeten op deze machine, budget 3 s, bash start een kleinkind dat 25 s slaapt:

    TimeoutExpired na 25.4s (budget was 3s)

Waarom dat hier uitmaakt: doctor.sh start 54 Python-processen. Op een belaste
machine liep `test_copilot_doctor` daardoor 393 seconden op een budget van 120,
en viel daarna alsnog om. Een suite die onder belasting onbegrensd uitloopt
leert mensen hem opnieuw te draaien in plaats van hem te lezen.

Twee dingen lossen het op, en allebei zijn nodig:

1. Schrijf naar een BESTAND in plaats van naar een pijp. Dan heeft de aanroeper
   niets om op te wachten; erven kleinkinderen de handle, dan schrijven ze in
   het bestand en niemand blokkeert.
2. Dood bij een timeout de hele procesboom, niet alleen het directe kind. Anders
   blijven de kleinkinderen CPU gebruiken terwijl de volgende test al draait --
   precies de vervuiling die deze meting in eerste instantie vertroebelde.

Alleen stdlib: de suite mag geen afhankelijkheid krijgen die CI niet heeft.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

#: Hoe lang we na een kill nog wachten tot de boom echt weg is. Ruim genoeg
#: voor een interpreter die zijn atexit-hooks afwerkt, kort genoeg om niet
#: alsnog het probleem te worden dat we oplossen.
REAP_SEC = 5.0

#: Pollinterval. Klein genoeg om het budget scherp te houden, groot genoeg om
#: niet zelf een core bezig te houden met wachten.
POLL_SEC = 0.05


@dataclass
class Uitkomst:
    output: str          #: stdout en stderr samengevoegd, in die volgorde
    returncode: int | None   #: None als we hem hebben afgekapt
    timed_out: bool
    duur: float


def _dood_de_boom(proc: subprocess.Popen) -> None:
    """Dood het proces EN alles wat het gestart heeft.

    proc.kill() raakt alleen het directe kind. De 54 Python-processen van
    doctor.sh zijn kleinkinderen; die overleven dat en blijven de machine
    belasten. Windows heeft geen procesgroepen zoals POSIX, dus daar doet
    taskkill /T het werk.
    """
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True, check=False)
    else:
        import signal
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    try:
        proc.wait(timeout=REAP_SEC)
    except subprocess.TimeoutExpired:
        proc.kill()  # laatste redmiddel; de boom is dan al losgekoppeld


def run_bounded(cmd, *, cwd=None, env=None, timeout: float,
                encoding: str = "utf-8") -> Uitkomst:
    """Draai *cmd* en kom gegarandeerd binnen *timeout* terug.

    Geeft altijd de output terug die er op dat moment was, ook bij een timeout:
    een test die afkapt wil juist zien hoe ver het kwam.
    """
    # Bewust mkdtemp met handmatig opruimen, geen TemporaryDirectory. Op
    # Windows houdt een zojuist gedood kleinkind de geerfde handle nog even
    # vast, en dan gooit de automatische opruiming een PermissionError -- een
    # test die correct afkapte zou dan alsnog rood worden op het opruimen.
    d = tempfile.mkdtemp(prefix="kb-proc-")
    try:
        uit = Path(d) / "uit.txt"
        with uit.open("wb") as fh:
            kw = {}
            if os.name != "nt":
                kw["start_new_session"] = True   # eigen procesgroep om te killen
            proc = subprocess.Popen(
                cmd, cwd=cwd, env=env, stdout=fh,
                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **kw)
            begin = time.monotonic()
            afgekapt = False
            while True:
                if proc.poll() is not None:
                    break
                if time.monotonic() - begin > timeout:
                    _dood_de_boom(proc)
                    afgekapt = True
                    break
                time.sleep(POLL_SEC)
            duur = time.monotonic() - begin
        tekst = uit.read_text(encoding=encoding, errors="replace")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return Uitkomst(output=tekst,
                    returncode=None if afgekapt else proc.returncode,
                    timed_out=afgekapt, duur=duur)
