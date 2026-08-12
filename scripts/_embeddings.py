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
          endpoint http://localhost:11434, default model qwen3-embedding:4b.
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
    "ollama": {"endpoint": "http://localhost:11434", "model": "qwen3-embedding:4b"},
    "openai": {"endpoint": "https://api.openai.com/v1", "model": "text-embedding-3-small"},
    "voyage": {"endpoint": "https://api.voyageai.com/v1", "model": "voyage-3"},
}

CACHE_FILE = vault_root() / ".claude" / "embeddings-cache.json"

#: Ollama allocates its KV cache from the context size, not from the document
#: length, so an embedding model loads far larger than its weights. Measured on
#: qwen3-embedding:4b (RTX 3080, 16 GB): 16384 ctx costs 6.24 GB of VRAM, 2048
#: costs 4.06 GB. The vault's longest embedded document is ~1000 tokens
#: (doc_text caps it), so 2048 leaves room to spare and the vectors are
#: unchanged -- cosine between a 16384-ctx and a 2048-ctx embedding of the same
#: text measures 1.000000 for both a short query and a full-length document.
#: The 2.18 GB that frees is what lets a judge model stay resident beside the
#: embedding model instead of evicting it.
#: Raise this if documents ever grow past it: truncation WOULD change vectors
#: and silently invalidate the index.
OLLAMA_NUM_CTX = int(os.environ.get("KB_EMBED_NUM_CTX", "").strip() or 2048)

#: Never unload on a timer. A cold load takes 30-60 s while the retrieval hook
#: has a 2 s budget, so an idle gap turns retrieval off without saying so.
#: This does not protect against eviction by another model -- only fitting in
#: VRAM does that (see docs/research on the model combination).
OLLAMA_KEEP_ALIVE = os.environ.get("KB_EMBED_KEEP_ALIVE", "").strip() or -1


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
    """Stable identity of the active backend for cache-keying.

    Format: "provider:model", plus "+<doc_prefix>" when a document prefix is
    configured.

    The document prefix belongs in the identity: the same text under a
    different prefix yields a different vector, so reusing a cached vector
    across a prefix change is exactly as wrong as reusing it across a model
    change."""
    prov, model, _, _ = _resolve()
    dp = _prefix("doc")
    return f"{prov}:{model}" + (f"+{dp}" if dp else "")


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


#: Providers waarvan de naam een belofte is: draait lokaal, dus het endpoint
#: hoort loopback te zijn. "ollama" met een extern endpoint is geen configuratie
#: maar een lek.
LOCAL_ONLY_PROVIDERS = ("ollama",)


def is_local_endpoint(ep: str) -> bool:
    """True als ep naar loopback wijst.

    Strikte hostname-parsing plus ipaddress.is_loopback, zodat een subdomein
    dat op "localhost" lijkt of een loopback-adres in de query-string niet
    doorglipt. test_hostname_spoofs_do_not_pass_as_local bewaakt die gevallen
    met de letterlijke vormen; hier staan ze bewust niet, omdat de no-cloud-scan
    op broncode kijkt en een voorbeeld-URL in een docstring niet van een echte
    te onderscheiden is.
    """
    import ipaddress
    import urllib.parse
    try:
        hostname = urllib.parse.urlparse(ep).hostname or ""
    except Exception:
        return False
    if hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def endpoint_allowed(prov: str, endpoint: str) -> bool:
    """Poort tussen de config en het netwerk. Weigert luid i.p.v. stil te lekken.

    Waarom dit hier staat en niet in een test: het endpoint komt uit
    kennisbank-embed.json, en de ollama-tak van embed() draait VOOR de
    API-key-check. Eén schrijfactie in dat bestand -- iets wat een agent met
    Write kan doen op instructie uit opgehaalde kennis -- stuurde daarmee elke
    prompt en, bij de volgende indexbouw, de hele vault naar een willekeurige
    host. Zonder sleutel en zonder waarschuwing.

    KB_EMBED_ALLOW_REMOTE is de expliciete ontsnapping voor wie een ollama op
    een andere machine draait; dat is een bewuste keuze, geen stille.
    """
    if prov in LOCAL_ONLY_PROVIDERS and not is_local_endpoint(endpoint):
        if os.environ.get("KB_EMBED_ALLOW_REMOTE", "").strip():
            sys.stderr.write(
                f"KennisBank: embed-provider '{prov}' wijst naar {endpoint} "
                f"(niet-lokaal), toegestaan via KB_EMBED_ALLOW_REMOTE.\n")
            sys.stderr.flush()
            return True
        sys.stderr.write(
            f"KennisBank: embed-provider '{prov}' hoort lokaal te zijn maar het "
            f"endpoint is {endpoint!r} -- GEWEIGERD, er is niets verstuurd. "
            f"Zet KB_EMBED_ALLOW_REMOTE=1 als dit bewust is.\n")
        sys.stderr.flush()
        return False
    if prov not in LOCAL_ONLY_PROVIDERS:
        sys.stderr.write(
            f"KennisBank: embed-provider '{prov}' is CLOUD -- tekst verlaat je "
            f"machine.\n")
        sys.stderr.flush()
    return True


