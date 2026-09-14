#!/usr/bin/env python3
"""Verify-pass: check wiki-artikelen tegen hun raw-sessie-bronnen via OpenRouter.

Per artikel één chat-completion-call naar een onafhankelijk model (default
deepseek/deepseek-v4-flash). Artikelen mét traceerbare ``raw-sessie``-links
worden tegen de volledige brontekst gecheckt (bron-modus); artikelen zónder
krijgen een interne consistentie-check (consistentie-modus).

Trappen:
    python3 verify-wiki.py --dry-run    # geen API-calls, tokentelling + kostenraming
    python3 verify-wiki.py --smoke      # 3 artikelen echt door de API, geen writes
    python3 verify-wiki.py              # volledige pass: rapport + frontmatter-flags

Output: rapport + state-file (JSONL, hervatbaar) in $VAULT/06-claude/.
Frontmatter-flag (alleen bij problemen): ``verify: issues`` + ``verify_date``.

Stdlib only. Key uit $OPENROUTER_API_KEY of --env-file.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _frontmatter import parse_frontmatter, split_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash"
DEFAULT_ENV_FILE = Path.home() / "Claude/projects/inspo-pipeline/.env"
# prijzen per token (USD), deepseek-v4-flash op OpenRouter d.d. 2026-07-01
PRICE_PROMPT = 0.09 / 1_000_000
PRICE_COMPLETION = 0.18 / 1_000_000
MAX_COMPLETION_TOKENS = 4000
CHARS_PER_TOKEN = 3.5  # ruwe schatting voor NL/EN gemengd markdown

RAW_LINK_RE = re.compile(r"\[\[([^\]|]*raw-sessie[^\]|]*)(?:\|[^\]]*)?\]\]")

SYSTEM_BRON = """Je bent een strenge factchecker voor een persoonlijke kennisbank. \
Je krijgt een wiki-artikel dat is gedestilleerd uit sessie-logs, plus de volledige tekst van die bron-logs. \
Beoordeel of de claims in het artikel gedekt worden door de bronnen. Let op:
- claims die nergens in de bronnen voorkomen (mogelijk gehallucineerd)
- overgeneralisatie: iets dat in één sessie gold, gepresenteerd als altijd waar
- tegenspraak: het artikel beweert het omgekeerde van de bron
- verkeerd samengevoegde feiten uit verschillende sessies
Negeer stijl, structuur en weglatingen; alleen feitelijke dekking telt. \
Navigatie-elementen, backlinks en frontmatter zijn geen claims.
BELANGRIJK: het artikel is een bewuste compilatie, geen citaat. Parafrase, samenvatting, \
herstructurering en het uitschrijven van een patroon dat de bron beknopt noemt zijn de bedoeling \
en zijn GEEN probleem. "Staat niet letterlijk in de bron" is op zichzelf nooit een bevinding. \
Rapporteer alleen: inhoud die de bron tegenspreekt, en concrete feiten, code, cijfers of \
beweringen die inhoudelijk nergens op de bron terug te voeren zijn.
Antwoord UITSLUITEND met geldig JSON, geen andere tekst, volgens dit schema:
{"verdict": "ok" | "issues", "claims": [{"citaat": "<letterlijk citaat uit het artikel>", "probleem": "<korte uitleg>", "type": "niet-gedekt" | "overgeneralisatie" | "tegenspraak" | "samensmelting", "ernst": "hoog" | "middel" | "laag"}]}
Bij verdict "ok" is "claims" een lege lijst. Rapporteer alleen echte problemen, geen muggenzifterij. \
Maximaal 8 claims (de belangrijkste eerst); houd citaten kort, maximaal 25 woorden, inkorten met … mag."""

SYSTEM_CONSISTENTIE = """Je bent een strenge factchecker voor een persoonlijke kennisbank. \
Je krijgt een wiki-artikel waarvan de bron-logs niet meer beschikbaar zijn; bronvergelijking is onmogelijk. \
Check daarom alleen de interne kwaliteit:
- interne tegenstrijdigheden binnen het artikel
- verdacht stellige, specifieke claims (exacte cijfers, versienummers, datums) die zonder bron onverifieerbaar zijn
Negeer stijl, structuur, navigatie-elementen en frontmatter.
Antwoord UITSLUITEND met geldig JSON, geen andere tekst, volgens dit schema:
{"verdict": "ok" | "issues", "claims": [{"citaat": "<letterlijk citaat uit het artikel>", "probleem": "<korte uitleg>", "type": "intern-inconsistent" | "onverifieerbaar-stellig", "ernst": "hoog" | "middel" | "laag"}]}
Bij verdict "ok" is "claims" een lege lijst. Rapporteer alleen echte problemen, geen muggenzifterij. \
Maximaal 8 claims (de belangrijkste eerst); houd citaten kort, maximaal 25 woorden, inkorten met … mag."""

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def load_api_key(env_file: Path) -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY="):
                return line.partition("=")[2].strip().strip("'\"")
    sys.exit(f"fout: OPENROUTER_API_KEY niet in env en niet gevonden in {env_file}")


def resolve_sources(body: str, vault: Path) -> tuple[list[Path], list[str]]:
    """Resolve [[raw-sessie-...]]-links naar bestanden in 01-raw/sessies/."""
    found: list[Path] = []
    missing: list[str] = []
    seen: set[str] = set()
    for target in RAW_LINK_RE.findall(body):
        name = target.rsplit("/", 1)[-1].strip()
        if not name.endswith(".md"):
            name += ".md"
        if name in seen:
            continue
        seen.add(name)
        p = vault / "01-raw/sessies" / name
        if p.is_file():
            found.append(p)
        else:
            missing.append(name)
    return found, missing


def collect_articles(vault: Path) -> list[dict]:
    """Inventariseer alle wiki-artikelen met hun modus en bronbestanden."""
    items = []
    for f in sorted((vault / "02-wiki").glob("*.md")):
        text = f.read_text(encoding="utf-8")
        _, body = parse_frontmatter(text)
        sources, missing = resolve_sources(body, vault)
        mode = "bron" if sources else "consistentie"
        src_chars = sum(len(p.read_text(encoding="utf-8")) for p in sources)
        items.append({
            "path": f,
            "name": f.name,
            "mode": mode,
            "sources": sources,
            "missing_sources": missing,
            "prompt_chars": len(text) + src_chars,
        })
    return items


def build_messages(item: dict) -> list[dict]:
    article = item["path"].read_text(encoding="utf-8")
    if item["mode"] == "bron":
        parts = [f"## ARTIKEL: {item['name']}\n\n{article}\n"]
        for p in item["sources"]:
            parts.append(f"\n## BRON-LOG: {p.name}\n\n{p.read_text(encoding='utf-8')}\n")
        if item["missing_sources"]:
            parts.append(
                "\n(Niet meer beschikbare bron-logs, niet meegeleverd: "
                + ", ".join(item["missing_sources"]) + ")"
            )
        return [
            {"role": "system", "content": SYSTEM_BRON},
            {"role": "user", "content": "".join(parts)},
        ]
    return [
        {"role": "system", "content": SYSTEM_CONSISTENTIE},
        {"role": "user", "content": f"## ARTIKEL: {item['name']}\n\n{article}"},
    ]


def parse_verdict(raw: str) -> dict:
    """Parse het modelantwoord; accepteert code fences eromheen."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\s*|\s*```$", "", text, flags=re.IGNORECASE)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("geen JSON-object in antwoord")
    data = json.loads(text[start:end + 1])
    if data.get("verdict") not in ("ok", "issues"):
        raise ValueError(f"ongeldig verdict: {data.get('verdict')!r}")
    if not isinstance(data.get("claims"), list):
        raise ValueError("claims is geen lijst")
    return data


