"""The World-owned selector remains usable without the legacy AI service."""

from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "wakfu_server/wakia_bridge/ai_backend.py"
SPEC = importlib.util.spec_from_file_location("wakia_cli_under_test", SOURCE)
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)


class WakIASelectorCliTests(unittest.TestCase):
    def test_alias_persists_compatible_identity_and_status(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "ai-backend.json"
            output = io.StringIO()
            with patch.object(CLI, "check_health") as health, redirect_stdout(output):
                self.assertEqual(
                    CLI.main(["--use", "wakia", "--config", str(config)]), 0
                )
                health.assert_called_once_with("127.0.0.1", 8091, "jondo", 2.0)
                self.assertEqual(CLI.main(["--status", "--config", str(config)]), 0)
            self.assertEqual(json.loads(config.read_text())["backend"], "jondo")
            for line in output.getvalue().splitlines():
                self.assertEqual(json.loads(line)["name"], "WakIA")
                self.assertEqual(json.loads(line)["backend"], "jondo")

    def test_health_failure_does_not_change_existing_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "ai-backend.json"
            previous = '{"version": 1, "backend": "current"}\n'
            config.write_text(previous)
            with patch.object(CLI, "check_health", side_effect=OSError("offline")):
                self.assertEqual(
                    CLI.main(["--use", "wakia", "--config", str(config)]), 1
                )
            self.assertEqual(config.read_text(), previous)

    def test_container_default_health_check_targets_wakia_service(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "ai-backend.json"
            with patch.object(CLI, "_repository", return_value=None), patch.object(
                CLI, "check_health"
            ) as health, redirect_stdout(io.StringIO()):
                self.assertEqual(
                    CLI.main(["--use", "wakia", "--config", str(config)]), 0
                )
            health.assert_called_once_with("wakia", 8091, "jondo", 2.0)

    def test_flat_world_layout_does_not_require_ai_service(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "app/wakfu_server/wakia_bridge"
            selector = root / "wakfu_ai/bridge/backend_selection.py"
            selector.parent.mkdir(parents=True)
            selector.write_bytes(
                (SOURCE.parent / "wakfu_ai/bridge/backend_selection.py").read_bytes()
            )
            source = root / "ai_backend.py"
            source.write_bytes(SOURCE.read_bytes())
            spec = importlib.util.spec_from_file_location("flat_wakia_cli", source)
            flat = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(flat)
            self.assertIsNone(flat._repository())
            self.assertEqual(
                flat._selector().read_config(root / "absent.json")["backend"], "jondo"
            )


if __name__ == "__main__":
    unittest.main()
