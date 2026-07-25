"""Integriteitscontroles op backlog/, de bron van waarheid voor werk (CLAUDE.md).

Aanleiding (TASK-54): vier taak-ID's werden door twee bestanden geclaimd -- twee
paren binnen backlog/tasks/ en twee over tasks/ en archive/tasks/ heen -- precies
op de nieuwste, vooruitkijkende items. Backlog.md kent geen automatisch committen
(`auto_commit: false`) en backlog/ staat niet in .gitignore, dus bestanden die
het gereedschap schrijft belanden niet vanzelf in git; een botsing viel daardoor
niemand op.

Wat deze test NIET kan zien: bestanden die nog untracked zijn. Een test draait op
de werkboom en kan niet weten wat wel of niet gecommit is. Dat gat wordt gedekt
door de sessiestart-waarschuwing in scripts/git-upstream-check.py.
"""
from __future__ import annotations

import collections
import re
import unittest
from pathlib import Path

BACKLOG = Path(__file__).resolve().parents[1] / "backlog"
ID_RE = re.compile(r"^id:\s*(\S+)", re.M)
STATUS_RE = re.compile(r"^status:\s*(.+?)\s*$", re.M)
MILESTONE_RE = re.compile(r"^milestone:\s*(.+?)\s*$", re.M)


def _task_files():
    return sorted(BACKLOG.rglob("task-*.md"))


class BacklogIntegrityTest(unittest.TestCase):
    def test_task_ids_are_unique(self):
        seen = collections.defaultdict(list)
        for path in _task_files():
            match = ID_RE.search(path.read_text(encoding="utf-8"))
            if match:
                seen[match.group(1)].append(str(path.relative_to(BACKLOG)))
        collisions = {k: v for k, v in seen.items() if len(v) > 1}
        self.assertEqual(
            collisions, {},
            "twee taakbestanden claimen hetzelfde ID; dat breekt de bron van "
            "waarheid stil, ook over tasks/ en archive/tasks/ heen:\n"
            + "\n".join(f"  {k}: {v}" for k, v in sorted(collisions.items())))

    def test_filename_matches_declared_id(self):
        mismatches = []
        for path in _task_files():
            match = ID_RE.search(path.read_text(encoding="utf-8"))
            if not match:
                mismatches.append(f"{path.name}: geen id-veld")
                continue
            from_name = path.name.split(" - ", 1)[0]          # "task-57"
            expected = from_name.replace("task-", "TASK-", 1)
            if match.group(1) != expected:
                mismatches.append(f"{path.name}: frontmatter zegt {match.group(1)}")
        self.assertEqual(mismatches, [],
                         "bestandsnaam en id-veld lopen uiteen:\n  "
                         + "\n  ".join(mismatches))

    def test_named_milestones_exist_as_files(self):
        declared = set()
        for path in _task_files():
            match = MILESTONE_RE.search(path.read_text(encoding="utf-8"))
            if match and match.group(1) not in ("", "null", "~"):
                declared.add(match.group(1).strip().strip("\"'"))
        milestones_dir = BACKLOG / "milestones"
        on_disk = set()
        if milestones_dir.is_dir():
            for path in milestones_dir.glob("*.md"):
                title = re.search(r"^title:\s*(.+?)\s*$", path.read_text(encoding="utf-8"), re.M)
                on_disk.add(title.group(1).strip().strip("\"'") if title else path.stem)
        missing = declared - on_disk
        self.assertEqual(
            missing, set(),
            f"taken noemen milestones zonder milestone-bestand: {sorted(missing)}")

    def test_every_task_declares_a_known_status(self):
        # backlog/config.yml: statuses: ["To Do", "In Progress", "Done"]
        allowed = {"To Do", "In Progress", "Done", "Draft"}
        bad = []
        for path in _task_files():
            match = STATUS_RE.search(path.read_text(encoding="utf-8"))
            status = match.group(1).strip().strip("\"'") if match else ""
            if status not in allowed:
                bad.append(f"{path.name}: {status!r}")
        self.assertEqual(bad, [], "onbekende status-waarden:\n  " + "\n  ".join(bad))


if __name__ == "__main__":
    unittest.main()