def _prefix(kind: str) -> str:
    """Model-specific instruction prefix for the query or the document side.

    Not cosmetic: e5-instruct is TRAINED with "Instruct: ...\\nQuery: " on the
    query side and passage-style markers on the document side. Embed without
    them and you measure a different model than the one you meant to measure.
    Qwen3 loses 1-5% without a query prefix; bge-m3 and gte want none at all.
    The default is empty, so behaviour is unchanged when nothing is configured.

    Config: query_prefix / doc_prefix in kennisbank-embed.json, or the env vars
    KB_EMBED_QUERY_PREFIX / KB_EMBED_DOC_PREFIX.

    Deliberately NOT routed through _setting(): that strips the value, and the
    trailing space of "query: " is part of the prefix. Stripping it yields
    "query:question", a different tokenisation than the model was trained on.
    """
    name, env = {"query": ("query_prefix", "KB_EMBED_QUERY_PREFIX"),
                 "doc": ("doc_prefix", "KB_EMBED_DOC_PREFIX")}.get(kind, ("", ""))
    if not name:
        return ""
    v = os.environ.get(env)
    if v is not None:
        # An explicitly empty value disables the prefix. Treating "" as unset
        # would make KB_EMBED_QUERY_PREFIX= fall through to the config, so a
        # configured prefix could not be switched off for one run -- and the
        # embed_id() suffix would silently keep tracking the config value.
        return v
    v = _config().get(name)
    return v if isinstance(v, str) else ""


def embed(text: str, timeout: float = 30.0, kind: str = ""):
    """Return an embedding vector for text, or None on any failure (fail-soft).

    ``kind`` is "query", "doc" or empty. It selects which instruction prefix is
    placed before the text (see _prefix); empty means no prefix, which is the
    historical behaviour."""
    text = (text or "").strip()
    if not text:
        return None
    pre = _prefix(kind) if kind else ""
    if pre:
        text = pre.replace("\\n", "\n") + text
    prov, model, endpoint, api_key_env = _resolve()
    if not endpoint_allowed(prov, endpoint):
        return None
    try:
        if prov == "ollama":
            r = _http_json(
                f"{endpoint}/api/embeddings",
                {"model": model, "prompt": text,
                 "keep_alive": OLLAMA_KEEP_ALIVE,
                 "options": {"num_ctx": OLLAMA_NUM_CTX}},
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
# local model (e.g. qwen3-embedding:4b, ~6GB resident) can take seconds to load
# into VRAM after eviction/idle; the incremental index build at SessionStart
# does NOT load it when nothing changed, so the first prompt otherwise pays the
# full cold-load. These helpers let a caller fire a detached load so the NEXT
# prompt is hot, without ever waiting.

def _warm_marker() -> Path:
    return CACHE_FILE.parent / ".embed-warm.marker"


def _pid_alive(pid: int) -> bool:
    """Check a process without sending it a signal (including on Windows)."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def warm_in_progress(max_age: float = 60.0) -> bool:
    """Return whether the detached warm-up child is still alive.

    Older markers were empty files, so they are treated as an unknown/stale
    attempt rather than as proof that a process is alive. The marker is only a
    rate-limit record; it must not make a user-facing hook claim that work is
    running when the child already exited.

    The window is symmetric on purpose. On Windows time.time() reads a clock with
    a 15.625 ms resolution while the filesystem stamps mtime from a finer one, so
    a marker written moments ago can measure as slightly in the future (586 of
    5000 samples); rejecting that as "not running" spawned a second warm child
    for no reason (TASK-140).
    """
    try:
        import time as _time
        marker = _warm_marker()
        age = _time.time() - marker.stat().st_mtime
        if abs(age) >= max_age:
            return False
        data = json.loads(marker.read_text(encoding="utf-8"))
        pid = data.get("pid") if isinstance(data, dict) else None
        if not isinstance(pid, int) or pid <= 0:
            return False
        return _pid_alive(pid)
    except Exception:
        return False


def is_resident(timeout: float = 0.5):
    """Whether the configured model is loaded RIGHT NOW: True, False, or None.

    Reads Ollama's process table (GET /api/ps). That is a lookup, not a load --
    unlike a probe embed, which would pay the very 30-60 s cold load a caller
    asks this question to avoid. None means "cannot tell" (another provider, a
    remote endpoint, Ollama down, a malformed answer); a caller that reports
    this to a user must stay silent on None instead of claiming a cold model.

    The timeout is deliberately below a second: this is only ever worth asking
    on a path that must not block, so an unresponsive Ollama reads as unknown."""
    prov, model, endpoint, _key = _resolve()
    if prov != "ollama" or not model or not endpoint_allowed(prov, endpoint):
        return None
    try:
        import urllib.request
        req = urllib.request.Request(f"{endpoint}/api/ps", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    entries = data.get("models") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return None
    loaded = set()
    for e in entries:
        if not isinstance(e, dict):
            continue
        for key in ("name", "model"):
            v = e.get(key)
            if isinstance(v, str) and v:
                loaded.add(v)
                # Ollama reports "qwen3.5:4b" for a pull of "qwen3.5"; accept
                # both spellings so a config without a tag still matches.
                if v.endswith(":latest"):
                    loaded.add(v[: -len(":latest")])
    return model in loaded or f"{model}:latest" in loaded


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
        proc = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--warm"], **kwargs)
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                json.dumps({"pid": proc.pid, "started_at": _time.time()}) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass
    except Exception:
        pass


# --- shared embedding cache (path -> {hash, id, dim, embedding}) -------------

def load_cache() -> dict:
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cache(cache: dict) -> None:
    """Atomisch wegschrijven via een procesuniek tijdelijk bestand.

    SessionStart start meerdere indexbouwers die alledrie kunnen schrijven. Met
    een gedeeld tmp-pad schreven twee processen door elkaar heen en won de
    laatste -- een lost update. Bewust GEEN merge van de twee caches: een merge
    kan geen verwijdering uitdrukken en zou de prune-stap in build-embed-index
    permanent tot een no-op maken. Aanroepers schrijven alleen als er
    daadwerkelijk iets is toegevoegd of gesnoeid.
    """
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_FILE.with_name(f"{CACHE_FILE.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, CACHE_FILE)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


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
    vec = embed(text, kind="doc")
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
