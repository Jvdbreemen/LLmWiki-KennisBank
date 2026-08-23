#!/usr/bin/env python3
"""_sweepstate.py - watermark + transcript-reader voor de capture-sweep.

Spiegelt distill-notify's .distilled-pattern met een EIGEN .swept-watermark, zodat
de geheugen-sweep onafhankelijk van de destillatie bijhoudt welke transcripts al
tot memory verwerkt zijn. transcript_text() reduceert een CC-.jsonl tot platte
user/assistant-tekst (fail-soft).

Stdlib only.
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import outside_window  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

WATERMARK = ".swept"

#: De single-flight lock van de sweep. Woont hier omdat de sweep hem zelf
#: verwerft, vasthoudt en vrijgeeft; sweep-launch is alleen nog een spawn-gate.
#:
#: Waarom de sweep en niet de launcher. De launcher spawnt gedetacheerd en
#: eindigt direct, dus er is geen proces meer dat een lease kan verversen. De
#: sweep is het enige proces dat weet dat hij nog leeft. En er zijn drie
#: aanroepers: sweep-launch, commands/kennisbank/rebuild-memory.md en
#: index-launch.py -- de laatste twee slaan de launcher over. Zolang alleen de
#: launcher verwierf, was "de launcher neemt, de sweep geeft vrij" geen contract
#: maar een aanname, en gaven die twee een slot vrij dat ze nooit namen.
LOCK_NAME = ".sweep.lock"

#: Een lock ouder dan dit geldt als verweesd. Woonde in sweep-launch; verhuisd
#: omdat verwerven en oordelen bij elkaar horen.
STALE_SEC = 3600

#: Hoe vaak de lease-thread de mtime aanraakt.
LEASE_REFRESH_SEC = 30

#: Bovengrens op de lease. Een tikkende thread bewijst dat het PROCES leeft, niet
#: dat er voortgang is. Zonder plafond houdt een vastgelopen sweep zijn slot voor
#: onbepaalde tijd en ligt al het onderhoud stil tot iemand het lockbestand met
#: de hand weggooit -- de spiegel van de bug die de lease oploste: eerst dubbel
#: werk door valse staleness, dan nul werk door valse liveness. Met een plafond
#: verloopt het slot alsnog, en is het ergste geval weer een vertraging in plaats
#: van een blokkade.
LEASE_MAX_SEC = 4 * STALE_SEC


def lock_path(vault=None) -> Path:
    return (vault or vault_root()) / ".claude" / LOCK_NAME


def is_stale(lock: Path) -> bool:
    """True als de lock verder dan STALE_SEC van nu af ligt -- in het verleden
    (verweesd) of in de toekomst (klokverzetting; zonder die kant verloopt zo'n
    lock nooit en ligt het onderhoud permanent stil).

    Het venster is SYMMETRISCH en niet `age < 0`, want een verse mtime kan op
    Windows in de toekomst liggen: `time.time()` leest daar
    GetSystemTimeAsFileTime met een resolutie van 15,625 ms, terwijl het
    bestandssysteem de mtime van een fijnere klok stempelt. Gemeten: 586 van
    5000 net aangemaakte bestanden gaven age < 0 (max +0,016 s). Met `age < 0`
    verklaarde acquire_lock dus 12% van zijn EIGEN verse locks stale, ruimde ze
    op en gaf single-flight weg (TASK-140)."""
    try:
        age = time.time() - lock.stat().st_mtime
        return outside_window(age, STALE_SEC)
    except OSError:
        return True


def _new_token() -> str:
    """Een token dat dit proces identificeert. PID alleen volstaat niet: PIDs
    worden hergebruikt, en na een reboot kan een vreemd proces het nummer van de
    vorige houder dragen."""
    return f"{os.getpid()}:{os.urandom(8).hex()}"


def _read_token(lock: Path) -> "str | None":
    try:
        return lock.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _touch(lock: Path) -> None:
    """Werk de mtime bij zonder een symlink te volgen.

    `Path.touch()` volgt symlinks; `acquire` gebruikt O_CREAT|O_EXCL en doet dat
    bewust niet. Die asymmetrie weghalen scheelt een pad waarop de sweep de mtime
    van een willekeurig bestand bijwerkt. O_NOFOLLOW bestaat niet op Windows;
    daar valt hij terug op utime, wat geen regressie is ten opzichte van touch().
    """
    if os.utime not in getattr(os, "supports_fd", ()):
        # Windows kent geen utime op een fd en geen O_NOFOLLOW. Terugvallen op
        # het pad is daar geen regressie: Path.touch() deed niets anders.
        try:
            os.utime(str(lock))
        except OSError:
            pass
        return
    flags = os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(str(lock), flags)
    except OSError:
        return  # fail-open: onderhoud stopt nooit op een lease-touch
    try:
        os.utime(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def acquire_lock(vault=None, token: "str | None" = None) -> "str | None":
    """Neem de lock atomair. Geeft het token terug, of None als een ander hem heeft.

    1. O_CREAT|O_EXCL direct -- slaagt als de lock nog niet bestaat.
    2. Bij FileExistsError: is hij stale?
       - Nee  -> er draait een sweep; None.
       - Ja   -> opruimen en een keer opnieuw proberen.
    """
    lock = lock_path(vault)
    tok = token or _new_token()
    lock.parent.mkdir(parents=True, exist_ok=True)
    for poging in (1, 2):
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, tok.encode("utf-8"))
            finally:
                os.close(fd)
            return tok
        except FileExistsError:
            if poging == 2 or not is_stale(lock):
                return None
            try:
                lock.unlink()
            except OSError:
                return None
        except OSError:
            return None
    return None


def release_lock(vault=None, token: "str | None" = None) -> bool:
    """Geef de lock vrij. Met een token: alleen als hij nog van ons is.

    Zonder eigenaarscheck verwijdert een sweep die de lock nooit nam het slot van
    een sweep die nog draait, waarna de volgende launcher een tweede spawnt. Het
    patroon staat al in index-launch.py:249 -- "Release only our lock; an old
    worker must not remove a newer one".

    Fail-open: een niet-verwijderbare lock verloopt vanzelf na STALE_SEC.
    """
    lock = lock_path(vault)
    if token is not None and _read_token(lock) != token:
        return False
    try:
        lock.unlink()
        return True
    except OSError:
        return False


@contextlib.contextmanager
def sweep_lock(vault=None):
    """Yield True als dit proces de lock bezit, False als een ander hem heeft.

    Verwerven, verversen en vrijgeven zitten in een constructie, zodat er geen
    pad meer bestaat waarop de lock blijft liggen: elke vroege return en elke
    exception loopt door de finally. Voorheen stonden acquire en release in
    verschillende modules met ~290 regels ertussen en zonder try/finally.

    De lease-thread bindt het vault-pad EEN keer. Resolveerde hij `vault_root()`
    per tik, dan volgt hij een gewijzigde KENNISBANK_VAULT: gemeten schrijft een
    thread die een test overleeft daarna in de vault waar de env-var naartoe is
    hersteld. De tests gebruiken juist een tijdelijke vault om dat te vermijden.
    """
    lock = lock_path(vault)
    tok = acquire_lock(vault)
    if tok is None:
        yield False
        return

    stop = threading.Event()
    begin = time.monotonic()

    def _loop():
        while not stop.wait(LEASE_REFRESH_SEC):
            if time.monotonic() - begin > LEASE_MAX_SEC:
                return          # plafond: laat het slot alsnog verlopen
            if _read_token(lock) != tok:
                return          # niet meer van ons; niet blijven tikken
            _touch(lock)

    threading.Thread(target=_loop, daemon=True, name="sweep-lease").start()
    try:
        yield True
    finally:
        stop.set()
        release_lock(vault, tok)


def _tdir(vault=None) -> Path:
    return (vault or vault_root()) / "01-raw" / "transcripts"


def _watermark(vault=None) -> set:
    f = _tdir(vault) / WATERMARK
    try:
        return {ln.strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()}
    except OSError:
        return set()


def pending(vault=None) -> list:
    d = _tdir(vault)
    if not d.exists():
        return []
    done = _watermark(vault)
    return [p for p in sorted(d.glob("*.jsonl")) if p.stem not in done]


def mark(stems, vault=None) -> int:
    done = _watermark(vault)
    new = [s for s in dict.fromkeys(stems) if s and s not in done]
    if not new:
        return 0
    f = _tdir(vault) / WATERMARK
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            for s in new:
                fh.write(s + "\n")
    except OSError as e:
        print(f"[sweepstate] kan watermark niet schrijven: {e}", file=sys.stderr)
        return 0
    return len(new)


#: Content-block kinds that carry conversation text. Claude Code writes "text";
#: Codex writes "input_text" on the way in and "output_text" on the way out.
_TEXT_BLOCKS = ("text", "input_text", "output_text")

#: Roles that count as conversation. "developer" is deliberately NOT one: that is
#: the injected instruction block (AGENTS.md, and inside it KennisBank's own
#: block), so capturing it would have the extractor summarise its own
#: instructions.
_ROLES = ("user", "assistant")


def _block_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") in _TEXT_BLOCKS:
                parts.append(str(block.get("text", "")))
        return "\n".join(parts)
    return ""


def transcript_text(jsonl_path) -> str:
    """Reduce a transcript jsonl to flat user/assistant text. Fail-soft.

    Three shapes, because the vault archives transcripts from several clients:

    - Claude Code: every record has ``message`` with ``role`` and ``content``.
    - Codex: every record is ``{timestamp, type, payload}``. The conversation
      lives under ``type == "response_item"`` with ``payload.type == "message"``;
      the rest (``reasoning``, ``custom_tool_call``, ``function_call``,
      ``token_count``) is tool noise, exactly as the Claude branch already takes
      user/assistant only. ``event_msg``/``agent_message`` repeats the assistant
      text and is skipped so it cannot double-count.
    - Copilot: a hook event log of flat records where ``message`` is a STRING and
      ``role`` sits beside it. Only ``role == "user"`` carries conversation;
      ``tool_use`` and ``session`` are tooling and lifecycle. Assistant replies
      are absent from this format altogether, so it yields half a conversation --
      better than nothing, but not a full transcript.

    Without the Codex and Copilot branches this function returned NOTHING for 39
    of the 299 archived transcripts, together 94 MB of session content: a capture
    layer that was entirely blind rather than partly (TASK-145).
    """
    out = []
    try:
        with Path(jsonl_path).open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if not isinstance(rec, dict):
                    continue
                msg = rec.get("message")
                if isinstance(msg, dict):
                    role = msg.get("role")
                    if role in _ROLES:
                        t = _block_text(msg.get("content")).strip()
                        if t:
                            out.append(f"{role}: {t}")
                    continue
                if isinstance(msg, str) and rec.get("role") in _ROLES:
                    role = rec.get("role")
                    t = msg.strip()
                    # The hook writes "userPromptSubmitted: <prompt>"; the event
                    # name is metadata and does not belong in the knowledge.
                    event = str(rec.get("event") or "")
                    if event and t.startswith(event + ":"):
                        t = t[len(event) + 1:].strip()
                    if t:
                        out.append(f"{role}: {t}")
                    continue
                payload = rec.get("payload")
                if rec.get("type") == "response_item" and isinstance(payload, dict) \
                        and payload.get("type") == "message":
                    role = payload.get("role")
                    if role in _ROLES:
                        t = _block_text(payload.get("content")).strip()
                        if t:
                            out.append(f"{role}: {t}")
    except Exception:
        return ""
    return "\n\n".join(out)
