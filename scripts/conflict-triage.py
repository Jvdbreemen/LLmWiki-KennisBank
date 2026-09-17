#!/usr/bin/env python3
"""Conflict-triage: beoordeel conflict-scan-kandidaatparen op echte tegenspraak via OpenRouter.

Leest de JSON-uitvoer van conflict-scan.py, stuurt per paar beide volledige
artikelen naar een onafhankelijk model en vraagt een streng ja/nee-oordeel:
is er een FEITELIJKE tegenspraak (beide artikelen doen over hetzelfde een
bewering die niet allebei waar kan zijn)? Semantische overlap is geen conflict.

Gebruik:
    python3 conflict-triage.py pairs.json                # volledige triage
    python3 conflict-triage.py pairs.json --limit 10     # ijkset/test
    python3 conflict-triage.py pairs.json --dry-run      # raming, geen calls

Output: state-file (JSONL, hervatbaar) + markdown-rapport in $VAULT/06-claude/.
De beslissing (welke claim survives) blijft aan de gebruiker; dit script
filtert alleen de paren die een beslissing waard zijn.

Stdlib only. Key uit $OPENROUTER_API_KEY of --env-file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _llmjson  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash"
DEFAULT_ENV_FILE = Path.home() / "Claude/projects/inspo-pipeline/.env"
PRICE_PROMPT = 0.09 / 1_000_000
PRICE_COMPLETION = 0.18 / 1_000_000
MAX_COMPLETION_TOKENS = 4000
CHARS_PER_TOKEN = 3.5

SYSTEM = """Je beoordeelt twee wiki-artikelen uit dezelfde persoonlijke kennisbank op FEITELIJKE tegenspraak. \
Een tegenspraak betekent: beide artikelen doen over hetzelfde onderwerp een bewering die niet allebei waar kan zijn \
(ander pad, andere conclusie, andere werking, tegengestelde aanbeveling over hetzelfde).
GEEN tegenspraak zijn: semantische overlap, verschillend detailniveau, complementaire invalshoeken, \
verschillende scenario's of contexten, stijlverschillen, meetverschillen, of een artikel dat een ander samenvat. \
Wees streng: bij twijfel is het antwoord false.
Antwoord UITSLUITEND met geldig JSON volgens dit schema:
{"tegenspraak": true | false, "citaat_a": "<letterlijke tegenstrijdige passage uit artikel A, max 40 woorden, leeg bij false>", "citaat_b": "<idem uit B>", "toelichting": "<1-2 zinnen: wat spreekt elkaar tegen, of kort waarom niet>", "advies": "A" | "B" | null}
"advies" is welke claim correct lijkt (recenter, beter onderbouwd); null bij tegenspraak=false."""

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


def pair_key(p: dict) -> str:
    a, b = sorted([Path(p["path_a"]).name, Path(p["path_b"]).name])
    return f"{a}|{b}"


def call_model(api_key: str, model: str, messages: list[dict]) -> tuple[str, dict]:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": MAX_COMPLETION_TOKENS,
        "reasoning": {"enabled": False},
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(API_URL, data=payload, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/rvdbreemen/LLmWiki-KennisBank",
        "X-Title": "KennisBank conflict-triage",
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


def parse_verdict(raw: str) -> dict:
    # Het eerste complete object, niet het stuk van de eerste "{" tot de
    # laatste "}": een opmerking met accolades na het antwoord maakt dat stuk
    # ongeldig en gooit een betaald oordeel weg (TASK-189, _llmjson).
    data = _llmjson.first_object(raw)
    if data is None:
        raise ValueError("geen JSON-object in antwoord")
    if not isinstance(data.get("tegenspraak"), bool):
        raise ValueError(f"ongeldig tegenspraak-veld: {data.get('tegenspraak')!r}")
    return data


def triage_pair(pair: dict, api_key: str, model: str) -> dict:
    pa, pb = Path(pair["path_a"]), Path(pair["path_b"])
    user = (
        f"## ARTIKEL A: {pa.name} (updated: {pair.get('updated_a', '?')})\n\n"
        f"{pa.read_text(encoding='utf-8')}\n\n"
        f"## ARTIKEL B: {pb.name} (updated: {pair.get('updated_b', '?')})\n\n"
        f"{pb.read_text(encoding='utf-8')}"
    )
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": user}]
    record = {
        "key": pair_key(pair),
        "a": pa.name, "b": pb.name,
        "updated_a": pair.get("updated_a"), "updated_b": pair.get("updated_b"),
        "signal": pair.get("signal"),
    }
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0}
    try:
        content, usage = call_model(api_key, model, messages)
        for k in usage_total:
            usage_total[k] += usage.get(k, 0) or 0
        try:
            verdict = parse_verdict(content)
        except (ValueError, json.JSONDecodeError):
            retry = messages + [
                {"role": "assistant", "content": content},
                {"role": "user", "content": "Dat was geen geldig JSON volgens het schema. Antwoord opnieuw met uitsluitend het JSON-object."},
            ]
            content, usage = call_model(api_key, model, retry)
            for k in usage_total:
                usage_total[k] += usage.get(k, 0) or 0
            verdict = parse_verdict(content)
        record.update(
            tegenspraak=verdict["tegenspraak"],
            citaat_a=verdict.get("citaat_a", ""),
            citaat_b=verdict.get("citaat_b", ""),
            toelichting=verdict.get("toelichting", ""),
            advies=verdict.get("advies"),
        )
    except Exception as e:
        record.update(tegenspraak=None, error=f"{type(e).__name__}: {e}")
    record["usage"] = usage_total
    return record


def load_state(state_file: Path) -> dict[str, dict]:
    done: dict[str, dict] = {}
    if state_file.is_file():
        for line in state_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["key"]] = rec
    return done


def write_report(records: list[dict], report_file: Path, model: str, today: str) -> None:
    conflicts = [r for r in records if r.get("tegenspraak") is True]
    errors = [r for r in records if r.get("tegenspraak") is None]
    prompt_t = sum(r["usage"]["prompt_tokens"] for r in records)
    compl_t = sum(r["usage"]["completion_tokens"] for r in records)
    cost = prompt_t * PRICE_PROMPT + compl_t * PRICE_COMPLETION
    out = [
        "---", "type: rapport", f"created: {today}",
        "tags: [reconcile, triage]", "---", "",
        f"# Conflict-triage {today}", "",
        f"Model: `{model}` via OpenRouter. Paren: {len(records)}; "
        f"**{len(conflicts)} echte tegenspraak**, "
        f"{len(records) - len(conflicts) - len(errors)} geen conflict, {len(errors)} error.",
        f"Tokens: {prompt_t:,} prompt + {compl_t:,} completion ≈ ${cost:.2f}.", "",
        "## Tegenspraken", "",
    ]
    conflicts.sort(key=lambda r: -(r.get("signal") or 0))
    for r in conflicts:
        out += [
            f"### [[{r['a'].removesuffix('.md')}]] <> [[{r['b'].removesuffix('.md')}]]",
            f"- A ({r['updated_a']}): “{r['citaat_a']}”",
            f"- B ({r['updated_b']}): “{r['citaat_b']}”",
            f"- {r['toelichting']} Advies: {r['advies'] or 'geen'}.",
            "",
        ]
    if errors:
        out += ["## Errors", ""]
        out += [f"- {r['a']} <> {r['b']}: {r.get('error')}" for r in errors]
        out.append("")
    report_file.write_text("\n".join(out), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pairs", type=Path, help="JSON-uitvoer van conflict-scan.py")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--skip", type=int, default=0, help="eerste N paren overslaan")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()

    vault = vault_root()
    today = date.today().isoformat()
    pairs = json.loads(args.pairs.read_text(encoding="utf-8"))
    pairs.sort(key=lambda p: -(p.get("signal") or 0))
    pairs = pairs[args.skip:]
    if args.limit:
        pairs = pairs[:args.limit]

    if args.dry_run:
        chars = sum(
            Path(p["path_a"]).stat().st_size + Path(p["path_b"]).stat().st_size
            for p in pairs
        )
        prompt_t = int(chars / CHARS_PER_TOKEN) + len(pairs) * 300
        compl_t = len(pairs) * 150
        cost = prompt_t * PRICE_PROMPT + compl_t * PRICE_COMPLETION
        print(f"paren: {len(pairs)}")
        print(f"geschatte prompt-tokens: {prompt_t:,}")
        print(f"geschatte kosten: ${cost:.2f}")
        return

    api_key = load_api_key(args.env_file)
    out_dir = vault / "06-claude"
    out_dir.mkdir(exist_ok=True)
    state_file = out_dir / f"triage-state-{today}.jsonl"
    report_file = out_dir / f"triage-report-{today}.md"

    done = load_state(state_file)
    todo = [p for p in pairs if pair_key(p) not in done]
    log(f"te doen: {len(todo)} van {len(pairs)} (al in state: {len(done)})")

    state_lock = threading.Lock()
    counter = {"n": 0, "conflict": 0}

    def worker(pair: dict) -> None:
        rec = triage_pair(pair, api_key, args.model)
        with state_lock:
            with state_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            counter["n"] += 1
            if rec.get("tegenspraak") is True:
                counter["conflict"] += 1
            n, c = counter["n"], counter["conflict"]
        tag = {True: "CONFLICT", False: "ok", None: "ERROR"}[rec.get("tegenspraak")]
        log(f"[{n}/{len(todo)}] {tag:8s} {rec['a']} <> {rec['b']}  (conflicten: {c})")

    if todo:
        with ThreadPoolExecutor(max_workers=args.threads) as ex:
            list(ex.map(worker, todo))

    records = [r for r in load_state(state_file).values()
               if r["key"] in {pair_key(p) for p in pairs}]
    write_report(records, report_file, args.model, today)
    log(f"\nrapport: {report_file}")


if __name__ == "__main__":
    main()
