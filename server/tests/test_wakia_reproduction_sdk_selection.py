"""Incident replay remains bounded to the World-owned WakIA SDK."""
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import wakfu_server.combat.combat_npc_reproduction as reproduction
from wakfu_server.combat.combat_npc_reproduction import (
    UnsupportedNPCReproduction,
    _sdk_modules,
    sdk_identity,
)


class WakIASdkSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "server"
        self.combat = self.root / "wakfu_server/combat"
        self.bridge = (self.root / "wakfu_server/wakia_bridge").resolve()
        self.combat.mkdir(parents=True)
        self.bridge.mkdir(parents=True)
        (self.bridge / "world_loader.py").write_text(
            "def load_entry(directory):\n"
            "    def run_npc_turn(): pass\n"
            "    run_npc_turn.__module__ = 'wakfu_server.wakia_bridge.wakfu_ai.bridge.world_entry'\n"
            "    return run_npc_turn\n"
        )
        self.legacy = (Path(self.temp.name) / "removed-ai-service").resolve()
        self.legacy.mkdir()
        (self.legacy / "world_loader.py").write_text("# old receipt fixture\n")
        self.file_patch = patch.object(
            reproduction, "__file__", str(self.combat / "combat_npc_reproduction.py")
        )
        self.file_patch.start()
        self.addCleanup(self.file_patch.stop)
        self.imports = patch(
            "wakfu_server.combat.combat_npc_reproduction.importlib.import_module",
            side_effect=lambda name: name,
        )
        self.imports.start()
        self.addCleanup(self.imports.stop)

    def test_runtime_selects_only_world_owned_wakia_sdk(self):
        runtime = SimpleNamespace(native_ai_backend_pin={"backend": "jondo"})
        oracle, stats, directory = _sdk_modules(runtime)
        self.assertEqual(directory, self.bridge)
        self.assertEqual(
            oracle, "wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle"
        )
        self.assertEqual(
            stats, "wakfu_server.wakia_bridge.wakfu_ai.native.native_stats"
        )

    def test_legacy_current_pin_is_rejected_without_loading_legacy_sdk(self):
        runtime = SimpleNamespace(native_ai_backend_pin={"backend": "current"})
        with patch.dict(os.environ, {"WAKFU_LEGACY_AI_SDK_DIR": str(self.legacy)}):
            with self.assertRaisesRegex(UnsupportedNPCReproduction, "SDK was removed"):
                _sdk_modules(runtime)

    def test_legacy_receipt_identity_is_rejected(self):
        runtime = SimpleNamespace(native_ai_backend_pin={"backend": "jondo"})
        with self.assertRaisesRegex(UnsupportedNPCReproduction, "SDK was removed"):
            _sdk_modules(runtime, sdk_source=sdk_identity(self.legacy))

    def test_wakia_receipt_identity_replays_only_when_bridge_matches(self):
        identity = sdk_identity(self.bridge)
        _, _, directory = _sdk_modules(sdk_source=identity)
        self.assertEqual(directory, self.bridge)
        with patch.object(
            reproduction, "sdk_identity", return_value={"sha256": "changed"}
        ):
            with self.assertRaisesRegex(UnsupportedNPCReproduction, "SDK was removed"):
                _sdk_modules(sdk_source=identity)


if __name__ == "__main__":
    unittest.main()
