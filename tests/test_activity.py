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

    def test_weeklog_rollup_has_sources_and_cache(self):
        vault = self.make_vault()
        _activity.build_activity_index(vault, full=True, verbose=False)
        now = datetime(2026, 7, 8, 12, 0, tzinfo=_activity.LOCAL_TZ)
        first = _activity.weeklog("vorige week", vault=vault, now=now)
        second = _activity.weeklog("vorige week", vault=vault, now=now)
        self.assertGreaterEqual(first["rollup"]["event_count"], 1)
        self.assertTrue(first["rollup"]["source_refs"])
        self.assertEqual(second["rollup"]["cache"], "hit")

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


if __name__ == "__main__":
    unittest.main()
