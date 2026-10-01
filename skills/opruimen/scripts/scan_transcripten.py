#!/usr/bin/env python3
"""Laatste prompt per Claude Code-transcript, met stilte-uren, kaart en proces.

Gebruik:  scan_transcripten.py [--dagen N] [--sid <uuid>]

Standaard de laatste 3 dagen, gesorteerd op de laatste echte prompt. Tijden zijn
UTC: de timestamp-velden in het transcript zijn UTC en de bestands-mtime is lokaal,
dus mengen levert een schijnverschil van twee uur op.

De transcriptmap komt uit CC_PROJECTS (default ~/.claude/projects). Op een
machine zonder Claude Code bestaat die map niet; dan is dit script een no-op en
vindt het 0 transcripten. De CCD-kaarten staan in de sidebar-map van de app
(~/Library/Application Support/Claude/claude-code-sessions/ op macOS); ook die is
optioneel.
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import subprocess

# Claude Code is optioneel: op een machine zonder levende installatie bestaat
# CC_PROJECTS niet en levert de scan leeg.
PROJECTEN = os.path.expanduser(os.environ.get("CC_PROJECTS") or "~/.claude/projects")
KAARTEN = os.path.expanduser("~/Library/Application Support/Claude/claude-code-sessions")
RE_SR = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
RE_LC = re.compile(r"<local-command-[^>]*>.*?</local-command-[^>]*>", re.S)


def schoon(t):
    if not isinstance(t, str):
        return None
    t = RE_LC.sub("", RE_SR.sub("", t)).strip()
    if not t or t.startswith("<") or "system-reminder" in t or t.startswith("Caveat:"):
        return None
    return t


def menselijke_blokken(rec):
    """Echte tekstblokken van de gebruiker in een user-record; per blok, niet samengevoegd."""
    if rec.get("type") != "user" or rec.get("isMeta"):
        return []
    inhoud = (rec.get("message") or {}).get("content")
    if isinstance(inhoud, str):
        return [t for t in (schoon(inhoud),) if t]
    uit = []
    for blok in inhoud or []:
        if isinstance(blok, dict) and blok.get("type") == "text":
            t = schoon(blok.get("text", ""))
            if t:
                uit.append(t)
    return uit


def scan(pad):
    laatste, laatste_ts, eerste, cwd = None, None, None, None
    with open(pad, errors="replace") as f:
        for regel in f:
            try:
                rec = json.loads(regel)
            except Exception:
                continue
            if cwd is None and rec.get("cwd"):
                cwd = rec["cwd"]
            if eerste is None and rec.get("timestamp"):
                eerste = rec["timestamp"]
            for t in menselijke_blokken(rec):
                laatste, laatste_ts = t, rec.get("timestamp")
    return laatste, laatste_ts, eerste, cwd


def kaarten():
    uit = {}
    for p in glob.glob(os.path.join(KAARTEN, "**", "local_*.json"), recursive=True):
        try:
            d = json.load(open(p, errors="replace"))
        except Exception:
            continue
        uit[d.get("cliSessionId")] = d
    return uit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dagen", type=float, default=3)
    ap.add_argument("--sid", help="één sessie, volledige uuid")
    args = ap.parse_args()

    kaart = kaarten()
    nu = dt.datetime.now(dt.timezone.utc)
    grens = nu - dt.timedelta(days=args.dagen)
    rijen = []
    for pad in glob.glob(os.path.join(PROJECTEN, "*", "*.jsonl")):
        sid = os.path.basename(pad)[:-6]
        if args.sid and sid != args.sid:
            continue
        prompt, ts, eerste, cwd = scan(pad)
        if ts is None:
            continue
        moment = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if moment < grens:
            continue
        n = subprocess.run(
            f'ps -eo command | grep -F "{sid}" | grep -v grep | grep -vc cozempic',
            shell=True, capture_output=True, text=True).stdout.strip() or "0"
        k = kaart.get(sid)
        rijen.append((moment, sid, cwd or "", (prompt or "")[:70].replace("\n", " "),
                      (nu - moment).total_seconds() / 3600, n,
                      "geen" if not k else ("gearchiveerd" if k.get("isArchived") else "open"),
                      str((k or {}).get("title"))[:38]))
    rijen.sort(reverse=True)
    print(f"{len(rijen)} transcript(en) met een prompt in de laatste {args.dagen} dagen "
          f"(tijden UTC)")
    print(f"{'laatste prompt':17} {'uren stil':9} {'proc':4} {'kaart':13} {'titel':38} prompt")
    for moment, sid, cwd, prompt, stil, n, krt, titel in rijen:
        print(f"{moment.strftime('%Y-%m-%d %H:%M'):17} {stil:9.1f} {n:4} {krt:13} {titel:38} "
              f"{prompt}  [{sid[:8]} {cwd}]")


if __name__ == "__main__":
    main()
