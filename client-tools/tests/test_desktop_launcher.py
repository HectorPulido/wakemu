"""Protect account isolation and explicit server selection in the native entrypoint."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("desktop_entry", ROOT / "client-tools/desktop-launcher.py")
desktop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop)


class DesktopLauncherStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.package = Path(self.tmp.name) / "launcher"
        self.state_file = self.package / "profile/launcher-state.json"

    def test_first_repository_launch_selects_local_client_and_retains_internet_preset(self):
        desktop.seed_state(self.package)
        state = json.loads(self.state_file.read_text())
        self.assertEqual(state["selected_id"], "local")
        self.assertEqual([s["id"] for s in state["servers"]], ["local", "internet"])
        local = state["servers"][0]
        self.assertEqual(local["server_host"], "127.0.0.1")
        self.assertEqual(local["api_url"], "http://127.0.0.1:18081")
        self.assertEqual(local["install_root"], str(ROOT / "client"))
        self.assertEqual(state["accounts"], {})
        self.assertEqual(self.state_file.stat().st_mode & 0o777, 0o600)

    def test_reopening_does_not_rewrite_saved_selection_or_credentials(self):
        self.state_file.parent.mkdir(parents=True)
        original = b'{"private-existing-state": "preserve exactly"}\n'
        self.state_file.write_bytes(original)
        desktop.seed_state(self.package)
        self.assertEqual(self.state_file.read_bytes(), original)

    def test_explicit_server_config_preserves_accounts_and_is_idempotent(self):
        desktop.seed_state(self.package)
        state = json.loads(self.state_file.read_text())
        state["accounts"] = {"fixture": {"username": "retained", "protected": "opaque-fixture"}}
        self.state_file.write_text(json.dumps(state))
        config = Path(self.tmp.name) / "server.json"
        config.write_text(json.dumps(dict(
            server_host="192.0.2.20", api_url="https://192.0.2.20:8443",
            http_url="https://192.0.2.20:8443", shop_url="https://192.0.2.20:8443",
            achievements_url="https://192.0.2.20:8443", dispatch_port=25558,
            game_ports=[25556], chat_port=26337, install_root="/fixture/client",
        )))
        desktop.seed_state(self.package, config)
        desktop.seed_state(self.package, config)
        updated = json.loads(self.state_file.read_text())
        self.assertEqual(updated["accounts"], state["accounts"])
        self.assertEqual(len(updated["servers"]), 3)
        configured = updated["servers"][0]
        self.assertEqual(updated["selected_id"], configured["id"])
        self.assertEqual(configured["dispatch_port"], 25558)
        self.assertEqual(configured["game_ports"], [25556])
        self.assertEqual(configured["api_url"], "https://192.0.2.20:8443")
        self.assertEqual(configured["install_root"], "/fixture/client")

    def test_config_relative_client_and_certificate_paths_follow_config_directory(self):
        folder = Path(self.tmp.name) / "settings"
        folder.mkdir()
        (folder / "server.pem").write_text("fixture certificate")
        config = folder / "server.json"
        config.write_text(json.dumps(dict(
            server_host="127.0.0.1", install_root="../my-client", certificate="server.pem",
        )))
        desktop.seed_state(self.package, config)
        server = json.loads(self.state_file.read_text())["servers"][0]
        self.assertEqual(server["install_root"], str((folder / "../my-client").resolve()))
        self.assertEqual(server["certificate"], str((folder / "server.pem").resolve()))


if __name__ == "__main__":
    unittest.main()
