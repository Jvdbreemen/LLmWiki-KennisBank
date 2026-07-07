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


def api_key_env_for(provider: str) -> str:
    env = os.environ.get("KB_LLM_API_KEY_ENV")
    if env and env.strip():
        return env.strip()
    cfg = _config()
    models = cfg.get("api_key_envs")
    if isinstance(models, dict) and models.get(provider):
        return str(models[provider])
    if cfg.get("api_key_env"):
        return str(cfg["api_key_env"])
    if provider == "openrouter":
        return "OPENROUTER_API_KEY"
    return ""


def _secrets_path() -> Path:
    raw = os.environ.get("KENNISBANK_SECRETS_FILE", "").strip()
    if raw:
        return Path(os.path.expanduser(os.path.expandvars(raw)))
    return Path.home() / ".config" / "kennisbank" / "secrets.json"


def _secret(name: str) -> str:
    if not name:
        return ""
    val = os.environ.get(name, "").strip()
    if val:
        return val
    try:
        data = json.loads(_secrets_path().read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get(name, "")).strip()


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
            key = _secret(api_key_env or "OPENROUTER_API_KEY")
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
    for prov in providers():
        if prov in CLOUD_PROVIDERS:
            sys.stderr.write(
                f"⚠ LLM-router: provider '{prov}' is CLOUD — content verlaat je machine.\n")
            sys.stderr.flush()  # nooit gebufferd achter de _call-output (privacy #4)
        out = _call(prov, model_for(prov), _endpoint(prov), api_key_env_for(prov),
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
