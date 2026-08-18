#!/usr/bin/env python3
"""memory-doctor.py - deterministische gezondheidschecks voor het geheugen.

Checks + onderhoud, aangeroepen door doctor.sh en handmatig:
  nocloud  - waarschuw als de actieve _llm-keten cloud bevat OF de Ollama-endpoint
             niet lokaal is (is_local() is naam-gebaseerd; endpoint apart checken).
  rot      - tel unverified memories ouder dan N uur (hangende judge/sweep).
  rejudge  - her-judge de fail-safe-unverified backlog en promoot naar current bij
             een expliciet 'current'-verdict (fail-safe; na een LLM-outage). Draai
             daarna build-kb-index zodat de gepromote memories recallbaar worden.

Fail-soft: ontbrekende vault/config -> geen waarschuwing / 0. nocloud/rot zijn
stdlib-only; rejudge gebruikt de _judge/_memory-seams (zelf fail-safe).
"""
from __future__ import annotations

import ipaddress
import os
import sys
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _llm  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402


def _is_local_endpoint(ep: str) -> bool:
    """Return True iff ep resolves to a loopback address.

    Uses strict hostname parsing (urllib.parse) + ipaddress.is_loopback to
    prevent naive substring bypasses such as http://localhost.evil.com or
    127.0.0.1 appearing in a query-string.
    """
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


def cloud_warnings() -> list:
    out = []
    try:
        chain = _llm.providers()
    except Exception:
        return out
    cloud = [p for p in chain if p in _llm.CLOUD_PROVIDERS]
    if cloud:
        out.append(f"LLM-keten bevat cloud-provider(s): {', '.join(cloud)} "
                   f"- content kan je machine verlaten (#4)")
    # endpoint-check: wanneer ollama ERGENS in de keten zit (ook niet-eerste positie)
    # kan het bij een remote endpoint data buiten de machine sturen (#4).
    if "ollama" in chain:
        try:
            ep = _llm._endpoint("ollama")
        except Exception:
            ep = ""
        if ep and not _is_local_endpoint(ep):
            out.append(f"Ollama-endpoint is niet lokaal ({ep}) - embeddings/generatie "
                       f"verlaten je machine (#4)")
    # De EMBED-keten is een tweede, losse configuratie (kennisbank-embed.json) en
    # werd hier niet gecontroleerd. Juist die staat op de hot path: kb-retrieve
    # stuurt elke prompt door emb.embed(). Een niet-lokaal endpoint daar is
    # precies het lek dat deze functie hoort te melden.
    try:
        import _embeddings as _emb
        prov, _model, ep, _key = _emb._resolve()
    except Exception:
        prov, ep = "", ""
    if prov and ep:
        if prov in _emb.LOCAL_ONLY_PROVIDERS and not _is_local_endpoint(ep):
            out.append(f"Embed-endpoint is niet lokaal ({ep}) bij provider '{prov}' "
                       f"- elke prompt en de hele vault verlaten je machine (#4)")
        elif prov not in _emb.LOCAL_ONLY_PROVIDERS:
            out.append(f"Embed-provider '{prov}' is cloud - tekst verlaat je "
                       f"machine (#4)")
    return out


