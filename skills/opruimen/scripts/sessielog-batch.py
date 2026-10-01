#!/usr/bin/env python3
"""Batch-sessielogs voor Hermes-sessies, gebruikt door de opruimen-skill.

Stap 1 (manifest): digests bouwen, matchen tegen bestaande logs in de vault.
Stap 2 (genereer): per sessie met een digest een log laten schrijven via
OpenRouter (stealth/space-bunny-alpha) met CCR als reserve, en wegschrijven naar
01-raw/sessies/. Status in een JSON-statefile, dus een afgebroken run kan gewoon
opnieuw starten.

Gevoelige sessies (zie gevoelig-paden.txt) gaan nooit naar een cloudmodel; die
gaan naar het lokale ollama-model of worden geblokkeerd gemeld.

De Hermes-store komt uit HERMES_HOME (default ~/.hermes), de vault uit
KENNISBANK_VAULT (default ~/KennisBank).

Gebruik:
  sessielog-batch.py manifest
  sessielog-batch.py genereer [--een <id>] [--natek-index] [--force-cloud]
  sessielog-batch.py --zelftest
"""
import datetime as dt
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERMES_HOME = os.path.expanduser(os.environ.get("HERMES_HOME") or "~/.hermes")
DB = os.path.join(HERMES_HOME, "state.db")
STATE = os.path.join(HERMES_HOME, "cache/scratch/sessielog-batch-state.json")

ROUTE = os.environ.get("SESSIELOG_ROUTE", "openrouter")      # openrouter | ccr
MODEL = os.environ.get("SESSIELOG_MODEL", "stealth/space-bunny-alpha")
OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
CCR = "http://127.0.0.1:3456/v1/messages"
CCR_MODEL = "openrouter,z-ai/glm-5.3-flash"
MAX_TOKENS = int(os.environ.get("SESSIELOG_MAX_TOKENS", "16000"))
OLLAMA = "http://127.0.0.1:11434/api/chat"
LOKAAL_MODEL = os.environ.get("SESSIELOG_LOKAAL_MODEL", "qwen3.8:27b-mlx")
LOKAAL_CTX = int(os.environ.get("SESSIELOG_LOKAAL_CTX", "16384"))
# Ollama kapt stil af op num_ctx. Beter zelf kappen, met een zichtbare markering,
# dan een log dat het einde van de sessie mist zonder dat iemand dat ziet.
LOKAAL_DIGEST = int(os.environ.get("SESSIELOG_LOKAAL_DIGEST", "24000"))

MIN_BERICHTEN = 8          # daaronder: statuscheck, niet logbaar
DIGEST_LIMIET = 60000
HERMES_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEVOELIG_BESTAND = os.path.join(HERMES_DIR, "gevoelig-paden.txt")

GEVOELIG_DEFAULT = [
    "01-raw/interview",
    "interviewtranscript",
    "interviewdata",
    "brondata",
    "enquete",
    "enquête",
    "sollicitatie",
    "medisch",
    "financie",
]

STILTE_UREN = float(os.environ.get("STILTE_UREN", "6"))

_template_cache = {}


def vault():
    """Resolutie volgens de KennisBank-regel: env eerst, dan productdefault."""
    return os.path.abspath(os.environ.get("KENNISBANK_VAULT")
                           or os.path.expanduser("~/KennisBank"))


def logdir():
    d = os.path.join(vault(), "01-raw/sessies")
    if not os.path.isdir(d):
        raise FileNotFoundError(
            f"logsessie-map ontbreekt: {d}\n"
            f"control KENNISBANK_VAULT (nu {vault()}) of geef --vault <pad>")
    return d


def template():
    """Template per vault, met een expliciete foutmelding als hij ontbreekt."""
    v = vault()
    if v in _template_cache:
        return _template_cache[v]
    pad = os.path.join(v, "04-templates/tpl-sessie-log.md")
    if not os.path.isfile(pad):
        raise FileNotFoundError(
            f"template ontbreekt: {pad}\n"
            f"control KENNISBANK_VAULT (nu {v}) of geef --vault <pad>")
    with open(pad, encoding="utf-8", errors="replace") as fh:
        _template_cache[v] = fh.read()
    return _template_cache[v]


