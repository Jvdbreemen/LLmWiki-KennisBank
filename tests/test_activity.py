from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS))
import _activity  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class ActivityFixtureMixin:
    def make_vault(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="kb-activity-"))
        vault = tmp / "Kluis"
        _write(
            vault / "01-raw" / "sessies" / "raw-sessie-2026-07-03-codex-mcp.md",
            """---
date: 2026-07-03
project: LLmWiki-KennisBank
---
# Codex MCP hotfix

Besluit: pin mcp==1.28.1 voor Codex MCP.
Release v0.12.2 is gepusht met tag v0.12.2.
TASK-25 temporal activity recall uitgewerkt.
""",
        )
        _write(
            vault / "09-memory" / "codex-mcp.md",
            """---
title: Codex MCP gebruikt lokale py launcher
created: 2026-07-04T10:00:00+02:00
valid_from: 2026-07-04
memory_type: procedure
status: current
---
Gebruik `py -3` voor de KennisBank MCP server op Windows.
""",
        )
        _write(
            vault / "02-wiki" / "temporal-activity.md",
            """---
title: Temporal Activity Recall
updated: 2026-07-05
---
# Temporal Activity Recall

Topic timelines volgen Codex MCP, OpenRouter en release events door de tijd.
""",
        )
        for i in range(30):
            _write(
                vault / "01-raw" / "sessies" / f"raw-sessie-2026-07-01-unrelated-{i:02d}.md",
                f"""---
date: 2026-07-01
---
# Unrelated {i}

Algemene sessie zonder het gezochte onderwerp.
""",
            )
        _write(
            vault / ".claude" / "activity-topic-aliases.json",
            json.dumps({"codex mcp": ["kennisbank mcp", "mcp hotfix"]}),
        )
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        return vault


class PeriodParserTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 7, 8, 12, 0, tzinfo=_activity.LOCAL_TZ)

    def test_previous_week_is_iso_week(self):
        r = _activity.parse_period("vorige week", now=self.now)
        self.assertTrue(r.ok)
        self.assertEqual(r.start[:10], "2026-06-29")
        self.assertEqual(r.end_exclusive[:10], "2026-07-06")
        self.assertEqual(r.granularity, "week")

    def test_absolute_dates_in_dutch_and_english(self):
        for text in ("2026-07-03", "3 juli 2026", "July 3 2026"):
            r = _activity.parse_period(text, now=self.now)
            self.assertTrue(r.ok, text)
            self.assertEqual(r.start[:10], "2026-07-03")
            self.assertEqual(r.end_exclusive[:10], "2026-07-04")

    def test_range_and_topic_extraction(self):
        r = _activity.parse_period('onderwerp "Codex MCP" tussen 2026-07-01 en 2026-07-07', now=self.now)
        self.assertTrue(r.ok)
        self.assertEqual(r.topic, "Codex MCP")
        self.assertEqual(r.start[:10], "2026-07-01")
        self.assertEqual(r.end_exclusive[:10], "2026-07-08")

    def test_ambiguous_date_returns_error(self):
        r = _activity.parse_period("03/07/2026", now=self.now)
        self.assertFalse(r.ok)
        self.assertIn("Ambigue", r.error)

    def test_dst_boundary_is_injectable(self):
        now = datetime(2026, 3, 30, 9, 0, tzinfo=_activity.LOCAL_TZ)
        r = _activity.parse_period("gisteren", now=now)
        self.assertEqual(r.start[:10], "2026-03-29")
        self.assertEqual(r.timezone, "Europe/Amsterdam")


