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

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
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
    return out


def rot_count(hours: int = 48) -> int:
    mdir = vault_root() / "09-memory"
    if not mdir.exists():
        return 0
    cutoff = date.today() - timedelta(hours=hours)
    n = 0
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
            n += 1
    return n


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
        print(rot_count(hours))
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
    print("usage: memory-doctor.py nocloud|rot [--hours N]|rejudge [--limit N] [--hours N] [--dry-run]",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
