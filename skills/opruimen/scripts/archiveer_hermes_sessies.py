#!/usr/bin/env python3
"""Archiveer Hermes-sessies (soft-hide), hetzelfde codepad als de archiveerknop in de app.

Categorieën (kies er een of meer):
  --a2a-klein          door een ander proces gespawnde sessies (a2a, acp) met weinig berichten
  --ouder-dan-vandaag  alles zonder activiteit van vandaag
  --ids <id> [...]     precieze sessies

Zonder --yes is het een proefrun. Sessies met een lopende beurt worden altijd
overgeslagen, net als gepinde sessies en de verborgen "Bot Chat" (de canonieke
bot-rij van de desktop; archiveren breekt Bot Mode). Niets wordt verwijderd:
berichten blijven staan, de sessie is alleen niet meer zichtbaar in de lijst.
Terugzetten kan met dezelfde functie en False.
"""
import argparse
import datetime as dt
import json
import os
import sqlite3
import sys

# hermes_state gebruikt `str | object` in een annotatie en struikelt op de systeempython
# (3.9 op macOS). Start jezelf opnieuw met de venv-python van de installatie.
HERMES_HOME = os.path.expanduser(os.environ.get("HERMES_HOME") or "~/.hermes")
VENV = os.path.join(HERMES_HOME, "hermes-agent/venv/bin/python3")
if sys.version_info < (3, 10) and os.path.exists(VENV) and not os.environ.get("OPRUIMEN_HERSTART"):
    os.environ["OPRUIMEN_HERSTART"] = "1"
    os.execv(VENV, [VENV, os.path.abspath(__file__), *sys.argv[1:]])

sys.path.insert(0, os.path.join(HERMES_HOME, "hermes-agent"))
from hermes_state import SessionDB  # noqa: E402

DB = os.path.join(HERMES_HOME, "state.db")
KLEIN = 30
BOT_CHAT = "Bot Chat"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a2a-klein", action="store_true")
    ap.add_argument("--ouder-dan-vandaag", action="store_true")
    ap.add_argument("--ids", nargs="*", default=[])
    ap.add_argument("--yes", action="store_true", help="doorvoeren; zonder dit alleen tonen")
    args = ap.parse_args()
    if not (args.a2a_klein or args.ouder_dan_vandaag or args.ids):
        sys.exit("kies een categorie: --a2a-klein, --ouder-dan-vandaag of --ids")

    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    nu = dt.datetime.now()
    vandaag = nu.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    lopend = {r["conversation_id"] for r in c.execute(
        "select conversation_id, expires_at from session_turn_leases")
        if float(r["expires_at"]) > nu.timestamp()}
    ids = set(args.ids)

    kandidaten, overgeslagen = [], []
    for r in c.execute("select id, source, title, message_count, started_at, last_activity_at, "
                       "pinned, hidden from sessions where archived = 0"):
        ref = float(r["last_activity_at"] or r["started_at"] or 0)
        raak = (r["id"] in ids
                or (args.a2a_klein and r["source"] in ("a2a", "acp") and (r["message_count"] or 0) <= KLEIN)
                or (args.ouder_dan_vandaag and ref < vandaag))
        if not raak:
            continue
        if r["id"] in lopend:
            overgeslagen.append((r["id"], "lopende beurt"))
            continue
        if r["id"] not in ids and ((r["title"] or "") == BOT_CHAT or r["hidden"]):
            overgeslagen.append((r["id"], "bot-rij of verborgen, laten staan"))
            continue
        if r["pinned"] and r["id"] not in ids:
            overgeslagen.append((r["id"], "pinned"))
            continue
        kandidaten.append((r["id"], r["source"], r["message_count"],
                           dt.datetime.fromtimestamp(ref).strftime("%Y-%m-%d %H:%M"),
                           (r["title"] or "")[:52]))

    kandidaten.sort(key=lambda k: k[3])
    print(f"{len(kandidaten)} sessie(s) om te archiveren:")
    for k in kandidaten:
        print(f"  {k[0]:26} {k[1]:8} {k[2]:>4} ber.  laatst {k[3]}  {k[4]}")
    for sid, reden in overgeslagen:
        print(f"  overgeslagen: {sid} ({reden})")
    print(f"  berichten die blijven staan: {sum(k[2] for k in kandidaten)}")

    if not args.yes:
        print("\nProefrun, niets gewijzigd. Voeg --yes toe om te archiveren.")
        return

    db = SessionDB()
    gedaan = []
    for k in kandidaten:
        if db.set_session_archived(k[0], True):
            gedaan.append(k[0])
        else:
            print(f"  ! niet gearchiveerd: {k[0]}")
    print(f"\nGearchiveerd: {len(gedaan)} van {len(kandidaten)}.")
    spoor = os.path.join(HERMES_HOME, "cache/scratch/opruimen-het-laatst.json")
    os.makedirs(os.path.dirname(spoor), exist_ok=True)
    json.dump(gedaan, open(spoor, "w"), indent=1)
    print(f"Id's voor terugzetten: {spoor}")


if __name__ == "__main__":
    main()