class ActivityIndexTest(ActivityFixtureMixin, unittest.TestCase):
    def test_build_index_is_idempotent_and_queryable(self):
        vault = self.make_vault()
        stats = _activity.build_activity_index(vault, full=True, progress_interval=0, verbose=False)
        self.assertGreaterEqual(stats["total_events"], 5)
        again = _activity.build_activity_index(vault, full=False, progress_interval=0, verbose=False)
        self.assertEqual(again["skipped_sources"], again["sources"])
        r = _activity.what_did_i_do("2026-07-03", topic="Codex MCP", vault=vault)
        self.assertTrue(r["ok"])
        self.assertGreaterEqual(len(r["events"]), 2)
        self.assertTrue(all(e["event_time"][:10] == "2026-07-03" for e in r["events"]))
        self.assertTrue(all(e["source_ref"] for e in r["events"]))

    def test_topic_aliases_and_topic_timeline(self):
        vault = self.make_vault()
        _activity.build_activity_index(vault, full=True, verbose=False)
        r = _activity.topic_timeline(
            "kennisbank mcp",
            period_text="afgelopen 10 dagen",
            vault=vault,
            now=datetime(2026, 7, 8, 12, 0, tzinfo=_activity.LOCAL_TZ),
        )
        self.assertTrue(r["events"])
        self.assertIn(r["events"][0]["match_route"], {"explicit_entity", "explicit_topic", "tag", "fts"})

    def test_topic_filter_uses_larger_prefilter_pool_than_max_events(self):
        vault = self.make_vault()
        _activity.build_activity_index(vault, full=True, verbose=False)
        r = _activity.topic_timeline(
            "Codex MCP",
            period_text="afgelopen 10 dagen",
            max_events=1,
            vault=vault,
            now=datetime(2026, 7, 8, 12, 0, tzinfo=_activity.LOCAL_TZ),
        )
        self.assertEqual(len(r["events"]), 1)
        self.assertIn("Codex", r["events"][0]["title"] + r["events"][0]["summary"])

    def test_weeklog_rollup_is_deterministic_and_self_consistent(self):
        vault = self.make_vault()
        _activity.build_activity_index(vault, full=True, verbose=False)
        now = datetime(2026, 7, 8, 12, 0, tzinfo=_activity.LOCAL_TZ)
        first = _activity.weeklog("vorige week", vault=vault, now=now)
        second = _activity.weeklog("vorige week", vault=vault, now=now)
        self.assertGreaterEqual(first["rollup"]["event_count"], 1)
        self.assertTrue(first["rollup"]["source_refs"])
        # Het gerapporteerde aantal moet bij de meegeleverde events horen. De
        # oude cache-sleutel bevatte de event-limiet niet, waardoor een weeklog
        # met een lage limiet een daaropvolgende bevraging over dezelfde periode
        # een te kleine body gaf -- en dus een te laag event_count.
        self.assertEqual(first["rollup"]["event_count"], len(first["events"]))
        self.assertEqual(second["rollup"], first["rollup"],
                         "twee identieke bevragingen moeten hetzelfde opleveren")

    def test_a_narrow_query_does_not_poison_a_wider_one(self):
        """Regressie: kruisbesmetting tussen twee periodes met dezelfde grenzen.

        Met de cache erin vulde de eerste (smalle) bevraging de sleutel, en
        kreeg de tweede (brede) diezelfde te kleine body terug.
        """
        vault = self.make_vault()
        _activity.build_activity_index(vault, full=True, verbose=False)
        now = datetime(2026, 7, 8, 12, 0, tzinfo=_activity.LOCAL_TZ)
        narrow = _activity.weeklog("vorige week", vault=vault, now=now, max_events=1)
        wide = _activity.weeklog("vorige week", vault=vault, now=now)
        self.assertEqual(narrow["rollup"]["event_count"], len(narrow["events"]))
        self.assertEqual(wide["rollup"]["event_count"], len(wide["events"]))
        self.assertGreaterEqual(wide["rollup"]["event_count"],
                                narrow["rollup"]["event_count"])

    def test_eval_harness_negative_and_positive_controls(self):
        vault = self.make_vault()
        _activity.build_activity_index(vault, full=True, verbose=False)
        result = _activity.eval_queries(
            vault,
            [
                {"id": "positive", "mode": "timeline", "query": "2026-07-03", "topic": "Codex MCP", "min_events": 1},
                {"id": "negative", "mode": "timeline", "query": "1900-01-01", "max_events": 0},
            ],
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["passed"], 2)

    def test_cli_build_and_query(self):
        vault = self.make_vault()
        subprocess.run(
            [sys.executable, str(SCRIPTS / "build-activity-index.py"), "--vault", str(vault), "--full", "--json", "--quiet"],
            check=True,
            capture_output=True,
            text=True,
        )
        out = subprocess.run(
            [sys.executable, str(SCRIPTS / "kb-activity.py"), "--vault", str(vault), "--json", "timeline", "2026-07-03"],
            check=True,
            capture_output=True,
            text=True,
        )
        data = json.loads(out.stdout)
        self.assertGreaterEqual(len(data["events"]), 1)


