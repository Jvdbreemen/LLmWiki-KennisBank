"""Pluggable embedding provider for the KennisBank scripts.

Single source of truth for "turn text into a vector". The backend is
config-driven so the embedding MODEL can be swapped (local Ollama now, an API
provider such as Voyage or any OpenAI-compatible endpoint later) WITHOUT
touching the callers (semantic-tiling, the retrieval hook, the index builder).

Config resolution per setting (first match wins):
  1. environment variable
  2. kennisbank-embed.json in <vault>/.claude/
  3. built-in default

Settings:
  provider     KB_EMBED_PROVIDER      ollama | openai | voyage   (default ollama)
  model        KB_EMBED_MODEL         provider-specific default
  endpoint     KB_EMBED_ENDPOINT      base URL override (default per provider)
  api_key_env  KB_EMBED_API_KEY_ENV   NAME of the env var holding the API key.
                                      The key itself is never stored in config or
                                      in the repo; only the name of its env var.

Providers:
  ollama  Local Ollama HTTP API (POST {endpoint}/api/embeddings). Default
          endpoint http://localhost:11434, default model qwen3-embedding:8b.
          Honors the legacy OLLAMA_EMBED_MODEL var for backward-compat.
  openai  Any OpenAI-compatible /embeddings endpoint (OpenAI proper, a
          self-hosted gateway, or a third party that implements the same shape).
          POST {endpoint}/embeddings {"model":..,"input":text}. Default endpoint
          https://api.openai.com/v1, model text-embedding-3-small.
  voyage  Voyage AI (https://api.voyageai.com/v1). This is Anthropic's
          recommended embedding path: Anthropic/Claude has NO native embeddings
          API, so "embeddings via Claude" maps here. Default model voyage-3.

NOTE: OpenRouter's primary API is chat-completions; its embeddings support is
thin/unconfirmed. Use provider=openai with a verified gateway endpoint rather
than assuming OpenRouter serves /embeddings.

embed_id() returns "provider:model" so a vector computed with one model is never
compared against another. Different models live in different cosine spaces and
may differ in dimensionality, so cross-model cosine is silently wrong. Callers
MUST gate cache reuse on embed_id() equality (and dim as cheap insurance).

Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _frontmatter import split_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

_DEFAULTS = {
    "ollama": {"endpoint": "http://localhost:11434", "model": "qwen3-embedding:8b"},
    "openai": {"endpoint": "https://api.openai.com/v1", "model": "text-embedding-3-small"},
    "voyage": {"endpoint": "https://api.voyageai.com/v1", "model": "voyage-3"},
}

CACHE_FILE = vault_root() / ".claude" / "embeddings-cache.json"


def _config() -> dict:
    cfg_file = vault_root() / ".claude" / "kennisbank-embed.json"
    if cfg_file.exists():
        try:
            return json.loads(cfg_file.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}
    return {}


def _setting(name: str, env: str, file_cfg: dict, default: str = "") -> str:
    v = os.environ.get(env)
    if v is not None and v.strip():
        return v.strip()
    v = file_cfg.get(name)
    if isinstance(v, str) and v.strip():
        return v.strip()
    return default


def _resolve():
    fc = _config()
    prov = _setting("provider", "KB_EMBED_PROVIDER", fc, "ollama").lower()
    d = _DEFAULTS.get(prov, _DEFAULTS["ollama"])
    model = _setting("model", "KB_EMBED_MODEL", fc, "")
    if not model and prov == "ollama":
        model = os.environ.get("OLLAMA_EMBED_MODEL", "").strip() or d["model"]
    if not model:
        model = d["model"]
    endpoint = (_setting("endpoint", "KB_EMBED_ENDPOINT", fc, "") or d["endpoint"]).rstrip("/")
    api_key_env = _setting("api_key_env", "KB_EMBED_API_KEY_ENV", fc, "")
    return prov, model, endpoint, api_key_env


def provider() -> str:
    return _resolve()[0]


def embed_id() -> str:
    """Stable identity of the active backend for cache-keying: "provider:model"."""
    prov, model, _, _ = _resolve()
    return f"{prov}:{model}"


def cosine(a, b) -> float:
    """Cosine similarity, length-guarded. Mismatched lengths return 0.0 rather
    than silently scoring the overlap (the cross-model truncation trap)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _http_json(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    import urllib.request
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def embed(text: str, timeout: float = 30.0):
    """Return an embedding vector for text, or None on any failure (fail-soft)."""
    text = (text or "").strip()
    if not text:
        return None
    prov, model, endpoint, api_key_env = _resolve()
    try:
        if prov == "ollama":
            r = _http_json(
                f"{endpoint}/api/embeddings",
                {"model": model, "prompt": text, "keep_alive": "30m"},
                {"Content-Type": "application/json"},
                timeout,
            )
            return r.get("embedding") or (r.get("embeddings") or [None])[0]
        # API providers require a key, read from the named env var only.
        key = os.environ.get(api_key_env, "").strip() if api_key_env else ""
        if not key:
            return None
        if prov == "openai":
            r = _http_json(
                f"{endpoint}/embeddings",
                {"model": model, "input": text},
                {"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
                timeout,
            )
            return r["data"][0]["embedding"]
        if prov == "voyage":
            r = _http_json(
                f"{endpoint}/embeddings",
                {"model": model, "input": [text]},
                {"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
                timeout,
            )
            return r["data"][0]["embedding"]
    except Exception:
        return None
    return None


# --- model warm-up (kills cold-load latency on the hot path) -----------------
#
# The interactive retrieval hook must never block on a cold model load. A big
# local model (e.g. qwen3-embedding:8b, ~8GB) can take tens of seconds to load
# into VRAM after eviction/idle; the incremental index build at SessionStart
# does NOT load it when nothing changed, so the first prompt otherwise pays the
# full cold-load. These helpers let a caller fire a detached load so the NEXT
# prompt is hot, without ever waiting.

def _warm_marker() -> Path:
    return CACHE_FILE.parent / ".embed-warm.marker"


def warm(timeout: float = 120.0) -> bool:
    """Load/refresh the model with one throwaway embed. Blocks up to timeout.
    Returns True if a vector came back. Meant for detached/off-path use."""
    return embed("warm", timeout=timeout) is not None


def warm_async(min_interval: float = 60.0) -> None:
    """Fire-and-forget: load the embedding model in a DETACHED child so the hot
    path never waits on a cold load. Sentinel-guarded — skips if a warm was
    kicked within min_interval seconds, so a down Ollama can't cause a child
    pileup (one prompt per minute at worst). Silent and fail-open throughout.

    The child re-runs this module with --warm; it inherits the parent env so
    vault_root() (evaluated at import for CACHE_FILE) resolves. Callers on the
    hot path must ensure KENNISBANK_VAULT is set before invoking this."""
    try:
        import time as _time
        marker = _warm_marker()
        try:
            if marker.exists() and (_time.time() - marker.stat().st_mtime) < min_interval:
                return
        except Exception:
            pass
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("", encoding="utf-8")
        except Exception:
            pass
        import subprocess
        kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
            "env": os.environ.copy(),
        }
        if os.name == "nt":
            # DETACHED_PROCESS | CREATE_NO_WINDOW: outlive the hook, no console flash.
            kwargs["creationflags"] = 0x00000008 | 0x08000000
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "--warm"], **kwargs)
    except Exception:
        pass