def gevoelig_pad():
    """Het bestand naast het script of in de skillmap."""
    hier = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "gevoelig-paden.txt")
    return hier if os.path.isfile(hier) else GEVOELIG_BESTAND


def gevoelige_regexen():
    """Lees gevoelig-paden.txt en vul aan op de ingebakken defaultlijst.

    De defaultlijst geldt altijd: het bestand kan patronen toevoegen, niet
    weghalen. Een per ongeluk leeg of verwijderd bestand mag het hek niet openen.
    """
    regels = list(GEVOELIG_DEFAULT)
    pad = gevoelig_pad()
    if os.path.isfile(pad):
        try:
            with open(pad, encoding="utf-8", errors="replace") as fh:
                for regel in fh:
                    r = regel.strip()
                    if r and not r.startswith("#"):
                        regels.append(r)
        except OSError:
            pass
    return list(dict.fromkeys(regels))


def is_gevoelig(dig):
    laag = (dig or "").lower()
    return any(r.lower() in laag for r in gevoelige_regexen())


def kies_route(dig, force_cloud=False):
    """'lokaal' als de digest gevoelig is en de route een cloudroute is."""
    cloud = ROUTE in ("openrouter", "ccr")
    if cloud and is_gevoelig(dig) and not force_cloud:
        return "lokaal"
    return "cloud"


def api_key():
    """OPENROUTER_API_KEY uit de omgeving of uit de lokale env-bestanden."""
    k = os.environ.get("OPENROUTER_API_KEY")
    if k and k.strip() and "$" not in k:
        return k.strip()
    for pad in (os.path.join(HERMES_HOME, ".env"),
                os.path.expanduser("~/.openrouter-env")):
        if not os.path.isfile(pad):
            continue
        try:
            with open(pad, encoding="utf-8", errors="replace") as fh:
                for regel in fh:
                    r = regel.strip()
                    if r.startswith("export "):
                        r = r[len("export "):].strip()
                    if not r.startswith("OPENROUTER_API_KEY="):
                        continue
                    waarde = r.split("=", 1)[1].strip().strip("\"'")
                    if waarde and "$" not in waarde:
                        return waarde
        except OSError:
            continue
    raise RuntimeError(
        "geen OPENROUTER_API_KEY gevonden in de omgeving, $HERMES_HOME/.env "
        "of ~/.openrouter-env; zet de variabele of start CCR met de key")


def usage_tokens(antw):
    u = antw.get("usage") or {}
    return int(u.get("total_tokens") or (u.get("input_tokens", 0)
                                         + u.get("output_tokens", 0)) or 0)


def body_snippet(e):
    try:
        return e.read().decode("utf-8", "replace")[:300]
    except Exception:  # noqa: BLE001 - alleen voor de foutmelding
        return str(e)[:300]


def retrybaar(e):
    code = getattr(e, "code", None)
    if code == 429 or (isinstance(code, int) and 500 <= code < 600):
        return True
    t = str(e).lower()
    return "timeout" in t or "timed out" in t or "urlerror" in t \
        or "connection" in t or "reset by peer" in t


def prompt_voor(dig, max_digest=None):
    if max_digest and len(dig) > max_digest:
        dig = (dig[:max_digest]
               + f"\n[... digest afgekapt op {max_digest} van {len(dig)} tekens; "
                 "het einde van de sessie ontbreekt ...]")
    return ("Schrijf een sessielog in het Nederlands voor onderstaande werksessie. "
            "Gebruik exact het template. Vul elke kop in; laat geen kop weg en laat "
            "geen HTML-commentaar staan. Begin je antwoord met een regel "
            "'SLUG: <korte-kebab-case-slug>' en daarna pas het template.\n\n"
            "=== TEMPLATE ===\n" + template() + "\n=== DIGEST ===\n" + dig)


def _compleet(tekst):
    return "## AI-verantwoording" in (tekst or "")