def call_model(api_key: str, model: str, messages: list[dict]) -> tuple[str, dict]:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": MAX_COMPLETION_TOKENS,
        # v4-flash is een reasoning-model; zonder dit verbrandt het zijn
        # tokenbudget aan denk-tokens en blijft content leeg
        "reasoning": {"enabled": False},
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(API_URL, data=payload, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/rvdbreemen/LLmWiki-KennisBank",
        "X-Title": "KennisBank verify-pass",
    })
    last_err: Exception = RuntimeError("geen poging gedaan")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            choice = data["choices"][0]
            content = choice["message"].get("content")
            if not content:
                raise ValueError(
                    f"lege content (finish_reason={choice.get('finish_reason')!r})"
                )
            return content, data.get("usage", {})
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt * 3)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            if attempt < 3:
                time.sleep(2 ** attempt * 3)
                continue
            raise
    raise last_err


def verify_article(item: dict, api_key: str, model: str) -> dict:
    """Eén artikel verifiëren; ongeldig JSON wordt éénmaal opnieuw gevraagd."""
    messages = build_messages(item)
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0}
    record = {
        "name": item["name"],
        "mode": item["mode"],
        "sources": [p.name for p in item["sources"]],
        "missing_sources": item["missing_sources"],
    }
    try:
        content, usage = call_model(api_key, model, messages)
        for k in usage_total:
            usage_total[k] += usage.get(k, 0) or 0
        try:
            verdict = parse_verdict(content)
        except (ValueError, json.JSONDecodeError):
            retry_messages = messages + [
                {"role": "assistant", "content": content},
                {"role": "user", "content": "Dat was geen geldig JSON volgens het schema. Antwoord opnieuw met uitsluitend het JSON-object."},
            ]
            content, usage = call_model(api_key, model, retry_messages)
            for k in usage_total:
                usage_total[k] += usage.get(k, 0) or 0
            verdict = parse_verdict(content)
        record.update(verdict=verdict["verdict"], claims=verdict["claims"])
    except Exception as e:  # per-artikel isoleren: één kapotte call stopt de run niet
        record.update(verdict="error", claims=[], error=f"{type(e).__name__}: {e}")
    record["usage"] = usage_total
    return record