def rot_breakdown(hours: int = 48) -> dict:
    """De rot-telling, gesplitst naar wat hem nog kan verplaatsen.

    `waiting` is nooit met een beslissend verdict teruggekomen -- dat is een
    vraag over de sweep of het model. `undecided` is wel beoordeeld en bleef
    unverified, en daar komt geen automatisch pad meer aan te pas: trap 1
    promoot alleen `supported` en trap 2 past alleen `supported`/`absent`
    toe, dus `partial` en `unclear` blijven eeuwig liggen (TASK-198). Alleen
    een mens verplaatst die nog, via `memory-doctor.py pending` gevolgd door
    `decide <stem> approve|reject|skip`. NIET via /kennisbank:review: dat
    commando is de audit-view en kan alleen `demote` en `reopen`, en een
    unverified memory staat in geen van beide logboeken die het leest.

    Eén telling gaf één advies, en op de vault die dit blootlegde was dat
    advies fout: alle 24 rottende memories waren al beoordeeld, terwijl de
    melding naar Ollama en de instellingen wees.
    """
    out = {"total": 0, "waiting": 0, "undecided": 0}
    mdir = vault_root() / "09-memory"
    if not mdir.exists():
        return out
    try:
        import _groundcheck
        judged, key_of = _groundcheck.load_attempts(), _groundcheck.attempt_key
        settled, verdicts = _groundcheck.is_settled, _groundcheck.VERDICTS
    except Exception:
        judged, key_of = {}, (lambda p: "")
        settled, verdicts = (lambda rec: False), ()
    # `created` in de frontmatter is een DATUM, niet een tijdstip. Een drempel in
    # uren kan hier dus nooit fijner werken dan een hele dag. Dat was verstopt:
    # `date.today() - timedelta(hours=36)` gooit de restfractie stilzwijgend weg
    # en levert 1 dag, en onder de 24 uur zelfs 0 -- dan telde de check feitelijk
    # 'ouder dan vandaag'. Expliciet naar dagen afronden, met een ondergrens van
    # 1, maakt de granulariteit zichtbaar in plaats van hem te verbergen. Bij de
    # gebruikte 48 uur verandert er niets (2 dagen, zoals voorheen).
    cutoff = date.today() - timedelta(days=max(1, hours // 24))
    for f in mdir.glob("**/*.md"):
        try:
            fm, _ = parse_frontmatter(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if fm.get("status") != "unverified":
            continue
        created = fm.get("created", "")
        try:
            d = datetime.fromisoformat(created).date() if created else date.today()
        except Exception:
            continue
        if d < cutoff:
            out["total"] += 1
            rec = judged.get(key_of(f))
            # Undecided means BOTH: trap 1 will not return to it on its own,
            # AND what it returned was a judgement about the claim. An
            # inconclusive outcome (`no_transcript`, `unparseable`) says the
            # source is broken or the run was, which is not something a person
            # can decide -- that belongs in waiting, where the advice is right.
            decided = settled(rec) and str(rec.get("verdict", "")) in verdicts
            out["undecided" if decided else "waiting"] += 1
    return out


def rot_count(hours: int = 48) -> int:
    return rot_breakdown(hours)["total"]


def rejudge_pass(judge_fn=None, limit=None, hours=None, dry_run=False) -> dict:
    """Her-judge de unverified memories en promoot naar 'current' ALLEEN bij een
    expliciet 'current'-verdict. FAIL-SAFE: twijfel, model-down of een
    unverified-verdict laat de memory unverified; nooit retracten, nooit ruis
    promoten. Bedoeld om na een LLM/Ollama-outage de fail-safe-unverified backlog
    op te schonen (de capture-judge zet bij twijfel op unverified).

    hours: alleen unverified ouder dan N uur (zoals rot_count); None = alle.
    limit: verwerk hooguit N. dry_run: tel maar schrijf niet.
    Return: {"promoted", "kept", "failed"}. judge_fn injecteerbaar voor tests;
    default is _judge.judge (zelf fail-safe bij een dode judge)."""
    import _memory
    if judge_fn is None:
        import _judge
        judge_fn = _judge.judge
    res = {"promoted": 0, "kept": 0, "failed": 0}
    mdir = vault_root() / "09-memory"
    if not mdir.exists():
        return res
    cutoff = (date.today() - timedelta(hours=hours)) if hours is not None else None
    targets = []
    for f in sorted(mdir.glob("**/*.md")):
        try:
            fm, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if fm.get("status") != "unverified":
            continue
        if cutoff is not None:
            created = fm.get("created", "")
            try:
                d = datetime.fromisoformat(created).date() if created else date.today()
            except Exception:
                continue
            if not (d < cutoff):
                continue
        targets.append((f, body.strip()))
    if limit is not None:
        targets = targets[:limit]
    for f, body in targets:
        try:
            verdict = (judge_fn(body) or {}).get("verdict")
        except Exception:
            res["failed"] += 1
            continue
        if verdict == "current":
            if dry_run or _memory.set_status(f, "current"):
                res["promoted"] += 1
        else:
            res["kept"] += 1
    return res


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] == "nocloud":
        for w in cloud_warnings():
            print(w)
        return 0
    if argv and argv[0] == "rot":
        hours = 48
        if "--hours" in argv:
            try:
                hours = int(argv[argv.index("--hours") + 1])
            except Exception:
                hours = 48
        # --json geeft de splitsing die rot_breakdown() al kende maar die geen
        # enkele consument kon bereiken: `rot` printte alleen het totaal, dus
        # doctor.sh moest wel een oorzaak verzinnen bij een getal dat er twee
        # bevatte (TASK-200). Het kale `rot` blijft het totaal printen -- dat
        # is een bestaand contract, en een shell die alleen "is er rot?" vraagt
        # hoeft niet te leren JSON te lezen.
        if "--json" in argv:
            import json as _json
            print(_json.dumps(rot_breakdown(hours), sort_keys=True))
            return 0
        print(rot_count(hours))
        return 0
    if argv and argv[0] == "closed":
        # Wat is er dichtgezet, en waardoor. De reviewwachtrij loopt alleen
        # `unverified`, en recall filtert op `current`, dus een gesloten memory
        # verscheen tot nu toe NERGENS meer -- functioneel hetzelfde als
        # verwijderd, terwijl het ontwerp leunt op "het is omkeerbaar"
        # (TASK-150).
        import json as _json
        import _memory
        limit = 20
        if "--limit" in argv:
            try:
                limit = int(argv[argv.index("--limit") + 1])
            except Exception:
                limit = 20
        rows = _memory.recent_closures(limit=limit)
        if "--json" in argv:
            print(_json.dumps(rows, ensure_ascii=False))
        elif not rows:
            print("geen sluitingen geregistreerd")
        else:
            for r in rows:
                door = ", ".join(r.get("superseded_by") or []) or "-"
                print(f"{r.get('ts','')[:19]}  {r.get('status',''):<12} {r.get('stem','')}")
                print(f"    vervangen door: {door}")
                if r.get("reason"):
                    print(f"    reden: {r['reason']}")
            print(f"\nHeropenen: python3 memory-doctor.py reopen <stem>")
        return 0
    if argv and argv[0] == "discarded":
        # De tegenhanger van `closed`, een stap eerder in de pijplijn. Een NOOP
        # gooit de kandidaat weg voordat hij ooit een bestand wordt, dus er is
        # niets om te heropenen -- alleen om te LEZEN, en te zien of de seam
        # kennis weggooit die je had willen houden (TASK-155).
        import json as _json
        import _memory
        limit = 20
        if "--limit" in argv:
            try:
                limit = int(argv[argv.index("--limit") + 1])
            except Exception:
                limit = 20
        rows = _memory.recent_discards(limit=limit)
        if "--json" in argv:
            print(_json.dumps(rows, ensure_ascii=False))
        elif not rows:
            print("geen weggegooide kandidaten geregistreerd")
        else:
            for r in rows:
                print(f"{r.get('ts','')[:19]}  {r.get('title','')}")
                print(f"    gedekt door: {r.get('covered_by') or '?'}"
                      f"   promptversie: {r.get('prompt_version')}")
                body = " ".join(str(r.get("body", "")).split())
                print(f"    {body[:160]}")
            print("\nDeze kandidaten zijn NIET geschreven; "
                  "er is niets te heropenen.")
        return 0
    if argv and argv[0] == "promotions":
        # De andere helft van de audit-view naast `closed`: wat is er
        # autonoom gepromoveerd, langs welke route, en op welk bewijs. Sinds
        # TASK-195 zit er geen mens meer in de promotielus, dus dit logboek
        # IS de review — achteraf, met `demote <stem>` als terugweg.
        import json as _json
        import _memory
        limit = 20
        if "--limit" in argv:
            try:
                limit = int(argv[argv.index("--limit") + 1])
            except Exception:
                limit = 20
        rows = _memory.recent_promotions(limit=limit)
        if "--json" in argv:
            print(_json.dumps(rows, ensure_ascii=False))
        elif not rows:
            print("geen promoties geregistreerd")
        else:
            for r in rows:
                act = "DEMOTE " if r.get("action") == "demote" else ""
                print(f"{r.get('at','')[:19]}  {act}{r.get('stem','')}"
                      f"  [{r.get('route','?')}/{r.get('prompt_version') or '-'}]")
                if r.get("reason"):
                    reason = " ".join(str(r["reason"]).split())
                    print(f"    bewijs: {reason[:160]}")
            print(f"\nTerugdraaien: python3 memory-doctor.py demote <stem>")
        return 0
    if argv and argv[0] == "demote":
        import _memory
        if len(argv) < 2:
            print("gebruik: memory-doctor.py demote <stem>", file=sys.stderr)
            return 2
        stem = argv[1]
        path = _memory.memory_dir() / f"{stem}.md"
        if not path.exists():
            print(f"niet gevonden: {path}", file=sys.stderr)
            return 1
        if _memory.demote(path, reason="handmatig teruggedraaid via audit-view"):
            print(f"{stem} -> unverified (promotie teruggedraaid)")
            print("Draai build-kb-index zodat recall de wijziging ziet.")
            return 0
        print(f"{stem}: niets gewijzigd (status is niet current)", file=sys.stderr)
        return 1
    if argv and argv[0] == "reopen":
        import _memory
        if len(argv) < 2:
            print("gebruik: memory-doctor.py reopen <stem>", file=sys.stderr)
            return 2
        stem = argv[1]
        path = _memory.memory_dir() / f"{stem}.md"
        if not path.exists():
            print(f"niet gevonden: {path}", file=sys.stderr)
            return 1
        if _memory.reopen(path):
            print(f"{stem} -> current (superseded_by en valid_until verwijderd)")
            print("Draai build-kb-index zodat de memory weer recallbaar is.")
            return 0
        print(f"{stem}: niets gewijzigd (al open?)", file=sys.stderr)
        return 1
    if argv and argv[0] == "pending":
        import json as _json
        import _memory
        limit = None
        if "--limit" in argv:
            try:
                limit = int(argv[argv.index("--limit") + 1])
            except Exception:
                limit = None
        items = _memory.pending_reviews(limit=limit)
        if "--json" in argv:
            print(_json.dumps(items, ensure_ascii=False))
        elif not items:
            print("review-queue leeg: geen unverified memories")
        else:
            for it in items:
                age = f"{it['age_days']}d" if it["age_days"] is not None else "?"
                print(f"{it['stem']}  [{it['memory_type']}/{it['importance']}] "
                      f"({age}, {it['evidence_basis']}) {it['title']}")
        return 0
    if argv and argv[0] == "decide":
        import _memory
        if len(argv) < 3:
            print("usage: memory-doctor.py decide <stem> <approve|reject|skip>",
                  file=sys.stderr)
            return 2
        via = "cli"
        if "--via" in argv:
            try:
                via = argv[argv.index("--via") + 1]
            except Exception:
                via = "cli"
        try:
            r = _memory.decide(argv[1], argv[2], via=via)
        except _memory.ReviewError as exc:
            print(f"decide: {exc} (code {exc.code})", file=sys.stderr)
            return 1
        print(f"decide: {r['stem']} -> {r['new_status']}"
              + (" (skipped)" if r["status"] == "skipped" else ""))
        return 0
    if argv and argv[0] == "rejudge":
        kw = {"dry_run": "--dry-run" in argv}
        for flag in ("--limit", "--hours"):
            if flag in argv:
                try:
                    kw[flag[2:]] = int(argv[argv.index(flag) + 1])
                except Exception:
                    pass
        r = rejudge_pass(**kw)
        print(f"rejudge: promoted={r['promoted']} kept={r['kept']} failed={r['failed']}"
              + (" (dry-run)" if kw["dry_run"] else ""))
        return 0
    print("usage: memory-doctor.py nocloud|rot [--hours N]|rejudge [--limit N] [--hours N] [--dry-run]"
          "|pending [--json] [--limit N]|decide <stem> <approve|reject|skip>"
          "|closed [--json] [--limit N]|reopen <stem>|discarded [--json] [--limit N]"
          "|promotions [--json] [--limit N]|demote <stem>",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