def openrouter_log(prompt):
    """Hoofdroute: OpenRouter met stealth/space-bunny-alpha, reasoning aan."""
    body = json.dumps({"model": MODEL, "max_tokens": MAX_TOKENS,
                       "reasoning": {"enabled": True},
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    laatste = None
    for poging in range(3):
        try:
            req = urllib.request.Request(OPENROUTER, data=body, headers={
                "content-type": "application/json",
                "authorization": "Bearer " + api_key(),
                "http-referer": "https://hermes.local/opruimen",
                "x-title": "hermes-opruimen-sessielog"})
            with urllib.request.urlopen(req, timeout=600) as r:
                antw = json.loads(r.read())
            tekst = (antw.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            if not _compleet(tekst):
                laatste = RuntimeError(
                    "onvolledig: laatste kop '## AI-verantwoording' ontbreekt "
                    f"(finish_reason={(antw.get('choices') or [{}])[0].get('finish_reason')})")
            else:
                return tekst, usage_tokens(antw)
        except urllib.error.HTTPError as e:
            if not retrybaar(e):
                raise RuntimeError(f"OpenRouter HTTP {e.code}: {body_snippet(e)}")
            laatste = RuntimeError(f"OpenRouter HTTP {e.code}: {body_snippet(e)}")
        except RuntimeError as e:
            laatste = e
        except Exception as e:  # noqa: BLE001 - retry op netwerkfouten
            if not retrybaar(e):
                raise RuntimeError(f"OpenRouter-fout: {str(e)[:300]}")
            laatste = e
        if poging < 2:
            time.sleep((5, 15, 45)[poging])
    raise laatste


def ccr_log(prompt):
    """Reserve: CCR met glm-5.3-flash. Gedrag ongewijzigd."""
    body = json.dumps({"model": CCR_MODEL, "max_tokens": MAX_TOKENS,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    laatste = None
    for poging in range(3):
        try:
            req = urllib.request.Request(CCR, data=body, headers={
                "content-type": "application/json",
                "anthropic-version": "2023-06-01"})
            with urllib.request.urlopen(req, timeout=300) as r:
                antw = json.loads(r.read())
            tekst = "".join(b.get("text", "") for b in antw.get("content", []))
            if not _compleet(tekst):
                laatste = RuntimeError("onvolledig: laatste kop ontbreekt")
                continue
            return tekst, usage_tokens(antw)
        except Exception as e:  # noqa: BLE001 - bewust breed, met retry
            laatste = e
            if retrybaar(e):
                time.sleep(5)
                continue
            raise
    raise laatste


def ollama_log(prompt):
    """Lokale route voor gevoelige sessies. Geen stille terugval naar de cloud."""
    body = json.dumps({"model": LOKAAL_MODEL, "stream": False,
                       "options": {"num_ctx": LOKAAL_CTX},
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    try:
        req = urllib.request.Request(OLLAMA, data=body, headers={
            "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=1800) as r:
            antw = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"lokale route onbereikbaar ({OLLAMA}): {str(e)[:300]}")
    tekst = (antw.get("message") or {}).get("content") or ""
    if not _compleet(tekst):
        raise RuntimeError("lokale route: laatste kop '## AI-verantwoording' ontbreekt")
    return tekst, int(antw.get("eval_count") or antw.get("prompt_eval_count") or 0)


def log_via(dig, route):
    """route: 'cloud' volgt ROUTE, 'lokaal' gaat naar ollama."""
    if route == "lokaal":
        return ollama_log(prompt_voor(dig, LOKAAL_DIGEST)), LOKAAL_MODEL
    if ROUTE == "ccr":
        return ccr_log(prompt_voor(dig)), CCR_MODEL
    return openrouter_log(prompt_voor(dig)), MODEL


def doel_sessies():
    """Open sessies zonder activiteit in de laatste STILTE_UREN (default 6),
    minus pinned/hidden/Bot Chat en de lopende beurt."""
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    nu = dt.datetime.now()
    grens = nu.timestamp() - STILTE_UREN * 3600
    lopend = {r["conversation_id"] for r in c.execute(
        "select conversation_id, expires_at from session_turn_leases")
        if float(r["expires_at"]) > nu.timestamp()}
    uit = []
    for r in c.execute(
            "select id, source, title, message_count, started_at, last_activity_at, "
            "pinned, hidden from sessions where archived = 0"):
        ref = float(r["last_activity_at"] or r["started_at"] or 0)
        if ref >= grens:
            continue
        if r["id"] in lopend or r["pinned"] or r["hidden"]:
            continue
        if (r["title"] or "") == "Bot Chat":
            continue
        if (r["message_count"] or 0) < MIN_BERICHTEN:
            uit.append({"id": r["id"], "bron": r["source"], "berichten": r["message_count"],
                        "status": "te-klein", "reden": "statuscheck, niet logbaar"})
            continue
        uit.append({"id": r["id"], "bron": r["source"], "berichten": r["message_count"],
                    "start": r["started_at"], "laatst": ref, "titel": r["title"] or "",
                    "status": "open"})
    c.close()
    return uit


def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def blokken_als_tekst(content):
    """content is vaak JSON: lijst van blokken. Geef leesbare tekst terug."""
    if content is None:
        return ""
    t = content.strip()
    if t.startswith("[") or t.startswith("{"):
        try:
            data = json.loads(t)
        except (ValueError, TypeError):
            return t
        def loop(x):
            if isinstance(x, str):
                return x
            if isinstance(x, dict):
                if x.get("type") == "text":
                    return x.get("text", "")
                if x.get("type") == "tool_use":
                    return f"[tool: {x.get('name')}] {json.dumps(x.get('input', {}))[:200]}"
                if x.get("type") == "tool_result":
                    return ""  # geen tool-resultaten in digest
                return " ".join(loop(v) for v in x.values() if not isinstance(v, (dict,)) or True)
            if isinstance(x, list):
                return " ".join(loop(i) for i in x)
            return ""
        return loop(data)
    return t


def digest(sessie):
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    rijen = c.execute(
        "select role, content, tool_name, timestamp from messages "
        "where session_id = ? and active = 1 order by timestamp, id",
        (sessie["id"],)).fetchall()
    c.close()
    prompts, assist, tools, bestanden = [], [], {}, set()
    for r in rijen:
        tekst = blokken_als_tekst(r["content"]).strip()
        if r["tool_name"]:
            tools[r["tool_name"]] = tools.get(r["tool_name"], 0) + 1
        for m in re.finditer(r"(/Users/\S+|~/\S+)", tekst):
            bestanden.add(m.group(1).rstrip(".,:)\"'"))
        if r["role"] == "user" and tekst and not tekst.startswith("<") \
                and "system-reminder" not in tekst[:60] and "Caveat:" not in tekst[:60]:
            prompts.append(tekst)
        elif r["role"] == "assistant" and tekst:
            assist.append(tekst)
    d = []
    d.append(f"SESSIE {sessie['id']} | bron {sessie['bron']} | "
             f"{dt.datetime.fromtimestamp(sessie['start']):%Y-%m-%d %H:%M} tot "
             f"{dt.datetime.fromtimestamp(sessie['laatst']):%Y-%m-%d %H:%M} | "
             f"{sessie['berichten']} berichten")
    if sessie.get("titel"):
        d.append(f"TITEL: {sessie['titel']}")
    d.append("\nGEBRUIKERSPROMPTS (chronologisch):")
    for i, p in enumerate(prompts, 1):
        d.append(f"[{i}] {p[:600]}")
    if tools:
        d.append("\nTOOLGEBRUIK: " + ", ".join(f"{k} x{v}" for k, v in sorted(tools.items())))
    if bestanden:
        d.append("\nAANGERAAKTE BESTANDEN: " + ", ".join(sorted(bestanden)[:40]))
    d.append("\nSLOTFRAGMENTEN VAN ASSISTENTANTWOORDEN:")
    for a in assist[-12:]:
        d.append("- " + a[-400:].replace("\n", " "))
    return "\n".join(d)[:DIGEST_LIMIET]


def bestaande_logs():
    logs = {}
    for f in os.listdir(logdir()):
        if f.endswith(".md"):
            logs[f] = norm(open(os.path.join(logdir(), f), encoding="utf-8",
                                errors="replace").read())
    return logs


def match_log(dig, logs):
    """Zoek een log die een herkenbaar stuk van de eerste/laatste prompt bevat."""
    ankers = []
    for regel in dig.splitlines():
        if regel.startswith("[1] "):
            ankers.append(norm(regel[4:8 + 30]))
        if regel.startswith("[") and "] " in regel[:6]:
            ankers.append(norm(regel.split("] ", 1)[1][:34]))
    ankers = [a for a in ankers if len(a) >= 20][:4]
    for naam, tekst in logs.items():
        for a in ankers:
            if a in tekst:
                return naam, a
    return None, None


def slug_voor(dig):
    m = re.search(r"TITEL: (.+)", dig)
    bron = m.group(1) if m else ""
    if not bron:
        for regel in dig.splitlines():
            if regel.startswith("[1] "):
                bron = regel[4:]
                break
    s = norm(bron)[:48].strip().replace(" ", "-")
    return s or "sessie"


def natek(tekst):
    """Deterministische natek: Hermes-conventie forceren in plaats van hopen.

    - frontmatter: tags/source claude-sessie -> hermes-sessie (het model kopieert
      het template letterlijk; dit fixt het zonder een apart natek-script).
    - ruwe kandidaat-zinnen -> scan-formaat "- wiki-kandidaat: <onderwerp>"
      (wordt door wiki-scan.py herkend; de riemannvarianten van het model niet).
    """
    tekst = tekst.replace("source: claude-sessie", "source: hermes-sessie")
    tekst = re.sub(r"tags:\s*\[[^\]]*claude-sessie[^\]]*\]",
                   lambda mm: mm.group(0).replace("claude-sessie", "hermes-sessie"),
                   tekst)
    uit = []
    marker = re.compile(
        r"[Kk]andidaat[ -]?(?:voor[ -]|voor\s+)?[Ww]iki[ -]?,?\s*artikel(?:\s+over)?[:\s,-]+(.+?)\.?\s*$"
    )
    for regel in tekst.splitlines():
        m = marker.search(regel)
        if not m:
            uit.append(regel)
            continue
        topic = m.group(1).strip().strip("[]\"'").strip().rstrip(". ")
        voor = regel[: m.start()].rstrip()
        if re.fullmatch(r"[-*]?", voor.strip()):
            uit.append(f"- wiki-kandidaat: {topic}")
        else:
            uit.append(voor)
            uit.append(f"- wiki-kandidaat: {topic}")
    return "\n".join(uit)


def schrijf_log(s, tekst):
    m = re.match(r"SLUG:\s*(\S[^\n]*)", tekst)
    slug = norm((m.group(1) if m else ""))[:48].strip().replace(" ", "-") \
        or slug_voor(s["digest"])
    if m:
        tekst = tekst[m.end():].lstrip()
    tekst = natek(tekst)
    datum = dt.datetime.fromtimestamp(s["start"]).strftime("%Y-%m-%d")
    pad = os.path.join(logdir(), f"raw-sessie-{datum}-{slug}.md")
    if os.path.exists(pad):
        pad = os.path.join(logdir(), f"raw-sessie-{datum}-{slug}-{s['id'][:6]}.md")
    with open(pad, "w", encoding="utf-8") as fh:
        fh.write(tekst.rstrip() + "\n")
    return os.path.basename(pad)


def aantal_kandidaten(pad):
    try:
        with open(pad, encoding="utf-8", errors="replace") as fh:
            return sum(1 for r in fh if r.startswith("- wiki-kandidaat:"))
    except OSError:
        return -1


def natek_index():
    """Opt-in nasleep: karpathy-index herbouwen en graphify markeren."""
    v = vault()
    regels = []
    idx = os.path.join(v, ".claude/scripts/build-karpathy-index.py")
    py = os.path.expanduser("~/.venvs/llmwiki-dev/bin/python")
    if os.path.isfile(idx) and os.path.isfile(py):
        p = subprocess.run([py, idx, "--force"], cwd=v, capture_output=True,
                           text=True, timeout=1800)
        regels.append(f"build-karpathy-index: rc={p.returncode} "
                      f"{(p.stdout or p.stderr).strip().splitlines()[-1] if (p.stdout or p.stderr).strip() else ''}")
    else:
        regels.append(f"build-karpathy-index: overgeslagen, ontbreekt ({idx})")
    graph = os.path.join(v, "graphify-out")
    if os.path.isdir(graph):
        open(os.path.join(graph, ".needs-rebuild"), "a").close()
        regels.append("graphify: .needs-rebuild gezet")
    else:
        regels.append(f"graphify: overgeslagen, map ontbreekt ({graph})")
    return regels


def zelftest():
    checks = []

    def check(naam, ok, detail=""):
        checks.append((naam, bool(ok), detail))

    env = os.environ.get("KENNISBANK_VAULT")
    try:
        os.environ["KENNISBANK_VAULT"] = "/tmp/x"
        check("vault() volgt KENNISBANK_VAULT", vault() == "/tmp/x", vault())
        del os.environ["KENNISBANK_VAULT"]
        check("vault() zonder env is ~/KennisBank",
              vault() == os.path.abspath(os.path.expanduser("~/KennisBank")), vault())
    finally:
        if env is not None:
            os.environ["KENNISBANK_VAULT"] = env
        else:
            os.environ.pop("KENNISBANK_VAULT", None)

    gevoelig = "/home/gebruiker/01-raw/interview/brondata interviewscript"
    check("is_gevoelig herkent brondata", is_gevoelig(gevoelig))
    check("is_gevoelig negeert gewone sessie", not is_gevoelig("gewone sessie over css"))

    t = natek("---\nsource: claude-sessie\ntags: [claude-sessie, x]\n"
              "- Kandidaat voor wiki-artikel: kennisbank indexbouw\n")
    check("natek zet source om naar hermes-sessie",
          "source: hermes-sessie" in t and "claude-sessie" not in t, t.replace("\n", " | "))
    kand = [r for r in t.splitlines() if r.startswith("- wiki-kandidaat:")]
    check("natek maakt precies één - wiki-kandidaat regel",
          len(kand) == 1 and kand[0] == "- wiki-kandidaat: kennisbank indexbouw",
          " | ".join(kand))

    r1 = kies_route(gevoelig, force_cloud=False)
    r2 = kies_route(gevoelig, force_cloud=True)
    r3 = kies_route("gewone sessie over css", force_cloud=False)
    check("gevoelige digest zonder --force-cloud -> lokaal", r1 == "lokaal", r1)
    check("gevoelige digest met --force-cloud -> cloud", r2 == "cloud", r2)
    check("niet-gevoelige digest -> cloud", r3 == "cloud", r3)
    r4 = kies_route("gewone digest zonder bijzonderheden\n"
                    "sessietitel: enquête respondentdata verwerken", force_cloud=False)
    check("titel telt mee in het hek", r4 == "lokaal", r4)

    for naam, ok, detail in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {naam}" + (f"  [{detail}]" if detail else ""))
    falen = sum(1 for _, ok, _ in checks if not ok)
    print(f"\n{len(checks) - falen}/{len(checks)} checks PASS")
    return 1 if falen else 0


def main():
    argv = sys.argv[1:]
    if "--zelftest" in argv:
        sys.exit(zelftest())
    flags = ("--vault", "--een")
    if "--vault" in argv:
        os.environ["KENNISBANK_VAULT"] = argv[argv.index("--vault") + 1]
    cmd = next((a for i, a in enumerate(argv)
                if not a.startswith("-")
                and (i == 0 or argv[i - 1] not in flags)), "manifest")
    een = argv[argv.index("--een") + 1] if "--een" in argv else None
    force_cloud = "--force-cloud" in argv
    natek_vlag = "--natek-index" in argv

    if cmd == "manifest":
        vorige = {}
        if os.path.exists(STATE):
            for s in json.load(open(STATE))["sessies"]:
                if s.get("status") in ("gelogd", "al-gelogd", "mislukt"):
                    vorige[s["id"]] = s
        state = {"sessies": doel_sessies(), "gegenereerd": dt.datetime.now().isoformat()}
        logs = bestaande_logs()
        for s in state["sessies"]:
            if s["id"] in vorige and vorige[s["id"]].get("status") in ("gelogd", "al-gelogd"):
                oud = dict(vorige[s["id"]])
                s.clear()
                s.update(oud)
                # een geschreven log is vanaf nu een bestaand log: al-gelogd
                if s.get("status") == "gelogd":
                    s["status"] = "al-gelogd"
                continue
            if s["status"] != "open":
                continue
            dig = digest(s)
            s["digest"] = dig
            treffer, anker = match_log(dig, logs)
            if treffer:
                s["status"] = "al-gelogd"
                s["log"] = treffer
                s["anker"] = anker
                s.pop("digest")
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        json.dump(state, open(STATE, "w"), indent=1)
        for s in state["sessies"]:
            if s["status"] == "al-gelogd":
                print(f"al-gelogd  {s['id']} -> {s['log']}")
            elif s["status"] == "te-klein":
                print(f"te-klein   {s['id']} ({s['berichten']} berichten)")
            else:
                print(f"te-loggen  {s['id']}  {s['berichten']:>4} ber.  "
                      f"{dt.datetime.fromtimestamp(s['start']):%Y-%m-%d}")
        n = sum(1 for s in state["sessies"] if s["status"] == "open")
        print(f"\nte loggen: {n}, al gelogd: "
              f"{sum(1 for s in state['sessies'] if s['status'] == 'al-gelogd')}, "
              f"te klein: {sum(1 for s in state['sessies'] if s['status'] == 'te-klein')}")
        return

    if cmd == "genereer":
        state = json.load(open(STATE))
        routes = []
        for s in state["sessies"]:
            if s["status"] != "open" or (een and s["id"] != een):
                continue
            # Het hek toetst digest EN titel: een sessie die zichzelf in de titel al
            # als gevoelig aankondigt (bronmateriaal, enquete, interviewdata) hoort
            # niet naar de cloud. De titel is vaak het enige spoor als de prompts
            # zelf geen pad noemen.
            hek_tekst = (s.get("digest") or "") + "\n" + (s.get("titel") or "")
            route = kies_route(hek_tekst, force_cloud)
            if is_gevoelig(hek_tekst) and force_cloud:
                print(f"  LET OP {s['id']}: GEVOELIGE sessie naar de cloud "
                      f"(--force-cloud)", flush=True)
            elif route == "lokaal":
                print(f"  gevoelig: lokale route ({LOKAAL_MODEL})", flush=True)
            print(f"({dt.datetime.now():%H:%M:%S}) {s['id']} route={route} ...", flush=True)
            t0 = time.time()
            try:
                (tekst, tokens), model = log_via(s["digest"], route)
            except Exception as e:  # noqa: BLE001
                print(f"  MISLUKT: {e}", flush=True)
                s["status"] = ("geblokkeerd-gevoelig" if route == "lokaal" else "mislukt")
                s["fout"] = str(e)
                s["route"] = route
                s["model"] = LOKAAL_MODEL if route == "lokaal" else None
                s["seconden"] = round(time.time() - t0, 1)
                s["tokens"] = 0
                routes.append((s["id"], route, s["status"]))
                json.dump(state, open(STATE, "w"), indent=1)
                continue
            bestand = schrijf_log(s, tekst)
            s["status"] = "gelogd"
            s["log"] = bestand
            s["route"] = route
            s["model"] = model
            s["tokens"] = tokens
            s["seconden"] = round(time.time() - t0, 1)
            json.dump(state, open(STATE, "w"), indent=1)
            routes.append((s["id"], route, model))
            print(f"  -> {bestand}  ({s['seconden']}s, {tokens} tokens, {model})",
                  flush=True)

        print("\n=== eindrapport ===")
        print(f"vault: {vault()}")
        gelogd = [s for s in state["sessies"] if s["status"] == "gelogd"
                  and (not een or s["id"] == een)]
        print(f"gelogd: {len(gelogd)}")
        for s in gelogd:
            pad = os.path.join(logdir(), s["log"])
            print(f"  {pad}")
            print(f"    regels '- wiki-kandidaat:': {aantal_kandidaten(pad)}"
                  f"  route={s.get('route')} model={s.get('model')}"
                  f" tokens={s.get('tokens')} seconden={s.get('seconden')}")
        if routes:
            print("routes: " + ", ".join(f"{i}:{r}" for i, r, *_ in routes))
        lokaal = sum(1 for _, r, _ in routes if r == "lokaal")
        geblokkeerd = sum(1 for s in state["sessies"]
                         if s["status"] == "geblokkeerd-gevoelig"
                         and (not een or s["id"] == een))
        print(f"lokaal: {lokaal}, geblokkeerd-gevoelig: {geblokkeerd}")
        if natek_vlag:
            print("nasleep:")
            for r in natek_index():
                print(f"  {r}")
        print(f"\nvervolgstap: {os.path.join(vault(), '.claude/scripts/wiki-scan.py')} --days 8")
        return


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, RuntimeError) as e:
        print(f"FOUT: {e}", file=sys.stderr)
        sys.exit(1)