def flag_frontmatter(path: Path, today: str) -> None:
    """Zet verify: issues + verify_date in de frontmatter, body onaangetast."""
    text = path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    lines = [
        ln for ln in fm.splitlines()
        if not re.match(r"^\s*verify(_date)?\s*:", ln)
    ] if fm else []
    lines += [f"verify: issues", f"verify_date: {today}"]
    path.write_text("---\n" + "\n".join(lines) + "\n---\n" + body, encoding="utf-8")


def load_state(state_file: Path) -> dict[str, dict]:
    done: dict[str, dict] = {}
    if state_file.is_file():
        for line in state_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["name"]] = rec
    return done


def write_report(records: list[dict], report_file: Path, model: str, today: str) -> None:
    by_verdict = {"issues": [], "ok": [], "error": []}
    for r in records:
        by_verdict[r["verdict"]].append(r)
    prompt_t = sum(r["usage"]["prompt_tokens"] for r in records)
    compl_t = sum(r["usage"]["completion_tokens"] for r in records)
    cost = prompt_t * PRICE_PROMPT + compl_t * PRICE_COMPLETION

    out = [
        "---",
        "type: rapport",
        f"created: {today}",
        "tags: [verify, kwaliteit]",
        "---",
        "",
        f"# Verify-rapport {today}",
        "",
        f"Model: `{model}` via OpenRouter. Artikelen: {len(records)} "
        f"(bron-modus: {sum(1 for r in records if r['mode'] == 'bron')}, "
        f"consistentie-modus: {sum(1 for r in records if r['mode'] == 'consistentie')}).",
        f"Verdicts: **{len(by_verdict['issues'])} issues**, {len(by_verdict['ok'])} ok, "
        f"{len(by_verdict['error'])} error.",
        f"Tokens: {prompt_t:,} prompt + {compl_t:,} completion ≈ ${cost:.3f}.",
        "",
    ]
    ernst_orde = {"hoog": 0, "middel": 1, "laag": 2}
    for mode, kop in (("bron", "## Issues (bron-verificatie)"),
                      ("consistentie", "## Issues (consistentie-check, geen bron beschikbaar)")):
        rows = [r for r in by_verdict["issues"] if r["mode"] == mode]
        out.append(kop)
        out.append("")
        if not rows:
            out += ["Geen.", ""]
        for r in rows:
            out.append(f"### [[{r['name'].removesuffix('.md')}]]")
            if r["missing_sources"]:
                out.append(f"*Ontbrekende bron-logs: {', '.join(r['missing_sources'])}*")
            out.append("")
            for c in sorted(r["claims"], key=lambda c: ernst_orde.get(c.get("ernst", "laag"), 3)):
                out.append(f"- **[{c.get('ernst', '?')} / {c.get('type', '?')}]** "
                           f"“{c.get('citaat', '')}” — {c.get('probleem', '')}")
            out.append("")
    if by_verdict["error"]:
        out += ["## Errors", ""]
        for r in by_verdict["error"]:
            out.append(f"- [[{r['name'].removesuffix('.md')}]] — {r.get('error', '?')}")
        out.append("")
    out += ["## Ok", ""]
    out.append(", ".join(f"[[{r['name'].removesuffix('.md')}]]" for r in by_verdict["ok"]) or "Geen.")
    out.append("")
    report_file.write_text("\n".join(out), encoding="utf-8")


