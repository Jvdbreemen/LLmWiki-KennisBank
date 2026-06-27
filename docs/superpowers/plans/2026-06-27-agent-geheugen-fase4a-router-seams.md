# Agent-geheugen — Fase 4a: Model-router + seams + render-hardening (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** De testbare bouwstenen voor de capture-sweep (fase 4b): een configureerbare lokaal-first model-router `_llm.py` (provider-keten, opt-in cloud), de `render()`-input-hardening (uitgesteld uit fase 1), en twee mockbare LLM-seams — `_judge.py` (oordeel) en `_extract.py` (kandidaat-extractie). Alles puur en unit-getest zonder echt model.

**Architecture:** `_llm.py` spiegelt het bewezen `_embeddings.py`-provider-patroon: config-gedreven, lokaal-default, fail-soft. Een **geordende provider-keten** (default `["ollama"]`) — `generate()` probeert providers op volgorde tot er één lukt; cloud-providers zijn opt-in (in de keten zetten = expliciete toestemming, #4) en loggen **luid** wanneer ze vuren. `_judge.py` en `_extract.py` zijn dunne lagen op `_llm.generate()` met een mockbare seam (tests monkeypatchen `_llm.generate`); fail-safe (judge twijfelt/faalt → `unverified`, extract faalt → `[]`).

**Tech Stack:** Python 3.10+ (stdlib: `urllib`, `subprocess`, `json`), `_embeddings`/`_memory` (bestaand), `unittest`.

## Global Constraints

- **Lokaal-first (#4):** default provider-keten = `["ollama"]`. Cloud (`openrouter`, `claude-cli`) alleen als de gebruiker ze expliciet in de keten zet. Een cloud-stap logt **luid** naar stderr ("⚠ LLM-fallback naar cloud-provider '<p>' — content verlaat je machine").
- **Geen automatische stille cloud-fallback:** keten faalt volledig → `generate()` geeft `None` → caller fail-safe (judge → `unverified`). Self-healing.
- **Mockbare seam:** `_judge`/`_extract` roepen `_llm.generate(...)` aan; tests monkeypatchen dat. **Geen test mag een echt model/netwerk vereisen.**
- **Fail-safe:** `judge()` → bij None/parse-fout/twijfel: `"unverified"` (nooit `"current"`). `extract()` → bij None/parse-fout: `[]`.
- **Config-resolutie** (eerste match wint): env → `<vault>/.claude/kennisbank-llm.json` → built-in default. Idem `_embeddings.py`.
- **Stdlib only** (geen nieuwe pip-dep; `claude-cli` shelt het bestaande `claude`-binary).
- **Decoupling #9:** `_embeddings.py`, `kb-retrieve.py`, `build-embed-index.py`, `_kbindex.py` ongemoeid. `_memory.py` wordt alleen uitgebreid met de render-hardening (geen gedragswijziging op geldige input).
- **Module-conventie:** underscore-naam, `os.environ.setdefault("KENNISBANK_VAULT", parents[2])`, `sys.path.insert`.

---

### Task 1: `_llm.py` — lokaal-first model-router

**Files:**
- Create: `scripts/_llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Produces:
  - `providers() -> list[str]` — de actieve keten (default `["ollama"]`).
  - `model_for(provider) -> str` — model voor een provider.
  - `is_local() -> bool` — True als de EERSTE provider lokaal is (`ollama`).
  - `generate(prompt, system="", timeout=120.0) -> str | None` — probeert de keten op volgorde; eerste niet-lege string wint; `None` als alles faalt. Cloud-stap → luide stderr-waarschuwing.
  - `_call(provider, model, endpoint, api_key_env, prompt, system, timeout) -> str | None` — één provider-aanroep.
  - `LOCAL_PROVIDERS = {"ollama"}`; `CLOUD_PROVIDERS = {"openrouter", "claude-cli"}`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_llm.py`:

```python
"""Tests voor scripts/_llm.py - de model-router. Geen echt model/netwerk:
we monkeypatchen _call (de per-provider aanroep). Vault naar temp.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _llm  # noqa: E402


class LlmRouterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-llm-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self._saved_env = {k: os.environ.get(k) for k in
                           ("KENNISBANK_VAULT", "KB_LLM_PROVIDERS", "KB_LLM_MODEL", "KB_LLM_ENDPOINT")}
        for k in ("KB_LLM_PROVIDERS", "KB_LLM_MODEL", "KB_LLM_ENDPOINT"):
            os.environ.pop(k, None)
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self._orig_call = _llm._call

    def tearDown(self):
        import shutil
        _llm._call = self._orig_call
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _cfg(self, obj):
        import json
        (self.vault / ".claude" / "kennisbank-llm.json").write_text(
            json.dumps(obj), encoding="utf-8")

    def test_default_chain_is_ollama_local(self):
        self.assertEqual(_llm.providers(), ["ollama"])
        self.assertTrue(_llm.is_local())

    def test_generate_uses_first_provider(self):
        calls = []
        _llm._call = lambda prov, *a, **k: (calls.append(prov) or "OK van " + prov)
        self.assertEqual(_llm.generate("hi"), "OK van ollama")
        self.assertEqual(calls, ["ollama"])

    def test_chain_fallback_to_next_on_none(self):
        self._cfg({"providers": ["ollama", "openrouter"], "models": {"openrouter": "x"}})
        def fake(prov, *a, **k):
            return None if prov == "ollama" else "cloud-antwoord"
        _llm._call = fake
        buf = io.StringIO()
        with redirect_stderr(buf):
            out = _llm.generate("hi")
        self.assertEqual(out, "cloud-antwoord")
        # cloud-stap moet LUID loggen
        self.assertIn("cloud", buf.getvalue().lower())
        self.assertIn("openrouter", buf.getvalue())

    def test_all_fail_returns_none(self):
        self._cfg({"providers": ["ollama", "openrouter"]})
        _llm._call = lambda *a, **k: None
        self.assertIsNone(_llm.generate("hi"))

    def test_is_local_false_when_cloud_first(self):
        self._cfg({"providers": ["openrouter", "ollama"]})
        self.assertFalse(_llm.is_local())

    def test_env_overrides_providers(self):
        os.environ["KB_LLM_PROVIDERS"] = "ollama, claude-cli"
        self.assertEqual(_llm.providers(), ["ollama", "claude-cli"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '_llm'`.

- [ ] **Step 3: Implement `scripts/_llm.py`**

Create `scripts/_llm.py`:

```python
#!/usr/bin/env python3
"""_llm.py - lokaal-first model-router voor generatie (judge/extractie).

Spiegelt _embeddings.py: config-gedreven, pluggable provider, fail-soft. Een
GEORDENDE provider-keten (default ["ollama"], lokaal). generate() probeert de
keten op volgorde tot er één een niet-lege string geeft. Cloud-providers
(openrouter, claude-cli) zijn OPT-IN: ze in de keten zetten = expliciete
toestemming (#4). Een cloud-stap logt LUID naar stderr — nooit stil.

Config (eerste match wint):
  1. env: KB_LLM_PROVIDERS (comma-lijst), KB_LLM_MODEL, KB_LLM_ENDPOINT, KB_LLM_API_KEY_ENV
  2. <vault>/.claude/kennisbank-llm.json: {"providers":[...], "model":"...", "models":{prov:model}, "endpoint":"..."}
  3. default: providers ["ollama"], model gemma4:latest, endpoint http://localhost:11434

Stdlib only. claude-cli shelt het bestaande `claude`-binary (gebruikt je CC-auth).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

LOCAL_PROVIDERS = {"ollama"}
CLOUD_PROVIDERS = {"openrouter", "claude-cli"}

_DEFAULTS = {
    "ollama": {"endpoint": "http://localhost:11434", "model": "gemma4:latest"},
    "openrouter": {"endpoint": "https://openrouter.ai/api/v1", "model": ""},
    "claude-cli": {"endpoint": "", "model": ""},
}


def _config() -> dict:
    f = vault_root() / ".claude" / "kennisbank-llm.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}
    return {}


def providers() -> list:
    env = os.environ.get("KB_LLM_PROVIDERS")
    if env and env.strip():
        return [p.strip() for p in env.split(",") if p.strip()]
    cfg = _config()
    chain = cfg.get("providers")
    if isinstance(chain, list) and chain:
        return [str(p).strip() for p in chain if str(p).strip()]
    return ["ollama"]


def model_for(provider: str) -> str:
    env = os.environ.get("KB_LLM_MODEL")
    if env and env.strip():
        return env.strip()
    cfg = _config()
    models = cfg.get("models")
    if isinstance(models, dict) and models.get(provider):
        return str(models[provider])
    if cfg.get("model"):
        return str(cfg["model"])
    return _DEFAULTS.get(provider, {}).get("model", "")


def _endpoint(provider: str) -> str:
    env = os.environ.get("KB_LLM_ENDPOINT")
    if env and env.strip():
        return env.strip().rstrip("/")
    cfg = _config()
    if cfg.get("endpoint"):
        return str(cfg["endpoint"]).rstrip("/")
    return _DEFAULTS.get(provider, {}).get("endpoint", "")


def is_local() -> bool:
    chain = providers()
    return bool(chain) and chain[0] in LOCAL_PROVIDERS


def _http_json(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    import urllib.request
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _call(provider, model, endpoint, api_key_env, prompt, system, timeout):
    """Eén provider-aanroep. Geeft de gegenereerde tekst of None (fail-soft)."""
    try:
        if provider == "ollama":
            full = (system + "\n\n" + prompt) if system else prompt
            r = _http_json(f"{endpoint}/api/generate",
                           {"model": model, "prompt": full, "stream": False,
                            "options": {"temperature": 0}},
                           {"Content-Type": "application/json"}, timeout)
            return (r.get("response") or "").strip() or None
        if provider == "openrouter":
            key = os.environ.get(api_key_env or "OPENROUTER_API_KEY", "").strip()
            if not key:
                return None
            msgs = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
            r = _http_json(f"{endpoint}/chat/completions",
                           {"model": model, "messages": msgs},
                           {"Content-Type": "application/json",
                            "Authorization": f"Bearer {key}"}, timeout)
            return (r["choices"][0]["message"]["content"] or "").strip() or None
        if provider == "claude-cli":
            full = (system + "\n\n" + prompt) if system else prompt
            p = subprocess.run(["claude", "-p", full], capture_output=True,
                               text=True, timeout=timeout)
            return (p.stdout or "").strip() or None
    except Exception:
        return None
    return None


def generate(prompt: str, system: str = "", timeout: float = 120.0):
    """Probeer de provider-keten op volgorde. Eerste niet-lege string wint.
    Cloud-stap logt LUID naar stderr. None als de hele keten faalt."""
    api_key_env = os.environ.get("KB_LLM_API_KEY_ENV", "")
    for prov in providers():
        if prov in CLOUD_PROVIDERS:
            sys.stderr.write(
                f"⚠ LLM-router: provider '{prov}' is CLOUD — content verlaat je machine.\n")
        out = _call(prov, model_for(prov), _endpoint(prov), api_key_env,
                    prompt, system, timeout)
        if out:
            return out
    return None


def _cli(argv) -> int:
    if argv and argv[0] == "current":
        print("providers:", providers())
        for p in providers():
            print(f"  {p}: model={model_for(p)!r} endpoint={_endpoint(p)!r}")
        print("is_local:", is_local())
        return 0
    if argv and argv[0] == "test":
        out = generate("Antwoord met exact het woord OK.")
        print("resultaat:", repr(out))
        return 0 if out else 1
    print("usage: _llm.py current|test", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_llm.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/_llm.py tests/test_llm.py
git commit -m "feat(memory): _llm.py lokaal-first model-router (provider-keten, opt-in cloud, luid)"
```

---

### Task 2: `render()` input-hardening in `_memory.py`

**Files:**
- Modify: `scripts/_memory.py`
- Test: `tests/test_memory.py` (toevoegen aan bestaande klasse)

**Interfaces:**
- Consumes: bestaande `render`.
- Produces: `render` is robuust tegen niet-vertrouwde input (LLM-gegenereerde titels/bodies in fase 4b). `_yaml_scalar(s) -> str` (sanitize + quote) en `_yaml_list` met string-guard. Geen gedragswijziging op bestaande geldige input (bestaande tests blijven groen).

- [ ] **Step 1: Write the failing test**

Voeg toe aan `class MemoryFormatTest` in `tests/test_memory.py`:

```python
    def test_render_sanitizes_quotes_and_newlines_in_title(self):
        from _frontmatter import parse_frontmatter
        md = _memory.render('Een "rare" titel\nmet newline', "body",
                            source_session='pad "met" quote', created="2026-06-27")
        # frontmatter moet pareerbaar blijven (geen kapotte YAML)
        fm, body = parse_frontmatter(md)
        self.assertEqual(fm.get("type"), "memory")
        self.assertNotIn("\n", fm.get("title", ""))   # newline weg
        self.assertIn("body", body)

    def test_render_tags_accepts_string(self):
        from _frontmatter import parse_frontmatter
        md = _memory.render("T", "b", tags="losse-string", created="2026-06-27")
        fm, _ = parse_frontmatter(md)
        self.assertEqual(fm.get("tags"), ["losse-string"])

    def test_render_superseded_by_accepts_string(self):
        # een enkele wikilink als string mag niet in characters uiteenvallen
        md = _memory.render("T", "b", superseded_by="[[ander]]", created="2026-06-27")
        self.assertIn("[[ander]]", md)
        self.assertNotIn("[[a]], [[n]]", md)  # niet per-char gesplitst
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_memory.py -k "sanitize or accepts_string" -v`
Expected: FAIL — `test_render_tags_accepts_string` faalt (`"losse-string"` wordt per-char gesplitst door `_yaml_list`), en de title-sanitize ontbreekt.

- [ ] **Step 3: Harden `render` in `_memory.py`**

Voeg helpers toe en gebruik ze in `render`. Vervang de bestaande `_yaml_list` en de title/source_session-regels:

```python
def _yaml_scalar(s) -> str:
    """Veilige double-quoted scalar voor de minimale frontmatter-parser.
    Sanitize i.p.v. escape (de parser kent geen escapes): embedded quotes ->
    enkele quote, newlines -> spatie."""
    s = str(s).replace('"', "'").replace("\n", " ").replace("\r", " ").strip()
    return f'"{s}"'


def _yaml_list(items) -> str:
    if isinstance(items, str):
        items = [items]
    safe = [str(i).replace("\n", " ").strip() for i in (items or [])]
    return "[" + ", ".join(safe) + "]"
```

En in `render`, vervang:
- `f'title: "{title}"'` → `f"title: {_yaml_scalar(title)}"`
- `f'source_session: "{source_session}"'` → `f"source_session: {_yaml_scalar(source_session)}"`

(De `superseded_by` en `tags` gebruiken al `_yaml_list`; die krijgt nu de string-guard gratis.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_memory.py -v`
Expected: PASS — de drie nieuwe tests + alle bestaande `_memory`-tests (geen regressie op geldige input).

- [ ] **Step 5: Commit**

```bash
git add scripts/_memory.py tests/test_memory.py
git commit -m "fix(memory): render() input-hardening (sanitize scalars, _yaml_list string-guard)"
```

---

### Task 3: `_judge.py` — onafhankelijke oordeel-seam

**Files:**
- Create: `scripts/_judge.py`
- Test: `tests/test_judge.py`

**Interfaces:**
- Consumes: `_llm.generate`.
- Produces:
  - `judge(candidate, context="") -> dict` met `{"verdict": "current"|"unverified", "reason": str}`. `candidate` = de kandidaat-memory-tekst. Roept `_llm.generate` met een "probeer af te keuren; bij twijfel afkeuren"-prompt. Parse de JSON-uitkomst; **fail-safe**: `None`/parse-fout/onbekende verdict → `{"verdict": "unverified", ...}`. Alleen een expliciet hoog-zeker "current" promoot.
  - `JUDGE_SYSTEM: str` — de systeemprompt (onafhankelijke, sceptische keurder).

- [ ] **Step 1: Write the failing test**

Create `tests/test_judge.py`:

```python
"""Tests voor scripts/_judge.py - de oordeel-seam. _llm.generate wordt
gemonkeypatcht; geen echt model."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import unittest
import _judge  # noqa: E402
import _llm  # noqa: E402


class JudgeTest(unittest.TestCase):
    def setUp(self):
        self._orig = _llm.generate

    def tearDown(self):
        _llm.generate = self._orig

    def test_high_confidence_current(self):
        _llm.generate = lambda *a, **k: '{"verdict": "current", "reason": "duidelijke lesson learned"}'
        out = _judge.judge("Bug X opgelost door Y.")
        self.assertEqual(out["verdict"], "current")

    def test_doubt_is_unverified(self):
        _llm.generate = lambda *a, **k: '{"verdict": "unverified", "reason": "vaag"}'
        self.assertEqual(_judge.judge("iets vaags")["verdict"], "unverified")

    def test_model_none_is_failsafe_unverified(self):
        _llm.generate = lambda *a, **k: None
        self.assertEqual(_judge.judge("x")["verdict"], "unverified")

    def test_unparseable_is_failsafe_unverified(self):
        _llm.generate = lambda *a, **k: "ik ben geen json"
        self.assertEqual(_judge.judge("x")["verdict"], "unverified")

    def test_unknown_verdict_is_failsafe(self):
        _llm.generate = lambda *a, **k: '{"verdict": "weet-niet"}'
        self.assertEqual(_judge.judge("x")["verdict"], "unverified")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_judge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '_judge'`.

- [ ] **Step 3: Implement `scripts/_judge.py`**

Create `scripts/_judge.py`:

```python
#!/usr/bin/env python3
"""_judge.py - onafhankelijke oordeel-seam voor de capture-sweep.

Beoordeelt of een kandidaat-memory de moeite waard is om als 'current' (direct
recallbaar) te bewaren, of dat-ie naar 'unverified' (quarantaine) moet. Draait
in de sweep met verse context, los van de producerende sessie -> onafhankelijk.

FAIL-SAFE: alles wat geen expliciet hoog-zeker 'current' is -> 'unverified'.
Een None/parse-fout/onbekend verdict promoot NOOIT. Dit beschermt #1 (geen
foute/stale recall) en #2 (geen ruis).

Dunne laag op _llm.generate(); tests monkeypatchen die seam.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _llm  # noqa: E402

JUDGE_SYSTEM = (
    "Je bent een sceptische, onafhankelijke keurder van kandidaat-geheugens voor een "
    "persoonlijke kennisbank. Keur streng. Promoot ALLEEN tot 'current' als dit een "
    "duidelijke, herbruikbare lesson learned, bug-fix, besluit of duurzaam feit is. "
    "Bij twijfel, ruis, smalltalk of vaagheid: 'unverified'. "
    "Antwoord UITSLUITEND met JSON: {\"verdict\": \"current\"|\"unverified\", \"reason\": \"<kort>\"}."
)


def judge(candidate: str, context: str = "") -> dict:
    prompt = (f"Context:\n{context}\n\n" if context else "") + \
             f"Kandidaat-geheugen:\n{candidate}\n\nOordeel (alleen JSON):"
    raw = _llm.generate(prompt, system=JUDGE_SYSTEM)
    if not raw:
        return {"verdict": "unverified", "reason": "geen model-respons (fail-safe)"}
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        obj = json.loads(raw[start:end + 1]) if start >= 0 and end > start else {}
    except Exception:
        return {"verdict": "unverified", "reason": "onparseerbaar (fail-safe)"}
    verdict = obj.get("verdict")
    if verdict == "current":
        return {"verdict": "current", "reason": str(obj.get("reason", ""))[:200]}
    return {"verdict": "unverified", "reason": str(obj.get("reason", ""))[:200] or "geen current (fail-safe)"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_judge.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/_judge.py tests/test_judge.py
git commit -m "feat(memory): _judge.py onafhankelijke oordeel-seam (fail-safe naar unverified)"
```

---

### Task 4: `_extract.py` — kandidaat-extractie-seam

**Files:**
- Create: `scripts/_extract.py`
- Test: `tests/test_extract.py`

**Interfaces:**
- Consumes: `_llm.generate`.
- Produces:
  - `extract_candidates(transcript_text, max_n=8) -> list[dict]` met per kandidaat `{"title": str, "body": str}`. Roept `_llm.generate` met een extractie-prompt (lessons learned / bugs / besluiten / duurzame feiten). Parse JSON-lijst; **fail-safe**: `None`/parse-fout → `[]`. Begrenst op `max_n`. Lege/te-korte bodies worden gefilterd.
  - `EXTRACT_SYSTEM: str`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_extract.py`:

```python
"""Tests voor scripts/_extract.py - de extractie-seam. _llm.generate gemockt."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import unittest
import _extract  # noqa: E402
import _llm  # noqa: E402


class ExtractTest(unittest.TestCase):
    def setUp(self):
        self._orig = _llm.generate

    def tearDown(self):
        _llm.generate = self._orig

    def test_extracts_candidates(self):
        _llm.generate = lambda *a, **k: (
            '[{"title": "Bug in auth", "body": "Token-expiry gebruikte < i.p.v. <="},'
            ' {"title": "Besluit DB", "body": "Sqlite gekozen om lokaliteit"}]')
        out = _extract.extract_candidates("lange transcript tekst ...")
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["title"], "Bug in auth")
        self.assertIn("body", out[1])

    def test_none_is_empty(self):
        _llm.generate = lambda *a, **k: None
        self.assertEqual(_extract.extract_candidates("x"), [])

    def test_unparseable_is_empty(self):
        _llm.generate = lambda *a, **k: "geen json"
        self.assertEqual(_extract.extract_candidates("x"), [])

    def test_filters_empty_bodies_and_caps(self):
        items = ",".join('{"title": "T%d", "body": "voldoende lange inhoud %d"}' % (i, i)
                         for i in range(20))
        _llm.generate = lambda *a, **k: "[" + items + ',{"title":"leeg","body":""}]'
        out = _extract.extract_candidates("x", max_n=5)
        self.assertLessEqual(len(out), 5)
        self.assertTrue(all(c["body"].strip() for c in out))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_extract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '_extract'`.

- [ ] **Step 3: Implement `scripts/_extract.py`**

Create `scripts/_extract.py`:

```python
#!/usr/bin/env python3
"""_extract.py - kandidaat-extractie-seam voor de capture-sweep.

Haalt uit een transcript de herbruikbare kennis: lessons learned, bug-fixes,
besluiten, duurzame feiten. Geeft een lijst kandidaat-memories; de judge (_judge)
beslist daarna current vs unverified.

FAIL-SAFE: None/parse-fout -> [] (liever niets dan ruis). Dunne laag op
_llm.generate(); tests monkeypatchen die seam.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _llm  # noqa: E402

EXTRACT_SYSTEM = (
    "Je extraheert herbruikbare kennis uit een werk-transcript voor een persoonlijke "
    "kennisbank. Vang alleen: lessons learned, bug-fixes (oorzaak+oplossing), genomen "
    "besluiten, en duurzame feiten. NEGEER smalltalk, tussenstappen en vluchtige status. "
    "Elke memory is atomair en zelf-verklarend. Antwoord UITSLUITEND met een JSON-lijst: "
    "[{\"title\": \"<kort>\", \"body\": \"<2-4 zinnen>\"}]. Leeg = []."
)


def extract_candidates(transcript_text: str, max_n: int = 8) -> list:
    if not (transcript_text or "").strip():
        return []
    raw = _llm.generate(f"Transcript:\n{transcript_text}\n\nKandidaten (alleen JSON-lijst):",
                        system=EXTRACT_SYSTEM)
    if not raw:
        return []
    try:
        start = raw.find("[")
        end = raw.rfind("]")
        arr = json.loads(raw[start:end + 1]) if start >= 0 and end > start else []
    except Exception:
        return []
    out = []
    for item in arr if isinstance(arr, list) else []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        body = str(item.get("body", "")).strip()
        if title and body:
            out.append({"title": title, "body": body})
        if len(out) >= max_n:
            break
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_extract.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `python3 -m pytest tests/ -q`
Expected: alle tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/_extract.py tests/test_extract.py
git commit -m "feat(memory): _extract.py kandidaat-extractie-seam (fail-safe naar lege lijst)"
```

---

## Self-Review

**Spec coverage (fase 4a):**
- Lokaal-first model-router, provider-keten, opt-in cloud, luid bij cloud → Task 1. ✓
- `is_local()`, env/file/default config-resolutie → Task 1. ✓
- Geen automatische stille cloud-fallback (keten faalt → None → caller fail-safe) → Task 1 + Task 3. ✓
- render() input-hardening (sanitize scalars, _yaml_list string-guard) → Task 2. ✓
- judge-seam fail-safe naar unverified → Task 3. ✓
- extract-seam fail-safe naar [] → Task 4. ✓
- Mockbaar zonder echt model: alle judge/extract-tests monkeypatchen `_llm.generate`; router-tests monkeypatchen `_call`. ✓
- Buiten 4a (→ 4b): sweep-orkestratie, detached launcher, lockfile, heartbeat, /sessielog, sweep→index-ordening, doctor no-cloud-melding.

**Placeholder scan:** geen TBD/TODO; alle code + testcode volledig.

**Type consistency:** `_llm.generate(prompt, system="", timeout)` aangeroepen door `_judge`/`_extract` met dezelfde signatuur; `judge() -> {"verdict","reason"}` en `extract_candidates() -> [{"title","body"}]` consistent; `_call(provider, model, endpoint, api_key_env, prompt, system, timeout)` signatuur identiek in implementatie en de test-monkeypatch (de test gebruikt `*a, **k`, dus vorm-onafhankelijk).

**Geverifieerd vóór uitvoering:** Ollama `/api/generate` werkt lokaal (gemma4 ~35s cold, phi ~10s); generatie-modellen aanwezig. De router-default `gemma4:latest` is een aanwezig model. `_embeddings.py` is gelezen als template voor het provider-patroon (config-resolutie, `_http_json`).

**Aandachtspunt uitvoerder:** Task 1 — de tests monkeypatchen `_llm._call` (niet het netwerk), dus geen Ollama nodig; bevestig dat `generate()` `_call` per provider aanroept en de cloud-waarschuwing VÓÓR de call schrijft. Task 2 — bevestig dat de bestaande `_memory`-tests groen blijven (geldige input ongewijzigd; alleen embedded quotes/newlines/strings worden gesanitized). Task 3/4 — de JSON-parse pakt de eerste `{...}`/`[...]` uit een mogelijk pratende model-respons (robuust tegen preambles).
