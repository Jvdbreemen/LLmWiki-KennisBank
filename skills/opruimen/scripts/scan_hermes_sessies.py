#!/usr/bin/env python3
"""Open sessies in de Hermes-store, met lopende beurten en rommel-signalen.

Gebruik:  scan_hermes_sessies.py [--alles]

Zonder --alles: alleen sessies met activiteit in de laatste 7 dagen.
Markeert vermoedelijke rommel: door een ander proces gespawnde sessies
(source a2a of acp) met weinig berichten, en alles van voor vandaag.
"""
import argparse
import datetime as dt
import os
import sqlite3
import sys

DB = os.path.join(os.path.expanduser(
    os.environ.get("HERMES_HOME") or "~/.hermes"), "state.db")
KLEIN = 30  # berichten; daaronder is een gespawnde sessie vermoedelijk rommel


def ts(x):
    return dt.datetime.fromtimestamp(float(x)) if x else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alles", action="store_true", help="ook sessies ouder dan 7 dagen")
    args = ap.parse_args()

    if not os.path.exists(DB):
        sys.exit(f"geen sessiestore op {DB}")
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    nu = dt.datetime.now()
    grens = nu - dt.timedelta(days=7)
    vandaag = nu.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()

    beurten = {r["conversation_id"]: r["expires_at"]
               for r in c.execute("select conversation_id, expires_at from session_turn_leases")
               if float(r["expires_at"]) > nu.timestamp()}

    rijen = list(c.execute(
        "select id, source, title, message_count, started_at, last_activity_at, archived, pinned, hidden "
        "from sessions where archived = 0"))
    rijen.sort(key=lambda r: float(r["last_activity_at"] or r["started_at"] or 0), reverse=True)

    print(f"open sessies: {len(rijen)}   lopende beurten: {len(beurten)}")
    print(f"{'id':26} {'bron':8} {'ber':>5} {'gestart':16} {'laatst actief':16} vlagt")
    for r in rijen:
        la = ts(r["last_activity_at"])
        ref = la or ts(r["started_at"])
        if not args.alles and ref and ref < grens:
            continue
        vlag = []
        klein = (r["message_count"] or 0) <= KLEIN
        if r["source"] in ("a2a", "acp") and klein:
            vlag.append("gespawnd, klein")
        if ref and ref.timestamp() < vandaag:
            vlag.append("ouder dan vandaag")
        if r["id"] in beurten:
            vlag.append("BEURT LOOPT")
        if r["pinned"]:
            vlag.append("pinned")
        if (r["title"] or "") == "Bot Chat" or r["hidden"]:
            vlag.append("bot-rij, laten staan")
        print(f"{r['id']:26} {str(r['source']):8} {r['message_count']:>5} "
              f"{ts(r['started_at']).strftime('%Y-%m-%d %H:%M') if r['started_at'] else '-':16} "
              f"{la.strftime('%Y-%m-%d %H:%M') if la else '-':16} {', '.join(vlag)}")

    oud = c.execute(
        "select count(*) from sessions where archived = 0 and "
        "coalesce(last_activity_at, started_at) < ?", (vandaag,)).fetchone()[0]
    print(f"\narchief: {c.execute('select count(*) from sessions where archived = 1').fetchone()[0]} "
          f"| open van voor vandaag: {oud}")


if __name__ == "__main__":
    main()
