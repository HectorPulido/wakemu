"""The removed planner selector safely migrates persisted current metadata."""
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from wakfu_server.wakia_bridge.wakfu_ai.bridge import backend_selection
from wakfu_server.wakia_bridge.wakfu_ai.transport.endpoint import DEFAULT_ENDPOINT


class BackendMigrationTests(unittest.TestCase):
    def test_transport_default_uses_wakia_service(self):
        self.assertEqual(DEFAULT_ENDPOINT, "tcp://wakia:8091")

    def runtime(self):
        return SimpleNamespace(
            fight=SimpleNamespace(
                id=263,
                phase="active",
                current=SimpleNamespace(id=-7),
                turn_id=1,
            )
        )

    def test_missing_configuration_defaults_to_wakia_without_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "ai-backend.json"
            pin = backend_selection.pin_backend(self.runtime(), config_path=config)

        self.assertEqual(pin["backend"], "jondo")
        self.assertEqual(pin["endpoint"], "tcp://wakia:8091")
        self.assertFalse(config.exists())

    def test_persisted_current_configuration_is_read_as_wakia_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "ai-backend.json"
            config.write_text(json.dumps({"version": 1, "backend": "current"}))
            original = config.read_bytes()

            self.assertEqual(
                backend_selection.read_config(config),
                {"version": 1, "backend": "jondo"},
            )
            pin = backend_selection.pin_backend(self.runtime(), config_path=config)

            self.assertEqual(pin["endpoint"], "tcp://wakia:8091")
            self.assertEqual(config.read_bytes(), original)

    def test_persisted_current_pin_is_replaced_for_same_turn(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "ai-backend.json"
            config.write_text(json.dumps({"version": 1, "backend": "current"}))
            native = self.runtime()
            native.native_ai_backend_pin = {
                "version": 1,
                "identity": [263, -7, 1],
                "backend": "current",
                "endpoint": "tcp://ai:8090",
            }

            pin = backend_selection.pin_backend(native, config_path=config)

        self.assertEqual(pin["backend"], "jondo")
        self.assertEqual(pin["endpoint"], "tcp://wakia:8091")
        self.assertEqual(native.native_ai_backend_pin, pin)

    def test_removed_backend_cannot_be_written_or_selected(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "ai-backend.json"
            with self.assertRaises(ValueError):
                backend_selection.write_config(config, "current")
            config.write_text(json.dumps({"version": 1, "backend": "unknown"}))
            with self.assertRaises(ValueError):
                backend_selection.pin_backend(self.runtime(), config_path=config)


if __name__ == "__main__":
    unittest.main()
