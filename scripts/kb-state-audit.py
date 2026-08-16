#!/usr/bin/env python3
"""kb-state-audit.py - which memories contradict the configuration?

Deterministic, read-only, no LLM. Compares the claims in the memory layer
against an AUTHORITY: the configuration files and the constants in these
scripts. That is the difference from a second opinion -- there is a source that
is right by definition about what is running now.

Why it exists: the `second-brain-audit` skill ships a deterministic scanner,
and on this vault it found ZERO contradictions while four were demonstrably
present. It only compares monetary values, and this vault holds none. Its own
guidance says exactly that: "A zero is not a clean bill of health". This audit
does the same trick for the value types this vault DOES carry -- model tags,
thresholds, versions, paths, flags -- and reports just as loudly where it was
blind.

Four piles, and the last one is the point:

    CONTRADICTED  the memory says X, the authority says Y
    UNSUPPORTED   a value that appears in no authority at all
    CONFIRMED     the memory agrees with the authority
    COVERAGE      current memories with no checkable value -- here the audit
                  was blind, and that is not an approval

Plus a fifth that comes from TASK-146: memories that carry a checkable value
but count as an `event`. Those are never replaced, so for exactly that set
self-correction is switched off. The safe default is allowed to have visible
costs, not silent ones.

Only `status: current`, because that is exactly the set the recall hook can
inject. In this vault there is no harmless archive: whatever is current is
always-loaded.

Usage: python3 kb-state-audit.py [--json] [--fail-on-contradiction] [--limit N]
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _memory  # noqa: E402
import _settings  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402
from _progress import Progress  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

#: Model names come in two shapes. Ollama uses `family:tag`
#: (qwen3-embedding:4b); cloud models carry their version in the name itself
#: (claude-opus-4-8, text-embedding-3-small). Both have to be recognisable, or
#: precisely the stale claim falls outside the picture.
_OLLAMA_TAG = re.compile(r"\b([a-z][a-z0-9.]*(?:-[a-z0-9.]+)*):([a-z0-9][a-z0-9._-]*)\b")

#: Cloud models are recognised from a FIXED family list, not from a vendor
#: prefix. Measured on the live vault: a prefix rule read `Claude-sessiehistorie`
#: and `Claude-cli` as models, and the first of those is an ordinary Dutch word
#: with a hyphen in front of it. A list is duller and correct.
_VENDOR_FAMILIES = (
    "claude-opus", "claude-sonnet", "claude-haiku", "claude-fable",
    "gpt", "gemini", "llama", "mistral", "mixtral", "phi", "deepseek",
    "nomic-embed-text", "text-embedding", "voyage", "mxbai-embed",
)
_VENDOR_MODEL = re.compile(
    r"\b((?:" + "|".join(re.escape(f) for f in _VENDOR_FAMILIES) + r")"
    r"(?:-[a-z0-9.]+)*)\b", re.IGNORECASE)


def _clean_config(obj):
    """Only the ACTIVE keys. `_switching` and every `_`-prefixed key are
    examples and commentary -- they name OTHER models (gemma4:12b,
    text-embedding-3-small) and are therefore precisely NOT the authority.
    Counting them would turn every stale claim into a confirmed one."""
    if not isinstance(obj, dict):
        return {}
    return {k: v for k, v in obj.items() if not k.startswith("_")}


def _read_json(path: Path) -> dict:
    try:
        return _clean_config(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return {}


def code_constants() -> dict:
    """Constants from the scripts themselves. Also an authority: what the code
    does is what happens, regardless of what a memory claims about it.
    Fail-soft per module, because a deploy can be missing one."""
    out = {}
    try:
        import _reconcile
        out["RECONCILE_THRESHOLD"] = _reconcile.RECONCILE_THRESHOLD
        out["TOP_K"] = _reconcile.TOP_K
    except Exception:
        pass
    try:
        import importlib.util
        here = Path(__file__).resolve().parent
        spec = importlib.util.spec_from_file_location(
            "_tiling_probe", here / "semantic-tiling.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out["TILING_THRESHOLD_ERROR"] = mod.THRESHOLD_ERROR
        out["TILING_THRESHOLD_REVIEW"] = mod.THRESHOLD_REVIEW
    except Exception:
        pass
    return out


def authorities() -> dict:
    """The authority, as {model family -> tag} and {key -> value}."""
    root = vault_root()
    embed = _read_json(root / ".claude" / "kennisbank-embed.json")
    llm = _read_json(root / ".claude" / "kennisbank-llm.json")

    models = {}
    for cfg in (embed, llm):
        tag = str(cfg.get("model", "")).strip()
        if not tag:
            continue
        family = tag.split(":")[0] if ":" in tag else tag
        models[family.lower()] = tag

    values = {}
    for key in ("retrieve_top_n", "retrieve_threshold"):
        if key in embed:
            values[key] = embed[key]
    # `endpoint` is DELIBERATELY absent. It is an ordinary English word, and
    # this vault is full of memories about firmware REST endpoints. Measured:
    # eight of twelve "contradictions" were sentences of that kind, claiming
    # things like "endpoint=2" against "http://localhost:11434". A key that is
    # also a word is not a key. See _looks_like_key below.
    #
    # The toggles: the LIVE value via _settings.get, not the default in the
    # code. A memory claiming that archiving is on is right or wrong on the
    # basis of what kennisbank-settings.json says, not of what the source ships
    # as an initial value.
    for key in getattr(_settings, "DEFAULTS", {}):
        try:
            values[key] = _settings.get(key)
        except Exception:
            pass
    values.update(code_constants())
    return {"models": models, "values": values}


def model_tokens(text: str, known_families=()) -> list:
    """Every model name in the text, as (family, full_tag)."""
    out = []
    known = set(known_families or ())
    for m in _OLLAMA_TAG.finditer(text):
        family, tag = m.group(1), m.group(2)
        # `family:tag` also matches `adr-kit:adr`, `file:line`, `f1:ab` and
        # `_kbindex.py:41`. Measured on the live vault, that shape produced
        # more false models than real ones. Only families a configuration file
        # actually pins count; the rest is simply not a model claim this audit
        # can adjudicate, and falls under COVERAGE.
        if family.lower() not in known:
            continue
        out.append((family.lower(), f"{family}:{tag}"))
    for m in _VENDOR_MODEL.finditer(text):
        name = m.group(1)
        # Family = the name without its version tail, so that claude-opus-4-8
        # and claude-opus-5 are the same family.
        family = re.sub(r"-[\d.]+([-.][\d.]+)*$", "", name).lower()
        out.append((family, name))
    # One row per family per memory. "Gemini" and "Gemini-keys" in the same
    # text are one claim about one family; two rows read as two findings and
    # inflate every count.
    seen, unique = set(), []
    for family, name in out:
        if family in seen:
            continue
        seen.add(family)
        unique.append((family, name))
    return unique


#: A value just after a key name. Wide enough for "the threshold
#: retrieve_threshold is 0.6" and tight enough not to swallow the document.
_VALUE_NEAR = r"[^\n]{0,40}?(-?\d+(?:\.\d+)?|true|false|waar|onwaar)\b"


def _looks_like_key(key: str) -> bool:
    """Only keys that cannot also be an ordinary word.

    The same boundary _memory.looks_like_config uses: an underscore, a dot, or
    ALL_CAPS. `retrieve_top_n` and `RECONCILE_THRESHOLD` survive; `endpoint`
    and `model` do not, which is the whole point -- those words appear in
    dozens of memories about something else entirely.
    """
    k = str(key)
    return ("_" in k) or ("." in k) or (k.isupper() and len(k) > 2)


def value_claims(text: str, keys) -> list:
    """(key, claimed_value) for every authority key present in the text with a
    value behind it."""
    out = []
    for key in keys:
        if not _looks_like_key(key):
            continue
        pattern = re.compile(r"\b" + re.escape(str(key)) + _VALUE_NEAR, re.IGNORECASE)
        m = pattern.search(text)
        if m:
            out.append((key, m.group(1)))
    return out


def _same_value(claim: str, truth) -> bool:
    """Equal after normalisation: 3 == 3.0, 'true' == True."""
    c = str(claim).strip().lower()
    t = str(truth).strip().lower()
    if c == t:
        return True
    if t in ("true", "false") or isinstance(truth, bool):
        return c in (("true", "waar", "aan") if str(truth).lower() == "true"
                     else ("false", "onwaar", "uit"))
    try:
        return abs(float(c) - float(t)) < 1e-9
    except Exception:
        return False


def audit(limit=None) -> dict:
    authority = authorities()
    mdir = vault_root() / "09-memory"
    piles = {"contradicted": [], "unsupported": [], "confirmed": [],
             "coverage": [], "self_correction_off": []}
    if not mdir.exists():
        return {"piles": piles, "authorities": authority, "current": 0}

    files = sorted(mdir.glob("**/*.md"))
    if limit:
        files = files[:limit]
    current = 0
    with Progress(len(files), "auditing memories") as p:
        for f in files:
            p.step()
            try:
                fm, body = parse_frontmatter(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if fm.get("status") != "current":
                continue
            current += 1
            text = " ".join(body.split())
            checkable = False

            for family, tag in model_tokens(text, authority["models"]):
                truth = authority["models"].get(family)
                if truth is None:
                    checkable = True
                    piles["unsupported"].append({
                        "stem": f.stem, "claim": tag,
                        "why": f"no configuration file pins '{family}'"})
                    continue
                checkable = True
                pile = "confirmed" if tag.lower() == truth.lower() else "contradicted"
                piles[pile].append({"stem": f.stem, "claim": tag,
                                    "authority": truth, "key": family})

            for key, claim in value_claims(text, authority["values"]):
                checkable = True
                truth = authority["values"][key]
                pile = "confirmed" if _same_value(claim, truth) else "contradicted"
                piles[pile].append({"stem": f.stem, "claim": f"{key}={claim}",
                                    "authority": f"{key}={truth}", "key": key})

            if not checkable:
                piles["coverage"].append({"stem": f.stem})
            elif _memory.coerce_volatility(fm.get("volatility"), body) == "event":
                # TASK-146 mitigation: this memory DOES carry a value that can
                # go stale, but counts as an event and is therefore never
                # replaced. For this set, self-correction is switched off.
                piles["self_correction_off"].append({"stem": f.stem})

    return {"piles": piles, "authorities": authority, "current": current}


def report(res: dict) -> str:
    p = res["piles"]
    lines = []
    for name, heading in (("contradicted", "CONTRADICTED"),
                          ("unsupported", "UNSUPPORTED")):
        if not p[name]:
            continue
        lines.append(f"\n{heading}  {len(p[name])}")
        for it in p[name]:
            lines.append(f"  {it['stem']}")
            lines.append(f"      says: {it['claim']}")
            if it.get("authority"):
                lines.append(f"      authority: {it['authority']}")
            elif it.get("why"):
                lines.append(f"      {it['why']}")
    if p["self_correction_off"]:
        lines.append(f"\nNEVER CORRECTED  {len(p['self_correction_off'])}")
        lines.append("  carries a checkable value but counts as an event, "
                     "so it is never replaced:")
        for it in p["self_correction_off"][:10]:
            lines.append(f"  {it['stem']}")
    lines.append(f"\nCONFIRMED     {len(p['confirmed'])}")
    lines.append(f"COVERAGE      {len(p['coverage'])} of {res['current']} current "
                 f"memories carry no checkable value")
    lines.append("              -- there this audit was blind; that is not an approval")
    return "\n".join(lines)


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    limit = None
    if "--limit" in argv:
        try:
            limit = int(argv[argv.index("--limit") + 1])
        except Exception:
            limit = None
    res = audit(limit=limit)
    if "--json" in argv:
        print(json.dumps({k: v for k, v in res["piles"].items()}, ensure_ascii=False))
    else:
        print(report(res))
    if "--fail-on-contradiction" in argv and res["piles"]["contradicted"]:
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # never block a session on an audit
        print(f"kb-state-audit: skipped ({exc})", file=sys.stderr)
        sys.exit(0)
