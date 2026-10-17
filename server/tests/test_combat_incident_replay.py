"""Automatically observed operations replay without manually rebuilding scenes."""
import copy
import os
from pathlib import Path
import random
import struct
import tempfile
import unittest
from unittest.mock import patch

from wakfu_server.combat_incident_capture import incident_scope
from wakfu_server.combat_incident_replay import (
    RECIPE,
    replay_runtime_incident,
    write_incident,
    read_incident,
    IncidentReplayError,
)
from wakfu_server.combat_reproduction import controlled_environment, ReproductionClock
from wakfu_server.combat_reproduction_actions import prepare_context, execute


class IncidentReplayTests(unittest.TestCase):
    def incident(self, *, malformed=False):
        import test_combat_reproduction_actions as fixtures

        runtime, inputs = fixtures.ReproductionActionTests().fixture()
        target = runtime.fight.actors[-7].position
        action = dict(
            type="player_spell",
            owner_id=3,
            critical=None,
            body=b"malformed"
            if malformed
            else struct.pack(">qqiih", 7, (7 << 32) | 6266, *target),
        )
        clocks = {"wall_time_ns": 1700000000000000000, "monotonic_ns": 123000000000}
        policies = {
            "WAKFU_NATIVE_AREA_CALLBACKS": "1",
            "WAKFU_NATIVE_GRANTED_CAST": "0",
        }
        rng, clock = random.Random(42), ReproductionClock(clocks)
        live_inputs = dict(inputs, authority_recipe="observed-live-server-v1")
        with controlled_environment(clocks, policies), patch.dict(
            os.environ,
            {
                "WAKFU_COMBAT_INCIDENT_DIR": "/private/unused",
                "WAKFU_COMBAT_INCIDENT_MODE": "all",
            },
        ), patch("wakfu_server.combat_incident_capture._enqueue") as enqueue:
            context = prepare_context(runtime, action, inputs, rng, clock)
            try:
                with incident_scope(
                    runtime, action, live_inputs, recipients=(3,)
                ) as capture:
                    result = execute(
                        runtime, action, inputs, rng, clock, prepared_context=context
                    )
                    capture.packets(result["packets"])
            except ValueError:
                if not malformed:
                    raise
        receipt = enqueue.call_args.args[1]
        receipt["origin"] = "native-fixture-demonstration-not-live-client-incident"
        return receipt

    def test_automatically_captured_native_operation_matches_without_scene_setup(self):
        receipt = self.incident()
        before = copy.deepcopy(receipt)
        first = replay_runtime_incident(receipt, provider_recipe=RECIPE)
        second = replay_runtime_incident(receipt, provider_recipe=RECIPE)
        self.assertTrue(first["operation_matches"], first["differences"])
        self.assertTrue(first["rng_ownership_known"])
        self.assertFalse(first["shared_delivery_qualified"])
        self.assertEqual(first["actual_sha256"], second["actual_sha256"])
        self.assertEqual(receipt, before)

    def test_actual_captured_rejection_reproduces_and_tampered_output_differs(self):
        receipt = self.incident(malformed=True)
        result = replay_runtime_incident(receipt, provider_recipe=RECIPE)
        self.assertTrue(result["operation_matches"], result["differences"])
        self.assertEqual(result["status"], "rejected")
        altered = copy.deepcopy(receipt)
        altered["error"]["message"] = "different observed error"
        result = replay_runtime_incident(altered, provider_recipe=RECIPE)
        self.assertFalse(result["operation_matches"])
        self.assertTrue(result["differences"])

    def test_private_roundtrip_and_unknown_recipe_reject(self):
        receipt = self.incident(malformed=True)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "incident.json"
            write_incident(path, receipt)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(read_incident(path), receipt)
        with self.assertRaises(IncidentReplayError):
            replay_runtime_incident(receipt, provider_recipe="unknown")


if __name__ == "__main__":
    unittest.main()
