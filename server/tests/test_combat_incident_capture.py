"""Actual execution evidence stays private and never changes action behavior."""
import json
import os
from pathlib import Path
import random
import tempfile
import threading
import unittest
from unittest.mock import patch

from wakfu_server.combat_incident_capture import incident_scope, _persist
from wakfu_server.combat_input_observation import observe_rng
from wakfu_server.combat_reproduction_state import decode_state


class CombatIncidentCaptureTests(unittest.TestCase):
    def test_disabled_scope_does_not_encode_or_read_rng(self):
        with patch.dict(os.environ, {"WAKFU_COMBAT_INCIDENT_DIR": ""}), patch(
            "wakfu_server.combat_incident_capture.encode_state"
        ) as encode:
            with incident_scope(object(), object(), object()) as capture:
                self.assertIsNone(capture)
            encode.assert_not_called()

    def test_failed_action_keeps_original_error_and_observed_rng(self):
        runtime = {"hp": 100}
        rng, comparison = random.Random(42), random.Random(42)
        error = ValueError("actual game rejection")
        with patch.dict(
            os.environ,
            {
                "WAKFU_COMBAT_INCIDENT_DIR": "/private/unused",
                "WAKFU_COMBAT_INCIDENT_MODE": "failures",
            },
        ), patch(
            "wakfu_server.combat_incident_capture._identity", return_value={}
        ), patch(
            "wakfu_server.combat_incident_capture._enqueue"
        ) as enqueue:
            with self.assertRaises(ValueError) as raised:
                with incident_scope(runtime, {"type": "example"}, {}) as capture:
                    observe_rng("action", rng)
                    self.assertEqual(rng.random(), comparison.random())
                    runtime["hp"] = 90
                    capture.packets([(123, b"actual outgoing bytes")])
                    raise error
            self.assertIs(raised.exception, error)
        receipt = enqueue.call_args.args[1]
        self.assertEqual(decode_state(receipt["before"])["runtime"], {"hp": 100})
        after = decode_state(receipt["after"])
        self.assertEqual(after["runtime"], {"hp": 90})
        self.assertEqual(after["packets"], ((123, b"actual outgoing bytes"),))
        self.assertFalse(receipt["replay_qualified"])
        streams = decode_state(receipt["observations"])["rng_streams"]
        self.assertEqual(streams[0]["initial_state"], random.Random(42).getstate())
        self.assertEqual(streams[0]["final_state"], comparison.getstate())
        # The writer receives only frozen data, independent of later gameplay.
        runtime["hp"] = 1
        self.assertEqual(decode_state(receipt["after"])["runtime"]["hp"], 90)

    def test_capture_failure_cannot_replace_gameplay_exception(self):
        original = ValueError("gameplay")
        with patch.dict(
            os.environ, {"WAKFU_COMBAT_INCIDENT_DIR": "/private/unused"}
        ), patch(
            "wakfu_server.combat_incident_capture._identity",
            side_effect=RuntimeError("diagnostics"),
        ), patch(
            "wakfu_server.combat_incident_capture._enqueue",
            side_effect=OSError("disk full"),
        ), self.assertLogs(
            "wakfu_server.combat_incident_capture", level="WARNING"
        ):
            with self.assertRaises(ValueError) as raised:
                with incident_scope({}, {}, {}):
                    raise original
        self.assertIs(raised.exception, original)

    def test_success_only_saved_in_explicit_all_mode(self):
        with patch.dict(
            os.environ,
            {
                "WAKFU_COMBAT_INCIDENT_DIR": "/private/unused",
                "WAKFU_COMBAT_INCIDENT_MODE": "failures",
            },
        ), patch(
            "wakfu_server.combat_incident_capture._identity", return_value={}
        ), patch(
            "wakfu_server.combat_incident_capture._enqueue"
        ) as enqueue:
            with incident_scope({}, {}, {}):
                pass
            enqueue.assert_not_called()
            with patch.dict(os.environ, {"WAKFU_COMBAT_INCIDENT_MODE": "all"}):
                with incident_scope({}, {}, {}):
                    pass
            self.assertEqual(enqueue.call_count, 1)
            self.assertEqual(enqueue.call_args.args[1]["status"], "accepted")

    def test_observer_setup_failure_still_runs_gameplay(self):
        executed = []
        with patch.dict(
            os.environ, {"WAKFU_COMBAT_INCIDENT_DIR": "/private/unused"}
        ), patch(
            "wakfu_server.combat_incident_capture._identity", return_value={}
        ), patch(
            "wakfu_server.combat_input_observation.observe_combat_inputs",
            side_effect=RuntimeError("diagnostic setup"),
        ), self.assertLogs(
            "wakfu_server.combat_incident_capture", level="WARNING"
        ):
            with incident_scope({}, {}, {}) as capture:
                self.assertIsNone(capture)
                executed.append("actual action")
        self.assertEqual(executed, ["actual action"])

    def test_private_file_quota_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "incidents"
            _persist(root, "fixture", b'{"schema":"fixture"}')
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            self.assertEqual((root / "fixture.json").stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                _persist(root, "fixture", b"replacement")
            self.assertEqual(
                json.loads((root / "fixture.json").read_text())["schema"], "fixture"
            )
            with patch("wakfu_server.combat_incident_capture.MAX_FILES", 1):
                with self.assertRaisesRegex(ValueError, "quota"):
                    _persist(root, "another", b"new")

    def test_background_writer_persists_frozen_receipt(self):
        completed = threading.Event()

        def persist_and_notify(*args):
            try:
                _persist(*args)
            finally:
                completed.set()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "incidents"
            runtime = {"hp": 100}
            with patch.dict(
                os.environ,
                {
                    "WAKFU_COMBAT_INCIDENT_DIR": str(root),
                    "WAKFU_COMBAT_INCIDENT_MODE": "all",
                },
            ), patch(
                "wakfu_server.combat_incident_capture._identity", return_value={}
            ), patch(
                "wakfu_server.combat_incident_capture._persist",
                side_effect=persist_and_notify,
            ):
                with incident_scope(runtime, {"type": "example"}, {}) as capture:
                    runtime["hp"] = 90
                    capture.packets([(123, b"actual delivery")])
                runtime["hp"] = 1
                self.assertTrue(completed.wait(5), "Incident writer did not complete")
                files = list(root.glob("*.json"))
                self.assertEqual(len(files), 1)
                receipt = json.loads(files[0].read_text())
                self.assertEqual(decode_state(receipt["after"])["runtime"], {"hp": 90})
                self.assertFalse(receipt["replay_qualified"])


if __name__ == "__main__":
    unittest.main()