class UsageSourceExtractorTest(unittest.TestCase):
    """Guard rond `iter_usage_events` -- de vijfde bron, en een valstrik.

    Hij stond visueel middenin een blok van vijf `iter_*_events`-functies waarvan
    de andere vier nul aanroepers hadden. Deze leeft wel: `_events_for_source`
    routeert `.claude/kb-usage.db` ernaartoe. Een opruiming die "de hele familie"
    weghaalt sloopt hem, en tot deze test dekte niets dat pad.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-usage-src-"))
        self.vault = self.tmp / "Kluis"
        db = self.vault / ".claude" / "kb-usage.db"
        db.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE usage (stem TEXT PRIMARY KEY, path TEXT, used_at TEXT)")
        conn.execute("INSERT INTO usage VALUES (?,?,?)",
                     ("hook-gedreven-retrieval", "02-wiki/hook-gedreven-retrieval.md",
                      "2026-07-03T10:00:00"))
        conn.commit()
        conn.close()
        self.db = db

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_usage_db_is_routed_to_the_usage_extractor(self):
        events = _activity._events_for_source(self.vault, self.db)
        self.assertTrue(events, "kb-usage.db leverde geen events op")
        self.assertEqual({e.source_kind for e in events}, {"usage"})
        self.assertTrue(any("hook-gedreven-retrieval" in e.summary for e in events))

    def test_usage_db_is_listed_as_a_source(self):
        self.assertIn(self.db.resolve(),
                      [p.resolve() for p in _activity._source_files(self.vault)])


class FingerprintFastpathTest(ActivityFixtureMixin, unittest.TestCase):
    """De sha256 draaide over ELK bronbestand vóór de watermerkvergelijking.

    Gemeten op de vault van de auteur: 2220 bestanden, 376 MB, 1,67 s warm en
    51,75 s koud -- voor een bouw die meestal niets te doen heeft.
    """

    def _count_hashes(self, fn, *args, **kwargs):
        calls = []
        real = _activity._sha256

        def counting(path):
            calls.append(path)
            return real(path)

        _activity._sha256 = counting
        try:
            fn(*args, **kwargs)
        finally:
            _activity._sha256 = real
        return calls

    def test_clean_incremental_build_hashes_nothing(self):
        vault = self.make_vault()
        _activity.build_activity_index(vault, full=True, verbose=False)
        calls = self._count_hashes(_activity.build_activity_index, vault, verbose=False)
        self.assertEqual(calls, [],
                         f"onveranderde bronnen werden alsnog gehasht: {calls}")

    def test_touched_but_identical_source_is_not_reparsed(self):
        vault = self.make_vault()
        _activity.build_activity_index(vault, full=True, verbose=False)
        src = next((vault / "01-raw" / "sessies").glob("*.md"))
        import os as _os
        st = src.stat()
        _os.utime(src, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000_000))

        stats = _activity.build_activity_index(vault, verbose=False)
        self.assertEqual(stats["changed_sources"], 0,
                         "identieke inhoud met nieuwe mtime werd opnieuw geparsed")
        # Watermerk moet zijn bijgewerkt, anders hasht elke volgende bouw opnieuw.
        calls = self._count_hashes(_activity.build_activity_index, vault, verbose=False)
        self.assertEqual(calls, [], "watermerk niet ververst na een touch")

    def test_full_rebuild_still_reindexes_everything(self):
        vault = self.make_vault()
        first = _activity.build_activity_index(vault, full=True, verbose=False)
        second = _activity.build_activity_index(vault, full=True, verbose=False)
        self.assertEqual(second["skipped_sources"], 0,
                         "--full mag niets overslaan; fastpath lekt")
        self.assertEqual(second["changed_sources"], first["changed_sources"])


class LegacyTableMigrationTest(unittest.TestCase):
    """De vier write-only tabellen moeten ook uit BESTAANDE databases verdwijnen.

    De incrementele bouw hergebruikt het databasebestand; alleen --full unlinkt.
    Zonder een expliciete DROP in ensure_schema blijven de rijen dus eeuwig wees
    in elke gedeployde vault -- 23,7 MB van 57,7 MB op de vault van de auteur.
    """

    LEGACY = ("activity_entities", "activity_topics", "activity_artifacts", "activity_fts")

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-legacy-"))
        self.db = self.tmp / "kb-activity.db"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _tables(self, conn):
        return {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}

    def test_existing_database_loses_the_legacy_tables(self):
        import sqlite3
        conn = sqlite3.connect(self.db)
        conn.execute("CREATE TABLE activity_entities (event_id TEXT, entity TEXT, kind TEXT)")
        conn.execute("CREATE TABLE activity_topics (event_id TEXT, topic TEXT, match_route TEXT)")
        conn.execute("CREATE TABLE activity_artifacts (event_id TEXT, artifact TEXT)")
        conn.execute("CREATE VIRTUAL TABLE activity_fts USING fts5(id UNINDEXED, title, summary, entities, topics)")
        conn.execute("INSERT INTO activity_topics VALUES ('e1','kennisbank','explicit')")
        conn.commit()
        self.assertTrue(set(self.LEGACY) <= self._tables(conn), "fixture niet opgezet")

        _activity.ensure_schema(conn)

        remaining = self._tables(conn) & set(self.LEGACY)
        self.assertEqual(remaining, set(),
                         f"legacy-tabellen blijven achter in een bestaande db: {remaining}")
        conn.close()

    def test_schema_version_is_not_bumped(self):
        # Een bump zet doctor.sh en de statusrapportage op WARN voor elke
        # gedeployde vault tot de gebruiker handmatig --full draait.
        self.assertEqual(_activity.SCHEMA_VERSION, "1")

    def test_fresh_database_has_no_legacy_tables(self):
        import sqlite3
        conn = sqlite3.connect(self.db)
        _activity.ensure_schema(conn)
        self.assertEqual(self._tables(conn) & set(self.LEGACY), set())
        self.assertIn("activity_events", self._tables(conn))
        conn.close()


if __name__ == "__main__":
    unittest.main()
