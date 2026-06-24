# CC transcript-archief + piggyback-destillatie — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Elke Claude Code-sessie wordt bij afsluiten automatisch naar de vault gearchiveerd, en de gebruiker kan de gearchiveerde transcripts met één commando in de wiki-pijplijn destilleren.

**Architecture:** Twee ontkoppelde helften. (1) Een Python `SessionEnd`-hook kopieert het transcript deterministisch en fail-open naar `$VAULT/01-raw/transcripts/`. (2) Een Python `SessionStart`-hook meldt openstaande transcripts; de gebruiker trekt de dure LLM-destillatie via het nieuwe `/destilleer`-commando (`import-cc-history.py --source` → `/wiki`). Het archief is de enige bron van waarheid, dus `cleanupPeriodDays` doet er niet meer toe.

**Tech Stack:** Python 3.10+ (stdlib only), pytest (`unittest`-stijl, geladen via `tests/_loader.py`), Claude Code-hooks geregistreerd in de globale `~/.claude/settings.json` via de Windows `py -3`-launcher. Markdown slash-command.

## Global Constraints

- **Vault-resolutie:** altijd via `_vaultpath.vault_root()` (`$KENNISBANK_VAULT` of `~/KennisBank`). NOOIT een hardcoded vault-pad. Hooks self-locaten met `os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))` vóór de import.
- **Hooks zijn fail-open:** elke fout logt naar stderr en eindigt met `exit 0`. Een hook mag een sessie nooit blokkeren, vertragen of laten crashen.
- **Stdlib only** in alle scripts (geen externe pip-deps). Geen `jq`, geen Git Bash-afhankelijkheid.
- **Geen em dashes** in command-prose en docs (projectconventie). Taal: Nederlands.
- **Scripts gebruiken hyphen-bestandsnamen** en worden in tests geladen via `tests/_loader.py::load_script("naam.py")`. Importeerbare helpers (gedeeld) hebben GEEN hyphen.
- **Bestanden in `01-raw/transcripts/` en de watermark `.distilled` leven in de VAULT** (`D:/Users/Robert/Documents/Claude/Projects/Kluis`), niet in de git-repo. De repo wijzigt alleen scripts/commands/docs/setup.

---

## File Structure

| Bestand | Rol |
|---|---|
| `scripts/archive-transcript.py` | **nieuw.** SessionEnd-hook. `archive(hook, vault)` (pure) + `main()` (stdin→exit 0). Eén taak: transcript veilig kopiëren. |
| `scripts/distill-notify.py` | **nieuw.** SessionStart-hook + watermark-logica. `pending(vault)`, `mark(vault, stems)`, `main()` (notify, `--list-pending`, of `--mark <stem...>`). |
| `scripts/import-cc-history.py` | **wijzig.** `--source <dir>`-flag + `collect_jsonl(root, flat)`-helper, zodat een platte archiefmap geïmporteerd kan worden. |
| `commands/destilleer.md` | **nieuw.** Dun orkestratie-commando: snapshot → import `--source` → `/wiki` → `--mark $BATCH`. |
| `setup.sh` | **wijzig.** Eén regel: `01-raw/transcripts` toevoegen aan de vault-`mkdir`. Scripts/commands deployen al via bestaande globs. |
| `CONFIGURATION.md` | **wijzig.** Sectie met de exacte `settings.json`-hookregistratie (`py -3 ...`) + watermark-uitleg. |
| `CHANGELOG.md`, `README.md`, `vault-structure/README.md` | **wijzig.** Documenteer de nieuwe map, hooks en het commando. |
| `tests/test_archive_transcript.py` | **nieuw.** Unit-tests voor `archive-transcript.py`. |
| `tests/test_distill_notify.py` | **nieuw.** Unit-tests voor `distill-notify.py`. |
| `tests/test_import_source_flag.py` | **nieuw.** Unit-tests voor `import-cc-history.py --source`. |

---

## Task 1: Archiefhook — `scripts/archive-transcript.py`

**Files:**
- Create: `scripts/archive-transcript.py`
- Test: `tests/test_archive_transcript.py`

**Interfaces:**
- Consumes: `_vaultpath.vault_root()`, `_common.slugify(text)`.
- Produces:
  - `dest_path(vault: Path, hook: dict, src: Path) -> Path` — bestemmingspad `<vault>/01-raw/transcripts/<YYYY-MM-DD>-<project-slug>-<sid8>.jsonl`.
  - `archive(hook: dict, vault: Path) -> dict` — kopieert; return `{"status": "archived"|"skipped-empty"|"skipped-uptodate"|"error", ...}`.
  - `main() -> int` — leest stdin-JSON, roept `archive()`, returnt altijd `0`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_archive_transcript.py
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script

mod = load_script("archive-transcript.py")


def _make_transcript(dir_: Path, name: str, n_records: int) -> Path:
    p = dir_ / name
    lines = []
    for i in range(n_records):
        lines.append(json.dumps({
            "type": "user", "sessionId": "ABCDEF1234567890",
            "cwd": "/home/u/myproject",
            "timestamp": "2026-06-24T10:00:00Z",
            "message": {"role": "user", "content": f"turn {i} with enough text to pass the size floor"},
        }))
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


class ArchiveTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-arch-"))
        self.vault = self.tmp / "vault"
        self.src_dir = self.tmp / "src"
        self.src_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dest_path_shape(self):
        src = _make_transcript(self.src_dir, "session.jsonl", 5)
        hook = {"transcript_path": str(src), "session_id": "ABCDEF1234567890",
                "cwd": "/home/u/myproject"}
        dst = mod.dest_path(self.vault, hook, src)
        self.assertEqual(dst.parent, self.vault / "01-raw" / "transcripts")
        self.assertTrue(dst.name.endswith("-myproject-abcdef12.jsonl"), dst.name)

    def test_archive_copies_file(self):
        src = _make_transcript(self.src_dir, "session.jsonl", 5)
        hook = {"transcript_path": str(src), "session_id": "ABCDEF1234567890",
                "cwd": "/home/u/myproject"}
        res = mod.archive(hook, self.vault)
        self.assertEqual(res["status"], "archived")
        self.assertTrue(Path(res["dest"]).is_file())

    def test_archive_idempotent_same_session(self):
        src = _make_transcript(self.src_dir, "session.jsonl", 5)
        hook = {"transcript_path": str(src), "session_id": "ABCDEF1234567890",
                "cwd": "/home/u/myproject"}
        mod.archive(hook, self.vault)
        res2 = mod.archive(hook, self.vault)
        self.assertEqual(res2["status"], "skipped-uptodate")
        files = list((self.vault / "01-raw" / "transcripts").glob("*.jsonl"))
        self.assertEqual(len(files), 1)

    def test_archive_overwrites_when_source_grew(self):
        # Dekt de 'transcript groeit'-tak en de session-gekeyde dedup: een
        # gegroeide bron overschrijft DEZELFDE archieffile (1 bestand), ook al
        # zou de datum-prefix bij een dagovergang anders zijn.
        src = _make_transcript(self.src_dir, "session.jsonl", 5)
        hook = {"transcript_path": str(src), "session_id": "ABCDEF1234567890",
                "cwd": "/home/u/myproject"}
        mod.archive(hook, self.vault)
        _make_transcript(self.src_dir, "session.jsonl", 60)  # bron groeit
        res2 = mod.archive(hook, self.vault)
        self.assertEqual(res2["status"], "archived")
        files = list((self.vault / "01-raw" / "transcripts").glob("*.jsonl"))
        self.assertEqual(len(files), 1)

    def test_archive_skips_empty(self):
        src = self.src_dir / "tiny.jsonl"
        src.write_text("{}\n", encoding="utf-8")
        hook = {"transcript_path": str(src), "session_id": "X", "cwd": "/x"}
        res = mod.archive(hook, self.vault)
        self.assertEqual(res["status"], "skipped-empty")

    def test_archive_missing_source_is_error_not_raise(self):
        hook = {"transcript_path": str(self.src_dir / "nope.jsonl"),
                "session_id": "X", "cwd": "/x"}
        res = mod.archive(hook, self.vault)
        self.assertEqual(res["status"], "error")

    def test_main_exit_zero_on_garbage_stdin(self):
        import io
        old = sys.stdin
        sys.stdin = io.StringIO("not json at all")
        try:
            self.assertEqual(mod.main(), 0)
        finally:
            sys.stdin = old


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_archive_transcript.py -v`
Expected: FAIL — `FileNotFoundError: script not found: .../scripts/archive-transcript.py` (script bestaat nog niet).

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/archive-transcript.py
#!/usr/bin/env python3
"""archive-transcript.py — SessionEnd-hook: archiveer een CC-transcript.

Leest de SessionEnd-hook-JSON op stdin (transcript_path, session_id, cwd, reason)
en kopieert het transcript naar $VAULT/01-raw/transcripts/<datum>-<slug>-<sid8>.jsonl.

FAIL-OPEN, ALTIJD: elke fout logt naar stderr en eindigt met exit 0, zodat de hook
het afsluiten van een sessie nooit blokkeert. Idempotent: dezelfde sessie 2x
archiveren overschrijft alleen als de bron groter is (transcript groeit).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Self-locate de vault als KENNISBANK_VAULT ontbreekt in de hook-env (idem aan
# kb-retrieve.py / build-embed-index.py). Het script woont in
# <vault>/.claude/scripts/, dus parents[2] == <vault>.
os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402
from _common import slugify  # noqa: E402

MIN_BYTES = 200  # lege/-p-transcripts overslaan

# NB: spec-regel 102 noemt een OPTIONELE retry voor de partial-write-race
# (transcript nog niet volledig geschreven). Bewust weggelaten in v1: SessionEnd
# draait synchroon vóór exit (transcript is dan geflusht), en de groei-overschrijf
# in archive() (overschrijft alleen als de bron groter is) is het vangnet als er
# ooit toch een te korte kopie landt en de bron later groeit.


def _date_from_transcript(src: Path) -> str:
    try:
        return datetime.fromtimestamp(src.stat().st_mtime).date().isoformat()
    except OSError:
        return datetime.now().date().isoformat()


def _sid8(session_id: str | None, fallback: str) -> str:
    sid = (session_id or fallback or "").lower()
    cleaned = "".join(c for c in sid if c.isalnum())
    return cleaned[:8] or "noid"


def dest_path(vault: Path, hook: dict, src: Path) -> Path:
    cwd = hook.get("cwd") or ""
    slug = slugify(Path(cwd).name) if cwd else "unknown"
    sid8 = _sid8(hook.get("session_id"), src.stem)
    date = _date_from_transcript(src)
    return vault / "01-raw" / "transcripts" / f"{date}-{slug}-{sid8}.jsonl"


def archive(hook: dict, vault: Path) -> dict:
    tp = (hook.get("transcript_path") or "").strip()
    if not tp:
        return {"status": "error", "reason": "no transcript_path"}
    src = Path(os.path.expanduser(tp))
    if not src.is_file():
        return {"status": "error", "reason": f"source missing: {src}"}
    try:
        size = src.stat().st_size
    except OSError as e:
        return {"status": "error", "reason": str(e)}
    if size < MIN_BYTES:
        return {"status": "skipped-empty", "bytes": size}

    # Session-gekeyde dedup: hergebruik een bestaande archieffile met dezelfde
    # sid8, ongeacht de datum-prefix. Zo levert een SessionEnd-refire (bv. na
    # /clear, of een transcript dat over een dagovergang groeit) GEEN duplicaat.
    tdir = vault / "01-raw" / "transcripts"
    sid8 = _sid8(hook.get("session_id"), src.stem)
    try:
        existing = sorted(tdir.glob(f"*-{sid8}.jsonl"))
    except OSError:
        existing = []
    dst = existing[0] if existing else dest_path(vault, hook, src)
    if dst.exists():
        try:
            if dst.stat().st_size >= size:
                return {"status": "skipped-uptodate", "dest": str(dst)}
        except OSError:
            pass
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    except OSError as e:
        return {"status": "error", "reason": str(e)}
    return {"status": "archived", "dest": str(dst), "bytes": size}


def main() -> int:
    try:
        raw = sys.stdin.read()
        hook = json.loads(raw) if raw.strip() else {}
        if not isinstance(hook, dict):
            hook = {}
    except (json.JSONDecodeError, OSError, ValueError):
        hook = {}
    try:
        result = archive(hook, vault_root())
    except Exception as e:  # fail-open
        print(f"[archive-transcript] unexpected: {e}", file=sys.stderr)
        return 0
    if result.get("status") == "error":
        print(f"[archive-transcript] {result.get('reason')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    # Wrap ook de entry: een import- of opstartfout mag nooit een niet-nul exit
    # geven (mirror van kb-retrieve.py's fail-open __main__).
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_archive_transcript.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/archive-transcript.py tests/test_archive_transcript.py
git commit -m "feat(archive): SessionEnd-hook archiveert CC-transcripts naar de vault"
```