def dry_run(items: list[dict]) -> None:
    total_prompt_t = 0
    for it in items:
        total_prompt_t += int(it["prompt_chars"] / CHARS_PER_TOKEN) + 400  # + systeemprompt
    compl_t = len(items) * 500
    cost = total_prompt_t * PRICE_PROMPT + compl_t * PRICE_COMPLETION
    bron = [it for it in items if it["mode"] == "bron"]
    cons = [it for it in items if it["mode"] == "consistentie"]
    missing = [it for it in items if it["missing_sources"]]
    print(f"artikelen:            {len(items)}")
    print(f"  bron-modus:         {len(bron)}")
    print(f"  consistentie-modus: {len(cons)}")
    print(f"  met ontbrekende bronlinks: {len(missing)}")
    for it in missing:
        print(f"    - {it['name']}: {', '.join(it['missing_sources'])}")
    print(f"geschatte prompt-tokens:     {total_prompt_t:,}")
    print(f"geschatte completion-tokens: {compl_t:,}")
    print(f"geschatte kosten:            ${cost:.3f}")
    grootste = max(items, key=lambda it: it["prompt_chars"])
    print(f"grootste prompt: {grootste['name']} "
          f"(~{int(grootste['prompt_chars'] / CHARS_PER_TOKEN):,} tokens)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="geen API-calls, alleen raming")
    ap.add_argument("--smoke", action="store_true", help="3 artikelen, geen writes")
    ap.add_argument("--limit", type=int, help="max aantal artikelen (test)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--no-flag", action="store_true", help="geen frontmatter-writes")
    args = ap.parse_args()

    vault = vault_root()
    today = date.today().isoformat()
    items = collect_articles(vault)

    if args.dry_run:
        dry_run(items)
        return

    api_key = load_api_key(args.env_file)

    if args.smoke:
        bron = [it for it in items if it["mode"] == "bron"][:2]
        cons = [it for it in items if it["mode"] == "consistentie"][:1]
        picked = bron + cons
        log(f"smoketest: {', '.join(it['name'] for it in picked)}")
        for it in picked:
            rec = verify_article(it, api_key, args.model)
            log(json.dumps(rec, ensure_ascii=False, indent=2))
        return

    if args.limit:
        items = items[:args.limit]

    out_dir = vault / "06-claude"
    out_dir.mkdir(exist_ok=True)
    state_file = out_dir / f"verify-state-{today}.jsonl"
    report_file = out_dir / f"verify-report-{today}.md"

    done = load_state(state_file)
    todo = [it for it in items if it["name"] not in done]
    log(f"te doen: {len(todo)} van {len(items)} (al in state: {len(done)})")

    state_lock = threading.Lock()
    counter = {"n": 0}

    def worker(it: dict) -> dict:
        rec = verify_article(it, api_key, args.model)
        with state_lock:
            with state_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            counter["n"] += 1
            n = counter["n"]
        tag = rec["verdict"].upper() if rec["verdict"] != "ok" else "ok"
        log(f"[{n}/{len(todo)}] {tag:7s} {rec['name']}"
            + (f"  ({len(rec['claims'])} claims)" if rec["claims"] else ""))
        return rec

    if todo:
        with ThreadPoolExecutor(max_workers=args.threads) as ex:
            list(ex.map(worker, todo))

    records = list(load_state(state_file).values())
    records.sort(key=lambda r: r["name"])
    write_report(records, report_file, args.model, today)
    log(f"\nrapport: {report_file}")

    if not args.no_flag:
        flagged = 0
        for r in records:
            # alleen flaggen bij claims die ertoe doen; laag-ernst blijft rapport-only
            if r["verdict"] == "issues" and any(
                c.get("ernst") in ("hoog", "middel") for c in r["claims"]
            ):
                flag_frontmatter(vault / "02-wiki" / r["name"], today)
                flagged += 1
        log(f"frontmatter-flags gezet (ernst middel/hoog): {flagged}")


if __name__ == "__main__":
    main()
