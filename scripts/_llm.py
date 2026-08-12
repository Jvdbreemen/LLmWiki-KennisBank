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
  3. default: providers ["ollama"], model qwen3.5:4b, endpoint http://localhost:11434

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

#: The local judge/extraction model. It shares one GPU with the embedding model,
#: which is the hot path: retrieval has a 2 s budget and a cold load costs 30-60 s.
#: Ollama evicts the smaller model when the next one does not fit, so the judge is
#: pinned to a size that COEXISTS. Measured on an RTX 3080 Laptop (16 GB), both
#: models resident: qwen3-embedding:4b @ ctx 2048 = 4.06 GB, qwen3.5:4b @ ctx 4096
#: = 3.13 GB, together 7.19 GB. gemma4:12b costs 8.06 GB and evicted the embedder,
#: which is what turned retrieval off for whole sessions (TASK-139).
#: Every surface that writes KB_LLM_MODEL repeats this string; keep them in step.
#: tests/test_llm_model_default.py is the guard that they are.
OLLAMA_DEFAULT_MODEL = "qwen3.5:4b"

_DEFAULTS = {
    "ollama": {"endpoint": "http://localhost:11434", "model": OLLAMA_DEFAULT_MODEL},
    "openrouter": {"endpoint": "https://openrouter.ai/api/v1", "model": ""},
    "claude-cli": {"endpoint": "", "model": ""},
}

#: Ollama sizes a model from its context window, and without an explicit value it
#: uses the model's own default -- 16384 for qwen3.5:4b, measured at 3.6 GB of
#: VRAM against 3.13 GB at 4096. The judge never needs that: memory-sweep chunks
#: transcripts at 6000 characters (~1500 tokens) before calling extract, so the
#: worst case is roughly 1500 in + system prompt + a JSON answer, about 2700
#: tokens. 4096 covers it with room to spare.
#: Too low would be worse than wasteful: the prompt is truncated silently and the
#: judge answers about a transcript it only half saw. Raise this before raising
#: the chunk size in _sweeputil.chunk().
OLLAMA_NUM_CTX = int(os.environ.get("KB_LLM_NUM_CTX", "").strip() or 4096)

#: Reasoning models answer AFTER thinking, and the thinking spends the same
#: num_ctx budget as the answer. Measured on qwen3.5:4b with the reconcile
#: prompt at num_ctx 4096: 2106-3885 tokens of thinking, 30-56 s per call, and
#: one call in three returned done_reason="length" with an EMPTY response --
#: Ollama had put the reasoning in a separate `thinking` field and never reached
#: the answer. Every seam here is fail-safe (extract -> [], judge ->
#: unverified, reconcile -> ADD), so that silence looks exactly like a model
#: that considered the input and shrugged. With think=false the same three
#: prompts took 1.6-1.7 s, spent 39-48 tokens, and all three returned valid
#: JSON.
#: Sent unconditionally: a non-thinking model accepts the flag without
#: complaint (verified against gemma4:12b -- valid JSON, no HTTP error).
#: Set KB_LLM_THINK=1 to hand the budget back to the model's reasoning; only
#: worth it with a num_ctx that leaves room for an answer afterwards.
OLLAMA_THINK = os.environ.get("KB_LLM_THINK", "").strip() in ("1", "true", "yes")


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
                            "think": OLLAMA_THINK,
                            "options": {"temperature": 0,
                                        "num_ctx": OLLAMA_NUM_CTX}},
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