# --- shared embedding cache (path -> {hash, id, dim, embedding}) -------------

def load_cache() -> dict:
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(CACHE_FILE)


def file_hash(path) -> str:
    return hashlib.md5(Path(path).read_bytes()).hexdigest()[:8]


def doc_text(path, cap: int = 4000) -> str:
    """Body text of a markdown note (frontmatter stripped), capped for embedding."""
    try:
        _, body = split_frontmatter(Path(path).read_text(encoding="utf-8"))
        return body.strip()[:cap]
    except Exception:
        return ""


def get_cached(path, cache: dict, recompute: bool = True):
    """Return the embedding for path. A changed file hash OR a different
    embed_id() is a cache miss; recompute unless recompute=False. Cross-model
    vectors are never reused (see embed_id)."""
    key = str(Path(path))
    eid = embed_id()
    h = file_hash(path)
    entry = cache.get(key)
    if entry and entry.get("hash") == h and entry.get("id") == eid and entry.get("embedding"):
        return entry["embedding"]
    if not recompute:
        return None
    text = doc_text(path)
    if not text:
        return None
    vec = embed(text)
    if vec:
        cache[key] = {"hash": h, "id": eid, "dim": len(vec), "embedding": vec}
    return vec


if __name__ == "__main__":
    # Detached warm entrypoint (see warm_async). Loads the model, then exits.
    # Never raises: this runs unattended and must not spew.
    if "--warm" in sys.argv:
        try:
            warm()
        except Exception:
            pass
