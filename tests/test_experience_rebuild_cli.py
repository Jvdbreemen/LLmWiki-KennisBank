"""The production rebuild CLI targets split stores and degrades to lexical."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load():
    spec = importlib.util.spec_from_file_location(
        "experience_rebuild_cli", SCRIPTS / "rebuild-experience.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExperienceRebuildCliTest(unittest.TestCase):
    def _run_cli(self, root: Path):
        env = dict(os.environ, KENNISBANK_VAULT=str(root))
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "rebuild-experience.py"), "--records-only"],
            env=env, capture_output=True, text=True, timeout=30)

    def test_real_disabled_cli_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / ".claude"
            state.mkdir()
            files = {state / "kb-experience-ledger.db": b"ledger must not open",
                     state / "kb-experience-index.db": b"previous good projection"}
            for path, data in files.items():
                path.write_bytes(data)
            result = self._run_cli(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "disabled")
            self.assertEqual({path: path.read_bytes() for path in files}, files)
            self.assertEqual(set(state.iterdir()), set(files))

    def test_real_enabled_cli_builds_lexical_projection(self):
        import _experience

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "kennisbank-settings.json").write_text(
                '{"experience_projection": true}', encoding="utf-8")
            ledger = _experience.ledger_path(root)
            conn = _experience.connect(ledger)
            _experience.ensure_ledger_schema(conn)
            conn.close()
            result = self._run_cli(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["vector_status"], "lexical_fallback")
            self.assertTrue(_experience.projection_path(root).is_file())

    def test_default_paths_are_split_and_embedding_outage_uses_lexical(self):
        module = _load()
        captured = {}

        class Builder:
            @staticmethod
            def rebuild_experience_projection(ledger, projection, **kwargs):
                captured.update({"ledger": Path(ledger), "projection": Path(projection),
                                 **kwargs})
                return {"status": "ok", "vector_status": "lexical_fallback"}

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(module, "_builder", return_value=Builder), \
                mock.patch.dict(sys.modules, {"_embeddings": None}):
            (Path(tmp) / "kennisbank-settings.json").write_text(
                json.dumps({"experience_projection": True}), encoding="utf-8")
            code = module.main(["--vault", tmp])

        self.assertEqual(code, 0)
        self.assertEqual(captured["ledger"].name, "kb-experience-ledger.db")
        self.assertEqual(captured["projection"].name, "kb-experience-index.db")
        self.assertIsNone(captured["embed_fn"])

    def test_disabled_policy_never_initializes_backends_or_builder(self):
        for settings in (None, '{"experience_projection": false}',
                         '{"experience_projection": "false"}',
                         '{"experience_recall": true}', '{broken', '[]'):
            with self.subTest(settings=settings), tempfile.TemporaryDirectory() as tmp:
                module = _load()
                root = Path(tmp)
                if settings is not None:
                    (root / "kennisbank-settings.json").write_text(settings, encoding="utf-8")
                before = sorted(p.name for p in root.iterdir())
                output = io.StringIO()
                with mock.patch.object(module, "_builder") as builder, \
                        mock.patch.object(module, "_optional_embedding", return_value=(None, "")) as embedding, \
                        redirect_stdout(output):
                    builder.return_value.rebuild_experience_projection.return_value = {"status": "ok"}
                    code = module.main(["--vault", tmp])
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(output.getvalue())["status"], "disabled")
                builder.assert_not_called()
                embedding.assert_not_called()
                self.assertEqual(sorted(p.name for p in root.iterdir()), before)

    def test_other_enabled_vault_and_custom_paths_cannot_grant_build(self):
        module = _load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            active, selected = root / "active", root / "selected"
            active.mkdir()
            selected.mkdir()
            (active / "kennisbank-settings.json").write_text(
                '{"experience_projection": true}', encoding="utf-8")
            with mock.patch.dict(os.environ, {"KENNISBANK_VAULT": str(active)}), \
                    mock.patch.object(module, "_builder") as builder, \
                    mock.patch.object(module, "_optional_embedding", return_value=(None, "")) as embedding, \
                    redirect_stdout(io.StringIO()) as output:
                builder.return_value.rebuild_experience_projection.return_value = {"status": "ok"}
                code = module.main(["--vault", str(selected), "--records-only",
                                    "--ledger", str(active / "ledger.db"),
                                    "--projection", str(active / "index.db")])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "disabled")
            builder.assert_not_called()
            embedding.assert_not_called()

    def test_selected_enabled_vault_overrides_disabled_ambient_vault(self):
        module = _load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = root / "selected"
            selected.mkdir()
            (selected / "kennisbank-settings.json").write_text(
                '{"experience_projection": true}', encoding="utf-8")
            builder = mock.Mock()
            builder.rebuild_experience_projection.return_value = {"status": "ok"}
            with mock.patch.dict(os.environ, {"KENNISBANK_VAULT": str(root)}), \
                    mock.patch.object(module, "_builder", return_value=builder), \
                    mock.patch.object(module, "_optional_embedding", return_value=(None, "")), \
                    redirect_stdout(io.StringIO()):
                code = module.main(["--vault", str(selected), "--records-only"])
            self.assertEqual(code, 0)
            self.assertEqual(builder.rebuild_experience_projection.call_args.args,
                             (selected / ".claude/kb-experience-ledger.db",
                              selected / ".claude/kb-experience-index.db"))

    def test_missing_vault_never_uses_working_directory(self):
        for ambient in ({}, {"KENNISBANK_VAULT": ""}, {"KENNISBANK_VAULT": "   "}):
            with self.subTest(ambient=ambient):
                module = _load()
                with mock.patch.dict(os.environ, ambient, clear=True), \
                        mock.patch.object(module, "_builder") as builder, \
                        mock.patch.object(module, "_optional_embedding", return_value=(None, "")) as embedding, \
                        redirect_stdout(io.StringIO()) as output:
                    builder.return_value.rebuild_experience_projection.return_value = {"status": "ok"}
                    code = module.main(["--records-only"])
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(output.getvalue())["status"], "invalid")
                builder.assert_not_called()
                embedding.assert_not_called()

    def test_environment_vault_is_used_when_no_explicit_vault_is_given(self):
        module = _load()
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"KENNISBANK_VAULT": tmp}), \
                    mock.patch.object(module, "_builder") as builder, \
                    mock.patch.object(module, "_optional_embedding", return_value=(None, "")) as embedding, \
                    redirect_stdout(io.StringIO()) as output:
                builder.return_value.rebuild_experience_projection.return_value = {"status": "ok"}
                code = module.main([])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "disabled")
            builder.assert_not_called()
            embedding.assert_not_called()


if __name__ == "__main__":
    unittest.main()