---

## Task 2: `import-cc-history.py --source` flag

**Files:**
- Modify: `scripts/import-cc-history.py` (argparse-blok regel 250-267; glob regel 279; existence-check regel 272-274)
- Test: `tests/test_import_source_flag.py`

**Interfaces:**
- Produces: `collect_jsonl(root: Path, flat: bool) -> list[Path]` — `flat=True` globt `*.jsonl` (platte archiefmap), `flat=False` globt `*/*.jsonl` (CC `projects`-layout).
- Consumes (CLI): `--source <dir>` zet de bron op een platte archiefmap; default-gedrag (`--projects-dir`) blijft ongewijzigd.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_import_source_flag.py
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script

mod = load_script("import-cc-history.py")


class CollectJsonlTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-imp-"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_flat_glob_finds_top_level_jsonl(self):
        (self.tmp / "a.jsonl").write_text("{}\n", encoding="utf-8")
        (self.tmp / "b.jsonl").write_text("{}\n", encoding="utf-8")
        found = mod.collect_jsonl(self.tmp, flat=True)
        self.assertEqual(len(found), 2)

    def test_nested_glob_finds_project_layout(self):
        proj = self.tmp / "project-x"
        proj.mkdir()
        (proj / "s.jsonl").write_text("{}\n", encoding="utf-8")
        found = mod.collect_jsonl(self.tmp, flat=False)
        self.assertEqual(len(found), 1)

    def test_flat_glob_ignores_nested(self):
        proj = self.tmp / "project-x"
        proj.mkdir()
        (proj / "s.jsonl").write_text("{}\n", encoding="utf-8")
        found = mod.collect_jsonl(self.tmp, flat=True)
        self.assertEqual(len(found), 0)


class SourceImportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-imp2-"))
        self.archive = self.tmp / "transcripts"
        self.archive.mkdir(parents=True)
        self.vault = self.tmp / "vault"
        rec = json.dumps({
            "type": "user", "sessionId": "FEED0000",
            "cwd": "/home/u/proj", "timestamp": "2026-06-24T09:00:00Z",
            "message": {"role": "user", "content": "Hoe werkt de archiefhook precies?"},
        })
        (self.archive / "2026-06-24-proj-feed0000.jsonl").write_text(rec + "\n", encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_source_flag_imports_flat_archive(self):
        old = sys.argv
        sys.argv = ["import-cc-history.py", "--source", str(self.archive),
                    "--vault", str(self.vault)]
        try:
            rc = mod.main()
        finally:
            sys.argv = old
        self.assertEqual(rc, 0)
        out = list((self.vault / "01-raw" / "sessies").glob("raw-sessie-*.md"))
        self.assertEqual(len(out), 1, out)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_import_source_flag.py -v`
Expected: FAIL met TWEE foutmodi (beide rood, beide correct voor de red-fase):
- `CollectJsonlTest`: `AttributeError: module ... has no attribute 'collect_jsonl'`.
- `SourceImportTest`: `SystemExit: 2 — unrecognized arguments: --source` (argparse weigert de onbekende flag vóór enige AttributeError).

- [ ] **Step 3: Write minimal implementation**

Add the helper above `main()` in `scripts/import-cc-history.py`:

```python
def collect_jsonl(root: Path, flat: bool) -> list[Path]:
    """Verzamel jsonl-bestanden. flat=True: platte archiefmap (*.jsonl);
    flat=False: CC projects-layout (*/*.jsonl).

    NB: onder flat=True (een --source archiefmap) is jsonl_path.parent.name
    'transcripts' voor elke sessie, dus parse_session's project_slug wordt
    generiek 'transcripts'. Onschadelijk: render_body gebruikt cwd_display (de
    echte cwd uit het record) en target_path keyt op first_user_text+date+
    session_id. project_slug is alleen een fallback die voor gearchiveerde
    transcripts (die altijd een cwd-veld hebben) nooit wordt geraakt."""
    pattern = "*.jsonl" if flat else "*/*.jsonl"
    return sorted(root.glob(pattern))
```

In `main()`, add the `--source` argument right after the `--projects-dir` line (around line 257):

```python
    parser.add_argument("--source", type=Path, default=None,
                        help="Platte map met gearchiveerde *.jsonl-transcripts "
                             "(bv. $VAULT/01-raw/transcripts). Overschrijft --projects-dir.")
```

Replace the source-resolution + existence-check + glob (current lines 269-281):

```python
    if args.source is not None:
        src_root: Path = args.source
        flat = True
    else:
        src_root = args.projects_dir
        flat = False
    out_dir: Path = args.vault / "01-raw" / "sessies"

    if not src_root.exists():
        print(f"[error] bron-dir niet gevonden: {src_root}", file=sys.stderr)
        return 2

    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    jsonl_files = collect_jsonl(src_root, flat)
    if args.limit:
        jsonl_files = jsonl_files[: args.limit]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_import_source_flag.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Run the full suite to confirm no regression**

Run: `python -m pytest tests/ -q`
Expected: all pass (the existing importer behaviour is unchanged when `--source` is absent).

- [ ] **Step 6: Commit**

```bash
git add scripts/import-cc-history.py tests/test_import_source_flag.py
git commit -m "feat(import): --source flag importeert een platte transcript-archiefmap"
```

---

## Task 3: Destillatie-notificatie + watermark — `scripts/distill-notify.py`

**Files:**
- Create: `scripts/distill-notify.py`
- Test: `tests/test_distill_notify.py`

**Interfaces:**
- Produces:
  - `pending(vault: Path) -> list[str]` — stems van transcripts in `01-raw/transcripts/` die niet in `.distilled` staan.
  - `mark(vault: Path, stems: list[str]) -> int` — APPENDt exact de meegegeven stems aan `.distilled` (dedup), returnt het aantal nieuw toegevoegde. Markeert NOOIT meer dan de meegegeven set (lost de race op waarbij een transcript dat tijdens `/wiki` binnenkomt onterecht als gedestilleerd zou worden gemarkeerd).
  - `main() -> int` — `--list-pending` → print pending stems (één per regel); `--mark <stem...>` → markeert die stems; anders → SessionStart-notify (emit `additionalContext` JSON als er pending zijn, anders niets). Altijd exit 0.
- Watermark: `<vault>/01-raw/transcripts/.distilled`, één **stem** per regel (bv. `2026-06-24-myproject-abcdef12`). NB: de spec sprak van "session_ids"; in de implementatie zijn dit transcript-stems — functioneel equivalent want de stem bevat de sid8. De spec-bewoording is hierop aangelijnd.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_distill_notify.py
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script

mod = load_script("distill-notify.py")


class DistillNotifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-dn-"))
        self.vault = self.tmp / "vault"
        self.tdir = self.vault / "01-raw" / "transcripts"
        self.tdir.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _add(self, name):
        (self.tdir / name).write_text("{}\n", encoding="utf-8")

    def test_pending_lists_unmarked(self):
        self._add("2026-06-24-a-aaaa1111.jsonl")
        self._add("2026-06-24-b-bbbb2222.jsonl")
        self.assertEqual(len(mod.pending(self.vault)), 2)

    def test_mark_marks_only_given(self):
        self._add("2026-06-24-a-aaaa1111.jsonl")
        self._add("2026-06-24-b-bbbb2222.jsonl")
        n = mod.mark(self.vault, ["2026-06-24-a-aaaa1111"])
        self.assertEqual(n, 1)
        self.assertEqual(mod.pending(self.vault), ["2026-06-24-b-bbbb2222"])

    def test_mark_is_append_not_overwrite(self):
        self._add("2026-06-24-a-aaaa1111.jsonl")
        self._add("2026-06-24-b-bbbb2222.jsonl")
        mod.mark(self.vault, ["2026-06-24-a-aaaa1111"])
        mod.mark(self.vault, ["2026-06-24-b-bbbb2222"])
        self.assertEqual(mod.pending(self.vault), [])

    def test_mark_dedups(self):
        self._add("2026-06-24-a-aaaa1111.jsonl")
        self.assertEqual(mod.mark(self.vault, ["2026-06-24-a-aaaa1111"]), 1)
        self.assertEqual(mod.mark(self.vault, ["2026-06-24-a-aaaa1111"]), 0)

    def test_new_file_after_mark_is_pending(self):
        self._add("2026-06-24-a-aaaa1111.jsonl")
        mod.mark(self.vault, ["2026-06-24-a-aaaa1111"])
        self._add("2026-06-24-c-cccc3333.jsonl")
        self.assertEqual(len(mod.pending(self.vault)), 1)

    def _run_main(self, argv, stdin="{}"):
        """Roep main() aan met gepatchte argv/stdin/stdout en herstel ALLES,
        inclusief de KENNISBANK_VAULT-env (anders lekt die naar latere tests)."""
        import os
        out = io.StringIO()
        old_out, old_in, old_argv = sys.stdout, sys.stdin, sys.argv
        old_env = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        sys.stdout, sys.stdin, sys.argv = out, io.StringIO(stdin), argv
        try:
            rc = mod.main()
        finally:
            sys.stdout, sys.stdin, sys.argv = old_out, old_in, old_argv
            if old_env is None:
                os.environ.pop("KENNISBANK_VAULT", None)
            else:
                os.environ["KENNISBANK_VAULT"] = old_env
        return rc, out.getvalue()

    def test_main_notify_emits_context_when_pending(self):
        self._add("2026-06-24-a-aaaa1111.jsonl")
        rc, out = self._run_main(["distill-notify.py"])
        self.assertEqual(rc, 0)
        # NB: deze JSON-vorm wordt geassert tegen de eigen impl, niet tegen een
        # extern SessionStart-contract. Kruis het echte hook-outputformaat een
        # keer met de docs voor productie (zie kb-retrieve.py voor het UserPromptSubmit-precedent).
        payload = json.loads(out)
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("1", payload["hookSpecificOutput"]["additionalContext"])

    def test_main_notify_silent_when_none(self):
        rc, out = self._run_main(["distill-notify.py"])
        self.assertEqual(out.strip(), "")

    def test_main_list_pending_outputs_stems(self):
        self._add("2026-06-24-a-aaaa1111.jsonl")
        rc, out = self._run_main(["distill-notify.py", "--list-pending"])
        self.assertEqual(out.strip(), "2026-06-24-a-aaaa1111")

    def test_main_mark_via_cli(self):
        self._add("2026-06-24-a-aaaa1111.jsonl")
        self._run_main(["distill-notify.py", "--mark", "2026-06-24-a-aaaa1111"])
        self.assertEqual(mod.pending(self.vault), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_distill_notify.py -v`
Expected: FAIL — `FileNotFoundError: script not found: .../scripts/distill-notify.py`.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/distill-notify.py
#!/usr/bin/env python3
"""distill-notify.py — SessionStart-hook + destillatie-watermark.

Zonder argumenten (SessionStart-hook): telt gearchiveerde transcripts in
01-raw/transcripts/ die nog niet gedestilleerd zijn (niet in .distilled) en
injecteert een korte melding als additionalContext. Geen LLM, geen embed.

Met --list-pending: print de pending stems (één per regel) zodat /destilleer een
momentopname van de te verwerken set kan vastleggen.

Met --mark <stem...> (aangeroepen door /destilleer na een geslaagde import+wiki):
APPENDt exact die stems aan .distilled. Markeert nooit meer dan de meegegeven set,
zodat een transcript dat tijdens /wiki binnenkomt niet onterecht 'gedestilleerd' raakt.

FAIL-OPEN, ALTIJD: elke fout eindigt met exit 0 en injecteert niets.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

WATERMARK_NAME = ".distilled"


def _transcripts_dir(vault: Path) -> Path:
    return vault / "01-raw" / "transcripts"


def _read_watermark(vault: Path) -> set[str]:
    wm = _transcripts_dir(vault) / WATERMARK_NAME
    try:
        return {ln.strip() for ln in wm.read_text(encoding="utf-8").splitlines() if ln.strip()}
    except OSError:
        return set()


def _all_stems(vault: Path) -> list[str]:
    try:
        return sorted(p.stem for p in _transcripts_dir(vault).glob("*.jsonl"))
    except OSError:
        return []


def pending(vault: Path) -> list[str]:
    done = _read_watermark(vault)
    return [s for s in _all_stems(vault) if s not in done]


def mark(vault: Path, stems: list[str]) -> int:
    """Append exact de meegegeven stems aan .distilled (dedup). Markeert nooit
    de hele map: alleen de set die /destilleer daadwerkelijk verwerkte."""
    done = _read_watermark(vault)
    new = [s for s in dict.fromkeys(stems) if s and s not in done]
    if not new:
        return 0
    wm = _transcripts_dir(vault) / WATERMARK_NAME
    try:
        wm.parent.mkdir(parents=True, exist_ok=True)
        with wm.open("a", encoding="utf-8") as f:
            for s in new:
                f.write(s + "\n")
    except OSError as e:
        print(f"[distill-notify] kan watermark niet schrijven: {e}", file=sys.stderr)
        return 0
    return len(new)


def _emit_notify(count: int) -> None:
    if count <= 0:
        return
    ctx = (f"{count} gearchiveerde CC-transcript(s) wachten op destillatie. "
           f"Draai /destilleer om ze te importeren en in de wiki te verwerken.")
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": ctx,
        }
    }))


def main() -> int:
    # stdin leegtrekken (hook geeft JSON; we gebruiken het niet maar lezen het wel)
    try:
        sys.stdin.read()
    except OSError:
        pass
    try:
        vault = vault_root()
        argv = sys.argv[1:]
        if argv and argv[0] == "--mark":
            n = mark(vault, argv[1:])
            print(f"[distill-notify] gemarkeerd: {n} stem(s)", file=sys.stderr)
            return 0
        if argv and argv[0] == "--list-pending":
            for s in pending(vault):
                print(s)
            return 0
        _emit_notify(len(pending(vault)))
    except Exception as e:  # fail-open
        print(f"[distill-notify] unexpected: {e}", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    # Wrap ook de entry: een import- of opstartfout mag nooit een niet-nul exit
    # geven (mirror van kb-retrieve.py's fail-open __main__).
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_distill_notify.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/distill-notify.py tests/test_distill_notify.py
git commit -m "feat(distill): SessionStart-notify + .distilled watermark voor pending transcripts"
```

---

## Task 4: `/destilleer`-commando — `commands/destilleer.md`

**Files:**
- Create: `commands/destilleer.md`

**Interfaces:**
- Consumes: `scripts/import-cc-history.py --source`, `scripts/distill-notify.py --list-pending` + `--mark <stem...>`, en het bestaande `/wiki`-commando.
- Produces: geen code-interface (markdown slash-command). Roept Python aan met `python3 "$VAULT/.claude/scripts/..."` (conform de andere commands; macOS/Windows-Git-Bash hebben beide `python3`).

Dit is een prose-commando (geen unit-test). De stappen hieronder zijn de letterlijke inhoud van het bestand.

- [ ] **Step 1: Write the command file**

```markdown
Destilleer gearchiveerde Claude Code-transcripts uit de vault tot wiki-kennis.

## Vault-root bepalen (VERPLICHT — lees dit eerst)

Bepaal de vault-root EEN keer en gebruik die overal:
`VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`

Gebruik NOOIT een letterlijk pad. Alle scripts staan in `$VAULT/.claude/scripts/`.

## Doel
Tegenhanger van de archiefhook. De `SessionEnd`-hook (`archive-transcript.py`) heeft
transcripts naar `$VAULT/01-raw/transcripts/` gekopieerd. Dit commando trekt de dure
LLM-destillatie: importeer de nog niet verwerkte transcripts tot raw-sessielogs en
compileer ze tot wiki-artikelen. Idempotent via de `.distilled`-watermark.

## Stap 1: Leg de te verwerken set vast (snapshot)
```bash
BATCH=$(python3 "$VAULT/.claude/scripts/distill-notify.py" --list-pending < /dev/null)
echo "$BATCH"
```
`$BATCH` is de lijst pending transcript-stems (één per regel) op DIT moment. Is hij
leeg: meld "niets te destilleren" en stop. Bewaar deze set: stap 4 markeert exact
deze stems, niet wat er later in de map verschijnt.

## Stap 2: Importeer de archiefmap naar raw-sessielogs
```bash
python3 "$VAULT/.claude/scripts/import-cc-history.py" --source "$VAULT/01-raw/transcripts" --verbose
```
De importer slaat al bestaande raw-sessielogs over (target-bestand bestaat al),
dus dubbel draaien is veilig. Noteer welke nieuwe `raw-sessie-*.md` zijn geschreven.

## Stap 3: Compileer tot wiki
Voer de inhoud van `/wiki` uit over de zojuist geimporteerde raw-sessielogs
(zie `commands/wiki.md`): identificeer wiki-kandidaten, schrijf of werk artikelen
in `$VAULT/02-wiki/` bij, en draai de dagelijkse graphify-batch en semantische
tiling zoals `/wiki` voorschrijft. Verwerk alleen de raw-logs van vandaag of de
nieuw geimporteerde set; her-compileer geen oude artikelen.

## Stap 4: Markeer exact de snapshot als gedestilleerd
Alleen als stap 2 en 3 zonder fout zijn afgerond. Markeer ALLEEN de stems uit
`$BATCH` (stap 1), zodat een transcript dat tijdens stap 2-3 binnenkwam pending
blijft en bij de volgende run alsnog wordt aangeboden:
```bash
# shellcheck disable=SC2086  -- woordsplitsing op de stems is hier gewenst
[ -n "$BATCH" ] && python3 "$VAULT/.claude/scripts/distill-notify.py" --mark $BATCH < /dev/null
```
Dit APPENDt de verwerkte stems aan `$VAULT/01-raw/transcripts/.distilled`.

## Bevestiging
- Aantal transcripts in de snapshot (stap 1)
- Welke raw-sessielogs geimporteerd zijn (stap 2)
- Welke wiki-artikelen nieuw of bijgewerkt zijn (stap 3)
- Bevestiging dat de watermark is bijgewerkt met exact de snapshot (stap 4)

## Regels
- Idempotent: opnieuw draaien verwerkt alleen niet-gewatermerkte transcripts.
- Crasht stap 3 halverwege: laat de watermark ONGEMOEID (sla stap 4 over), zodat de
  rest bij de volgende run alsnog wordt opgepakt.
- Een transcript dat TIJDENS de run binnenkomt zit niet in `$BATCH` en blijft dus
  pending: het wordt bij de volgende `/destilleer` aangeboden. Geen stil verlies.
- Taal: volgt de prompt. Geen em dashes.
```

- [ ] **Step 2: Sanity-check the command file exists and is non-empty**

Run: `python -c "import pathlib,sys; p=pathlib.Path('commands/destilleer.md'); sys.exit(0 if p.is_file() and p.stat().st_size>500 else 1)"`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add commands/destilleer.md
git commit -m "feat(destilleer): /destilleer commando ketent import --source naar /wiki"
```

---

## Task 5: Deploy + documentatie + hookregistratie

**Files:**
- Modify: `setup.sh` (vault-`mkdir`, regel 103)
- Modify: `CONFIGURATION.md` (nieuwe sectie)
- Modify: `vault-structure/README.md`, `README.md`, `CHANGELOG.md`
- (Runtime, buiten repo) Modify: `~/.claude/settings.json`

**Interfaces:**
- Consumes: bestaande `setup.sh`-globs deployen `scripts/*.py` en `commands/*.md` automatisch, dus `archive-transcript.py`, `distill-notify.py` en `destilleer.md` komen vanzelf mee. Alleen de vault-map moet erbij.

- [ ] **Step 1: Add the transcripts dir to setup.sh**

In `setup.sh` regel 103, voeg `01-raw/transcripts` toe aan de brace-expansie:

```bash
mkdir -p "$VAULT"/{00-inbox,01-raw/sessies,01-raw/transcripts,02-wiki,03-projecten,04-templates,05-bronnen,06-claude,07-media,08-archive}
```

- [ ] **Step 2: Run the setup-deploy test to confirm scripts deploy**

Add a deploy assertion to `tests/test_setup_deploy.py` (in class `SetupDeployTest`):

```python
    def test_archive_and_distill_scripts_deployed(self):
        tmp, vault = self.run_setup()
        try:
            scripts = vault / ".claude" / "scripts"
            for name in ("archive-transcript.py", "distill-notify.py"):
                self.assertTrue((scripts / name).is_file(), f"{name} not deployed")
            self.assertTrue((vault / "01-raw" / "transcripts").is_dir(),
                            "transcripts dir not created")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
```

Run: `python -m pytest tests/test_setup_deploy.py -v`
Expected: PASS (existing tests + the new one). Skips with a clear reason if Git Bash is absent.

- [ ] **Step 3: Document the hook registration in CONFIGURATION.md**

Add after the "Index builder" section (around line 178):

````markdown
### Transcript-archief (`scripts/archive-transcript.py`, SessionEnd)

- **Effect:** kopieert het transcript van elke beeindigde sessie naar
  `$VAULT/01-raw/transcripts/<datum>-<project>-<sid8>.jsonl`. Deterministisch,
  fail-open, idempotent. Overleeft `cleanupPeriodDays` omdat de vault een
  backup-locatie is. Lege/`-p`-transcripts (< 200 bytes) worden overgeslagen.

### Destillatie-melding (`scripts/distill-notify.py`, SessionStart)

- **Effect:** telt transcripts in `01-raw/transcripts/` die niet in de
  `.distilled`-watermark staan en injecteert een melding "N wachten op
  destillatie". Geen LLM. Met `--mark <stem...>` (door `/destilleer`) worden
  exact de verwerkte stems aan de watermark toegevoegd.

### Hookregistratie (`~/.claude/settings.json`)

De scripts worden door `setup.sh` naar `$VAULT/.claude/scripts/` gedeployed. Voeg
daarna onderstaande entries TOE aan de bestaande `hooks`-arrays in je
`~/.claude/settings.json` (Windows `py -3`-launcher; pas `<VAULT>` aan).

> LET OP: dit is GEEN volledige settings.json. Plak het niet als geheel; dat
> wist je bestaande hooks, env (incl. `KENNISBANK_VAULT`) en permissions. Voeg
> alleen deze twee entries toe aan de respectieve arrays. De `SessionStart`-array
> bevat al `build-embed-index.py` (en evt. caveman) — zet `distill-notify.py`
> erNAAST, niet eroverheen.

```jsonc
// toe te voegen ENTRIES (geen complete settings.json):
"SessionEnd": [
  { "matcher": "", "hooks": [
    { "type": "command", "command": "py -3 \"<VAULT>/.claude/scripts/archive-transcript.py\"" }
  ]}
],
// onder de BESTAANDE SessionStart-array een extra hook-blok:
"SessionStart": [
  { "matcher": "", "hooks": [
    { "type": "command", "command": "py -3 \"<VAULT>/.claude/scripts/distill-notify.py\"" }
  ]}
]
```

Op macOS/Linux: vervang `py -3` door `python3`.
````

- [ ] **Step 4: Document the new dir + commando in vault-structure, README, CHANGELOG**

In `vault-structure/README.md`, onder `01-raw/`, voeg toe:
```
    transcripts/   Gearchiveerde CC-transcripts (.jsonl) via de SessionEnd-hook
```

In `README.md` commands-tabel (Engelstalig, conform de bestaande rijen), voeg een rij toe:
```
| `/destilleer` | none | Imports archived CC transcripts and compiles them into the wiki |
```

In `CHANGELOG.md` onder een nieuwe `## [Unreleased]`-sectie:
```
### Added
- **CC transcript-archief (`scripts/archive-transcript.py`, SessionEnd-hook).** Archiveert elk transcript naar `01-raw/transcripts/`, fail-open en idempotent. Overleeft `cleanupPeriodDays`.
- **`/destilleer`-commando + `scripts/distill-notify.py` (SessionStart).** Piggyback-destillatie: melding van openstaande transcripts plus een commando dat ze via `import-cc-history.py --source` naar `/wiki` ketent. Watermark in `.distilled`.
- **`import-cc-history.py --source <dir>`.** Importeert een platte transcript-archiefmap.
```

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest tests/ -q`
Expected: all pass (Git Bash-afhankelijke setup-test skipt netjes als bash ontbreekt).

- [ ] **Step 6: Register the hooks in the live settings.json (runtime, buiten repo)**

Gebruik de `update-config`-skill (of bewerk handmatig) om de `SessionEnd`- en
`SessionStart`-entries uit stap 3 toe te voegen aan `~/.claude/settings.json`.
Voeg de `SessionStart`-entry TOE aan de bestaande lijst (naast caveman-activate en
build-embed-index); overschrijf niets. Verifieer met:

```bash
py -3 - <<'PY'
import json, pathlib
d = json.loads((pathlib.Path.home()/".claude"/"settings.json").read_text(encoding="utf-8"))
ev = d.get("hooks", {})
print("SessionEnd:", [h["command"][-40:] for b in ev.get("SessionEnd", []) for h in b["hooks"]])
print("SessionStart:", [h["command"][-40:] for b in ev.get("SessionStart", []) for h in b["hooks"]])
PY
```
Expected: `SessionEnd` bevat `archive-transcript.py`; `SessionStart` bevat zowel
`build-embed-index.py` als `distill-notify.py`.

- [ ] **Step 7: Commit the repo changes**

```bash
git add setup.sh CONFIGURATION.md vault-structure/README.md README.md CHANGELOG.md tests/test_setup_deploy.py
git commit -m "feat(setup): deploy archief+destillatie-hooks, docs en transcripts-map"
```

---

## End-to-end verificatie (handmatig, na implementatie)

1. Start een echte CC-sessie in deze repo, doe iets, sluit af.
2. Controleer: `ls "$KENNISBANK_VAULT/01-raw/transcripts/"` toont een nieuw `.jsonl`.
3. Start een nieuwe sessie: de briefing meldt "1 wacht op destillatie".
4. Draai `/destilleer`: check een nieuw `raw-sessie-*.md` in `01-raw/sessies/` en een wiki-artikel/update in `02-wiki/`.
5. Start nog een sessie: geen pending-melding meer (watermark werkt).

## Self-Review (uitgevoerd door de plan-auteur, na adversariele verificatie-workflow)

- **Spec-dekking:** Component 1 → Task 1; Component 2 → Task 3; Component 3 → Task 4; `import --source` → Task 2; deploy/docs/hookregistratie → Task 5; watermark-ontwerp → Task 3 (`.distilled`); foutafhandeling fail-open → Tasks 1/3; testen → Tasks 1-3 + 5. Alle spec-secties gedekt.
- **Placeholder-scan:** geen TBD/TODO; alle code- en teststappen bevatten volledige inhoud.
- **Type-consistentie:** `archive()/dest_path()` (Task 1), `collect_jsonl()` (Task 2), `pending()/mark()` (Task 3) consistent gebruikt in tests en command. `--list-pending` + `--mark <stem...>` consistent tussen Task 3 (impl) en Task 4 (aanroep).

### Verwerkte verificatie-findings (4 lenzen, 0 blockers / 1 major / 9 minor)

- **[major] watermark-race (Task 3+4):** `mark_all` (glob-alles) vervangen door `mark(vault, stems)` die exact de in Stap 1 vastgelegde snapshot markeert. Een transcript dat tijdens `/wiki` binnenkomt blijft pending. Spec-bewoording (session_ids) aangelijnd op de implementatie (stems).
- **[minor] idempotentie cross-midnight (Task 1):** `archive()` dedupt nu op sid8-glob (`*-{sid8}.jsonl`) en hergebruikt de bestaande file, dus een refire over een dagovergang geeft geen duplicaat. Grow-test toegevoegd.
- **[minor] fail-open entry (Task 1+3):** `__main__` wrapt `main()` in try/except → exit 0, mirror van kb-retrieve.py.
- **[minor] cross-platform command (Task 4):** `py -3` → `python3` in destilleer.md (conform de andere commands); `py -3` blijft alleen in de hookregistratie met de macOS/Linux-noot.
- **[minor] env-leak in tests (Task 3):** notify-tests herstellen nu `KENNISBANK_VAULT`.
- **[minor] FAIL-reason (Task 2), settings.json-footgun (Task 5), README-taal (Task 5), project_slug-degradatie + partial-write-retry:** als notities/labels gedocumenteerd.
