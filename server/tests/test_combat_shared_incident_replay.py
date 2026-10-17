"""Automatically captured collective ACK and session guards replay privately."""
import copy
import os
import struct
import unittest
from unittest.mock import patch

from wakfu_server.combat_incident_replay import LIVE_RECIPE, replay_runtime_incident
from wakfu_server.combat_reproduction import controlled_environment
from wakfu_server.combat_shared import Session


class SharedIncidentReplayTests(unittest.TestCase):
    def fixture(self):
        from test_combat_shared_reproduction import SharedReproductionTests

        fixture = SharedReproductionTests()
        fixture.setUp()
        fixture.end_turn()
        return fixture

    def capture_ack(self, fixture, session, body):
        from test_combat_shared_reproduction import CLOCKS, POLICIES

        with controlled_environment(CLOCKS, POLICIES), patch.dict(
            os.environ,
            {
                "WAKFU_COMBAT_INCIDENT_DIR": "/private/unused",
                "WAKFU_COMBAT_INCIDENT_MODE": "all",
            },
        ), patch("wakfu_server.combat_incident_capture._enqueue") as enqueue:
            try:
                fixture.registry.acknowledge(
                    88,
                    session,
                    body,
                    lambda fight, runtime, request: runtime.acknowledge_turn(request),
                )
            except ValueError:
                pass
        receipt = enqueue.call_args.args[1]
        receipt["origin"] = "native-runtime-fixture-not-live-client-incident"
        return receipt

    def test_partial_and_final_ack_match_actual_barrier_and_mailboxes(self):
        fixture = self.fixture()
        body = struct.pack(">i", fixture.shared.ack.turn)
        for session, expected_return in ((fixture.one, False), (fixture.two, True)):
            receipt = self.capture_ack(fixture, session, body)
            before = copy.deepcopy(receipt)
            result = replay_runtime_incident(receipt, provider_recipe=LIVE_RECIPE)
            self.assertTrue(result["operation_matches"], result["differences"])
            self.assertTrue(result["mailbox_matches"])
            self.assertIs(receipt["return_value"], expected_return)
            self.assertFalse(result["shared_delivery_qualified"])
            self.assertFalse(result["bootstrap_qualified"])
            self.assertEqual(receipt, before)

    def test_stale_lease_rejection_is_observed_not_assumed_live(self):
        fixture = self.fixture()
        body = struct.pack(">i", fixture.shared.ack.turn)
        stale = Session(1, 100, "old-generation", 1134, 0)
        receipt = self.capture_ack(fixture, stale, body)
        self.assertEqual(receipt["status"], "raised")
        result = replay_runtime_incident(receipt, provider_recipe=LIVE_RECIPE)
        self.assertTrue(result["operation_matches"], result["differences"])
        self.assertEqual(result["status"], "raised")

    def test_changed_observed_mailbox_outcome_cannot_pass(self):
        fixture = self.fixture()
        body = struct.pack(">i", fixture.shared.ack.turn)
        receipt = self.capture_ack(fixture, fixture.one, body)
        receipt["return_value"] = True
        result = replay_runtime_incident(receipt, provider_recipe=LIVE_RECIPE)
        self.assertFalse(result["operation_matches"])
        self.assertTrue(result["differences"])

    def test_trusted_sink_gets_detached_recomputed_state_outside_public_summary(self):
        fixture = self.fixture()
        body = struct.pack(">i", fixture.shared.ack.turn)
        receipt = self.capture_ack(fixture, fixture.one, body)
        evidence = []
        result = replay_runtime_incident(
            receipt, provider_recipe=LIVE_RECIPE, evidence_sink=evidence.append
        )
        self.assertTrue(result["operation_matches"])
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["graph"], receipt["after"]["graph"])
        self.assertNotIn("graph", result)
        evidence[0]["graph"].clear()
        self.assertTrue(receipt["after"]["graph"])


if __name__ == "__main__":
    unittest.main()
