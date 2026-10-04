import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "local_launcher", ROOT / "client/tools/local-launcher.py"
)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def test_remember_only_token_and_reuse_without_password(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(
            launcher, "profile_root", return_value=Path(folder)
        ):
            calls = []

            def api(path, body):
                calls.append((path, body))
                return {
                    "account": {"username": "local"},
                    "game_token": "game",
                    "remember_token": "revocable",
                }

            token = launcher.authenticate("main", "local", "secret", True, api=api)
            self.assertEqual(calls[0][0], "/login")
            saved = json.loads((Path(folder) / "remember.json").read_text())
            self.assertEqual(saved, {"username": "local", "token": "revocable"})
            self.assertNotIn("secret", token.read_text())
            self.assertEqual(token.stat().st_mode & 0o777, 0o600)
            launcher.authenticate("main", "local", "", True, api=api)
            self.assertEqual(calls[-1], ("/remember", {"remember_token": "revocable"}))

    def test_register_then_login_and_disable_remember(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(
            launcher, "profile_root", return_value=Path(folder)
        ):
            (Path(folder) / "remember.json").write_text("{}")
            calls = []

            def api(path, body):
                calls.append(path)
                return {"account": {"username": "local"}, "game_token": "game"}

            launcher.authenticate(
                "new", "local", "password", False, register=True, api=api
            )
            self.assertEqual(calls, ["/register", "/login"])
            self.assertFalse((Path(folder) / "remember.json").exists())

    def test_dropin_configuration_resolves_paths_without_repository_imports(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "api_url": "http://192.0.2.1:18081/",
                        "runtime_root": "profiles",
                        "runner": "run-client.sh",
                        "install_root": "..",
                    }
                )
            )
            with patch.dict(launcher.os.environ, {"WAKFU_LAUNCHER_CONFIG": str(path)}):
                config = launcher.settings()
                self.assertEqual(config["api_url"], "http://192.0.2.1:18081")
                self.assertEqual(
                    config["runner"], Path(folder).resolve() / "run-client.sh"
                )
                self.assertEqual(
                    launcher.profile_root("beta"),
                    Path(folder).resolve() / "profiles/instances/beta",
                )
                with self.assertRaises(ValueError):
                    launcher.profile_root("../other")
