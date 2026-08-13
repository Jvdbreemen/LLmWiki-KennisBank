#!/usr/bin/env python3
"""kb-state-audit.py - welke memories spreken de configuratie tegen?

Deterministisch, read-only, geen LLM. Vergelijkt de claims in de geheugenlaag
met een GEZAG: de configuratiebestanden en de constanten in deze scripts. Dat
is het verschil met een tweede mening -- er is een bron die per definitie
gelijk heeft over wat er nu draait.

De aanleiding: de `second-brain-audit`-skill levert een deterministische
scanner mee, en die vond op deze vault NUL tegenstrijdigheden terwijl er
aantoonbaar vier stonden. Hij vergelijkt namelijk alleen geldbedragen, en die
staan hier niet in. Zijn eigen handleiding zegt precies dat: "A zero is not a
clean bill of health". Deze audit doet hetzelfde trucje voor de waardesoorten
die deze vault WEL draagt -- modeltags, drempels, versies, paden, vlaggen --
en meldt net zo hard waar hij blind was.

Vier stapels, en de laatste is het punt:

    CONTRADICTED  het geheugen zegt X, het gezag zegt Y
    UNSUPPORTED   een waarde die in geen enkel gezag voorkomt
    CONFIRMED     het geheugen klopt met het gezag
    COVERAGE      current memories zonder toetsbare waarde -- hier was de
                  audit blind, en dat is geen goedkeuring

Plus een vijfde die uit TASK-146 komt: memories die een toetsbare waarde
dragen maar als `event` gelden. Die worden nooit vervangen, dus voor precies
die verzameling staat zelfcorrectie uit. De veilige default mag zichtbaar
kosten hebben, niet stille.

Alleen `status: current`, want dat is exact de verzameling die de recall-hook
kan injecteren. In deze vault bestaat geen ongevaarlijk archief: wat current
is, is altijd-geladen.

Usage: python3 kb-state-audit.py [--json] [--fail-on-contradiction] [--limit N]
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _memory  # noqa: E402
import _settings  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402
from _progress import Progress  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

#: Modelnamen komen in twee vormen voor. Ollama gebruikt `familie:tag`
#: (qwen3-embedding:4b); cloudmodellen dragen hun versie in de naam zelf
#: (claude-opus-4-8, text-embedding-3-small). Beide moeten herkenbaar zijn,
#: anders valt precies de stale claim buiten beeld.
_OLLAMA_TAG = re.compile(r"\b([a-z][a-z0-9.]*(?:-[a-z0-9.]+)*):([a-z0-9][a-z0-9._-]*)\b")

#: Cloudmodellen worden herkend aan een VASTE familielijst, niet aan een
#: vendorprefix. Gemeten op de levende vault: een prefixregel las
#: `Claude-sessiehistorie` en `Claude-cli` als modellen, en de eerste is een
#: Nederlands woord met een streepje ervoor. Een lijst is saaier en klopt.
_VENDOR_FAMILIES = (
    "claude-opus", "claude-sonnet", "claude-haiku", "claude-fable",
    "gpt", "gemini", "llama", "mistral", "mixtral", "phi", "deepseek",
    "nomic-embed-text", "text-embedding", "voyage", "mxbai-embed",
)
_VENDOR_MODEL = re.compile(
    r"\b((?:" + "|".join(re.escape(f) for f in _VENDOR_FAMILIES) + r")"
    r"(?:-[a-z0-9.]+)*)\b", re.IGNORECASE)


def _clean_config(obj):
    """Alleen de ACTIEVE sleutels. `_switching` en elke `_`-sleutel zijn
    voorbeelden en commentaar -- die noemen andere modellen (gemma4:12b,
    text-embedding-3-small) en zijn dus juist NIET het gezag. Ze meenemen zou
    van elke stale claim een bevestigde maken."""
    if not isinstance(obj, dict):
        return {}
    return {k: v for k, v in obj.items() if not k.startswith("_")}


def _read_json(path: Path) -> dict:
    try:
        return _clean_config(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return {}


def code_constants() -> dict:
    """Constanten uit de scripts zelf. Ook een gezag: wat de code doet is wat
    er gebeurt, ongeacht wat een memory erover beweert. Fail-soft per module,
    want een deploy kan er een missen."""
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
    """Het gezag, als {modelfamilie -> tag} en {sleutel -> waarde}."""
    root = vault_root()
    embed = _read_json(root / ".claude" / "kennisbank-embed.json")
    llm = _read_json(root / ".claude" / "kennisbank-llm.json")

    models = {}
    for cfg in (embed, llm):
        tag = str(cfg.get("model", "")).strip()
        if not tag:
            continue
        familie = tag.split(":")[0] if ":" in tag else tag
        models[familie.lower()] = tag

    waarden = {}
    for sleutel in ("retrieve_top_n", "retrieve_threshold"):
        if sleutel in embed:
            waarden[sleutel] = embed[sleutel]
    # `endpoint` staat er BEWUST niet bij. Het is een gewoon Engels woord, en
    # deze vault staat vol memories over REST-endpoints van firmware. Gemeten:
    # acht van de twaalf 'tegenstrijdigheden' waren zulke zinnen, met claims
    # als "endpoint=2" tegenover "http://localhost:11434". Een sleutel die ook
    # een woord is, is geen sleutel. Zie _looks_like_key hieronder.
    # De toggles: de LEVENDE waarde via _settings.get, niet de default uit de
    # code. Een memory die zegt dat archiveren aanstaat is fout of goed op
    # grond van wat er in kennisbank-settings.json staat, niet van wat de
    # broncode als beginwaarde meelevert.
    for sleutel in getattr(_settings, "DEFAULTS", {}):
        try:
            waarden[sleutel] = _settings.get(sleutel)
        except Exception:
            pass
    waarden.update(code_constants())
    return {"models": models, "values": waarden}


def model_tokens(text: str, known_families=()) -> list:
    """Elke modelnaam in de tekst, als (familie, volledige_tag)."""
    uit = []
    bekend = set(known_families or ())
    for m in _OLLAMA_TAG.finditer(text):
        familie, tag = m.group(1), m.group(2)
        # `familie:tag` matcht ook `adr-kit:adr`, `file:line`, `f1:ab` en
        # `_kbindex.py:41`. Gemeten op de levende vault leverde die vorm meer
        # valse modellen op dan echte. Alleen families die een
        # configuratiebestand daadwerkelijk pint tellen mee; de rest is voor
        # deze audit gewoon geen modelclaim en valt onder COVERAGE.
        if familie.lower() not in bekend:
            continue
        uit.append((familie.lower(), f"{familie}:{tag}"))
    for m in _VENDOR_MODEL.finditer(text):
        naam = m.group(1)
        # Familie = de naam zonder het versiestaartje, zodat claude-opus-4-8
        # en claude-opus-5 dezelfde familie zijn.
        familie = re.sub(r"-[\d.]+([-.][\d.]+)*$", "", naam).lower()
        uit.append((familie, naam))
    # Eén regel per familie per memory. "Gemini" en "Gemini-keys" in dezelfde
    # tekst zijn één claim over één familie; twee regels lezen als twee
    # bevindingen en blazen elke telling op.
    gezien, uniek = set(), []
    for familie, naam in uit:
        if familie in gezien:
            continue
        gezien.add(familie)
        uniek.append((familie, naam))
    return uniek


#: Een waarde vlak achter een sleutelnaam. Ruim genoeg voor "de drempel
#: retrieve_threshold is 0.6" en krap genoeg om niet het hele document te
#: vangen.
_VALUE_NEAR = r"[^\n]{0,40}?(-?\d+(?:\.\d+)?|true|false|waar|onwaar)\b"


def _looks_like_key(key: str) -> bool:
    """Alleen sleutels die niet ook een gewoon woord kunnen zijn.

    Dezelfde grens als _memory.looks_like_config: een underscore, een punt, of
    ALL_CAPS. `retrieve_top_n` en `RECONCILE_THRESHOLD` overleven; `endpoint`
    en `model` niet, en dat is precies de bedoeling -- die woorden staan in
    tientallen memories over iets heel anders.
    """
    k = str(key)
    return ("_" in k) or ("." in k) or (k.isupper() and len(k) > 2)


def value_claims(text: str, keys) -> list:
    """(sleutel, geclaimde_waarde) voor elke gezagssleutel die in de tekst
    staat met een waarde erachter."""
    uit = []
    for key in keys:
        if not _looks_like_key(key):
            continue
        patroon = re.compile(r"\b" + re.escape(str(key)) + _VALUE_NEAR, re.IGNORECASE)
        m = patroon.search(text)
        if m:
            uit.append((key, m.group(1)))
    return uit


def _same_value(claim: str, truth) -> bool:
    """Gelijk na normalisatie: 3 == 3.0, 'true' == True."""
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
    gezag = authorities()
    mdir = vault_root() / "09-memory"
    piles = {"contradicted": [], "unsupported": [], "confirmed": [],
             "coverage": [], "self_correction_off": []}
    if not mdir.exists():
        return {"piles": piles, "authorities": gezag, "current": 0}

    files = sorted(mdir.glob("**/*.md"))
    if limit:
        files = files[:limit]
    current = 0
    with Progress(len(files), "memories toetsen") as p:
        for f in files:
            p.step()
            try:
                fm, body = parse_frontmatter(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if fm.get("status") != "current":
                continue
            current += 1
            tekst = " ".join(body.split())
            toetsbaar = False

            for familie, tag in model_tokens(tekst, gezag["models"]):
                waarheid = gezag["models"].get(familie)
                if waarheid is None:
                    toetsbaar = True
                    piles["unsupported"].append({
                        "stem": f.stem, "claim": tag,
                        "why": f"geen enkel configuratiebestand pint '{familie}'"})
                    continue
                toetsbaar = True
                pile = "confirmed" if tag.lower() == waarheid.lower() else "contradicted"
                piles[pile].append({"stem": f.stem, "claim": tag,
                                    "authority": waarheid, "key": familie})

            for key, claim in value_claims(tekst, gezag["values"]):
                toetsbaar = True
                waarheid = gezag["values"][key]
                pile = "confirmed" if _same_value(claim, waarheid) else "contradicted"
                piles[pile].append({"stem": f.stem, "claim": f"{key}={claim}",
                                    "authority": f"{key}={waarheid}", "key": key})

            if not toetsbaar:
                piles["coverage"].append({"stem": f.stem})
            elif _memory.coerce_volatility(fm.get("volatility"), body) == "event":
                # TASK-146-mitigatie: deze memory DRAAGT een waarde die kan
                # verouderen, maar geldt als gebeurtenis en wordt dus nooit
                # vervangen. Voor deze verzameling staat zelfcorrectie uit.
                piles["self_correction_off"].append({"stem": f.stem})

    return {"piles": piles, "authorities": gezag, "current": current}


def report(res: dict) -> str:
    p = res["piles"]
    regels = []
    for naam, kop in (("contradicted", "CONTRADICTED"),
                      ("unsupported", "UNSUPPORTED")):
        if not p[naam]:
            continue
        regels.append(f"\n{kop}  {len(p[naam])}")
        for it in p[naam]:
            regels.append(f"  {it['stem']}")
            regels.append(f"      zegt: {it['claim']}")
            if it.get("authority"):
                regels.append(f"      gezag: {it['authority']}")
            elif it.get("why"):
                regels.append(f"      {it['why']}")
    if p["self_correction_off"]:
        regels.append(f"\nNOOIT GECORRIGEERD  {len(p['self_correction_off'])}")
        regels.append("  draagt een toetsbare waarde maar geldt als gebeurtenis, "
                      "dus wordt nooit vervangen:")
        for it in p["self_correction_off"][:10]:
            regels.append(f"  {it['stem']}")
    regels.append(f"\nCONFIRMED     {len(p['confirmed'])}")
    regels.append(f"COVERAGE      {len(p['coverage'])} van de {res['current']} current "
                  f"memories dragen geen toetsbare waarde")
    regels.append("              -- daar was deze audit blind; dat is geen goedkeuring")
    return "\n".join(regels)


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
    except Exception as exc:  # nooit een sessie blokkeren op een audit
        print(f"kb-state-audit: overgeslagen ({exc})", file=sys.stderr)
        sys.exit(0)
