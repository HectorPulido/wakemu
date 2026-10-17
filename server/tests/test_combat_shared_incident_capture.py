"""Automatic receipts cover original locked Registry validation and publication."""
from contextlib import ExitStack
import builtins
import os
import struct
import unittest
from unittest.mock import patch

from wakfu_server.combat_shared import Session
from wakfu_server.combat_shared_incident_capture import (
    current_shared_incident,
    SharedIncidentCapture,
    shared_incidents_suppressed,
)
from wakfu_server.combat_shared_reproduction import (
    capture_shared_state,
    restore_shared_state,
    replay_execute,
    replay_acknowledge,
    lease_result,
)
from wakfu_server.combat_reproduction_state import decode_state
from wakfu_server.combat_reproduction import controlled_environment
import test_combat_shared_reproduction as shared_fixture
import test_combat_incident_dispatch_integration as dispatch_fixture

CLOCKS, POLICIES, end_current = (
    shared_fixture.CLOCKS,
    shared_fixture.POLICIES,
    shared_fixture.end_current,
)


class SharedIncidentCaptureTests(unittest.TestCase):
    def setUp(self):
        fixture = shared_fixture.SharedReproductionTests()
        fixture.setUp()
        self.fixture = fixture
        self.registry, self.shared = fixture.registry, fixture.shared
        self.one, self.two = fixture.one, fixture.two
        self.receipts = []
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(
            patch.dict(
                os.environ,
                {
                    "WAKFU_COMBAT_INCIDENT_DIR": "/private/diagnostic-only",
                    "WAKFU_COMBAT_INCIDENT_MODE": "all",
                },
            )
        )
        self.stack.enter_context(
            patch(
                "wakfu_server.combat_incident_capture._identity",
                return_value={"test": True},
            )
        )
        self.stack.enter_context(
            patch(
                "wakfu_server.combat_incident_capture._enqueue",
                side_effect=lambda root, receipt: self.receipts.append(receipt),
            )
        )

    def end(self, operation=end_current):
        with controlled_environment(CLOCKS, POLICIES):
            return self.registry.execute(88, self.one, 100, operation)

    def state(self, receipt, phase="after"):
        self.assertIsNotNone(receipt[phase], receipt["incomplete"])
        return decode_state(receipt[phase]["graph"])

    def test_one_envelope_covers_end_turn_partial_and_final_collective_ack(self):
        self.assertEqual(self.end(), 1)
        body = struct.pack(">i", self.shared.ack.turn)
        release_calls = []

        def release(fight, runtime, request):
            release_calls.append(request)
            return runtime.acknowledge_turn(request)

        with controlled_environment(CLOCKS, POLICIES):
            self.assertFalse(self.registry.acknowledge(88, self.one, body, release))
            self.assertTrue(self.registry.acknowledge(88, self.two, body, release))
        self.assertEqual(len(self.receipts), 3)
        end, partial, final = self.receipts
        self.assertEqual(
            [end["return_value"], partial["return_value"], final["return_value"]],
            [1, False, True],
        )
        self.assertEqual(self.state(partial, "before")["ack"].received, set())
        self.assertEqual(self.state(partial)["ack"].received, {1})
        self.assertEqual(self.state(partial)["sequence"], 1)
        self.assertIsNone(self.state(final)["ack"].turn)
        self.assertEqual(self.state(final)["sequence"], 2)
        self.assertEqual(len(release_calls), 1)
        leases = decode_state(end["lease_observations"])
        self.assertEqual([row["session"]["account_id"] for row in leases], [1, 1, 2])
        self.assertEqual(
            len(self.fixture.rows), 5
        )  # Original calls, no diagnostic lease reads.
        self.assertEqual(
            self.state(final)["outboxes"][1][-1].packets,
            self.state(final)["outboxes"][2][-1].packets,
        )
        self.assertTrue(decode_state(final["operation_packets"]))
        self.assertEqual(
            final["provider_identity"]["clock"]["module"],
            self.shared.runtime.clock.__module__,
        )
        self.assertEqual(
            final["provider_identity"]["clock"]["qualname"],
            self.shared.runtime.clock.__qualname__,
        )
        self.assertFalse(final["replay_qualified"])
        self.assertFalse(final["bootstrap_available"])
        self.assertFalse(final["dispatch_observed"])
        self.assertIsNone(current_shared_incident())

    def test_stale_session_rejection_is_captured_before_operation(self):
        stale = Session(1, 100, "stale", 1134, 0)
        called = []
        with self.assertRaisesRegex(ValueError, "Stale combat session lease"):
            self.registry.execute(
                88,
                stale,
                100,
                lambda *args: called.append(True),
                incident_request=dict(opcode=13260, body=b"exact-original-request"),
            )
        self.assertEqual(called, [])
        self.assertEqual(len(self.receipts), 1)
        receipt = self.receipts[0]
        self.assertEqual(receipt["status"], "raised")
        self.assertEqual(self.state(receipt)["sequence"], 0)
        self.assertEqual(decode_state(receipt["request"])["session"], stale)
        self.assertEqual(
            decode_state(receipt["request"])["wire_request"],
            dict(opcode=13260, body=b"exact-original-request"),
        )
        self.assertFalse(decode_state(receipt["lease_observations"])[0]["result"])
        self.assertFalse(receipt["return_recorded"])

    def test_postprocess_rejection_retains_operation_packets_without_adoption(self):
        failure = ValueError("accepted ACK boundary rejected")
        before_fight, before_runtime = self.shared.fight, self.shared.runtime
        with patch.object(self.registry, "_accepted_ack", side_effect=failure):
            with self.assertRaises(ValueError) as raised:
                self.end()
        self.assertIs(raised.exception, failure)
        self.assertIs(self.shared.fight, before_fight)
        self.assertIs(self.shared.runtime, before_runtime)
        receipt = self.receipts[0]
        self.assertTrue(decode_state(receipt["operation_packets"]))
        self.assertEqual(self.state(receipt)["sequence"], 0)
        self.assertEqual(self.state(receipt)["outboxes"], {1: (), 2: ()})
        self.assertEqual(receipt["error"]["message"], str(failure))

    def test_failed_final_ack_keeps_original_barrier_mutation_and_exception(self):
        self.end()
        body = struct.pack(">i", self.shared.ack.turn)
        self.registry.acknowledge(88, self.one, body, lambda *args: [])
        failure = ValueError("release callback rejected")

        def reject(*args):
            raise failure

        with self.assertRaises(ValueError) as raised:
            self.registry.acknowledge(88, self.two, body, reject)
        self.assertIs(raised.exception, failure)
        receipt = self.receipts[-1]
        self.assertEqual(self.state(receipt, "before")["ack"].received, {1})
        self.assertEqual(self.state(receipt)["ack"].received, {1, 2})
        self.assertEqual(self.state(receipt)["sequence"], 1)

    def test_inner_dispatch_helper_attaches_facts_without_second_receipt(self):
        helper = dispatch_fixture.IncidentDispatchIntegrationTests().helper(
            combat_session=self.one,
            TEST_MONSTERS_BY_ID={},
        )
        source = {"id": 100, "account_id": 1, "map_id": 1134}
        inner_scopes = []

        def operation(fight, runtime):
            with helper(
                runtime,
                "move",
                b"exact-move",
                source,
                b"deck",
                {100: source},
                {100: b"deck"},
            ) as incident:
                inner_scopes.append(incident)
                packets = [(13420, b"operation")]
                incident.packets(packets)
                return packets

        with patch(
            "wakfu_server.combat_incident_capture.incident_scope",
            side_effect=AssertionError("Nested receipt"),
        ):
            self.end(operation)
        self.assertEqual(len(self.receipts), 1)
        self.assertIsInstance(inner_scopes[0], SharedIncidentCapture)
        receipt = self.receipts[0]
        self.assertEqual(len(receipt["operations"]), 1)
        facts = decode_state(receipt["operations"][0])
        self.assertEqual(
            facts["action"], dict(type="move", body=b"exact-move", owner_id=1)
        )
        self.assertEqual(facts["inputs"]["deck_blob"], b"deck")
        self.assertEqual(
            decode_state(receipt["operation_packets"]), ((13420, b"operation"),)
        )

    def test_disabled_capture_does_not_encode_identify_or_replace_original_error(self):
        failure = ValueError("original operation error")

        def reject(*args):
            raise failure

        original_import = builtins.__import__
        imports = []

        def reject_diagnostic_import(name, *args, **kwargs):
            if name.endswith("combat_shared_incident_capture"):
                imports.append(name)
                raise ImportError("Diagnostic module unavailable")
            return original_import(name, *args, **kwargs)

        with patch.dict(os.environ, {"WAKFU_COMBAT_INCIDENT_DIR": ""}), patch(
            "builtins.__import__", side_effect=reject_diagnostic_import
        ):
            with self.assertRaises(ValueError) as raised:
                self.end(reject)
        self.assertIs(raised.exception, failure)
        self.assertEqual(len(self.fixture.rows), 1)
        self.assertEqual(self.receipts, [])
        self.assertEqual(imports, [])

    def test_enabled_diagnostic_import_failure_does_not_prevent_gameplay(self):
        original_import = builtins.__import__

        def reject_diagnostic_import(name, *args, **kwargs):
            if name.endswith("combat_shared_incident_capture"):
                raise ImportError("Diagnostic module unavailable")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=reject_diagnostic_import):
            self.assertEqual(self.end(lambda fight, runtime: []), 1)
        self.assertEqual(len(self.fixture.rows), 1)
        self.assertEqual(self.receipts, [])

    def test_offline_replay_suppresses_inherited_capture_and_nested_observers(self):
        payload = capture_shared_state(self.shared, registry=self.registry)
        restored = restore_shared_state(
            payload,
            [lease_result(self.one, result=True)],
            bind_runtime=shared_fixture.bind_clock,
        )
        with patch(
            "wakfu_server.combat_input_observation.observe_combat_inputs",
            side_effect=AssertionError("Offline nested observer"),
        ):
            self.assertEqual(
                replay_execute(restored, self.one, 100, lambda fight, runtime: []), 1
            )
        self.assertEqual(self.receipts, [])
        self.assertFalse(shared_incidents_suppressed())
        self.assertIsNone(current_shared_incident())
        # Partial ACK must likewise retain its state without writing a receipt.
        shared = restored[1]
        shared.ack.arm(7, [self.one, self.two])
        payload = capture_shared_state(shared, registry=restored[0])
        ack_restore = restore_shared_state(
            payload,
            [lease_result(self.one, result=True)],
            bind_runtime=shared_fixture.bind_clock,
        )
        with patch(
            "wakfu_server.combat_input_observation.observe_combat_inputs",
            side_effect=AssertionError("Offline nested observer"),
        ):
            self.assertFalse(
                replay_acknowledge(ack_restore, self.one, struct.pack(">i", 7))
            )
        self.assertEqual(self.receipts, [])
        self.assertEqual(ack_restore[1].ack.received, {1})

    def test_unknown_lease_result_and_failed_snapshots_remain_unqualified(self):
        self.registry.live_session = lambda session: "truthy-original-result"
        self.shared.join_context = {"unknown_provider": lambda *args: None}
        self.end(lambda fight, runtime: [])
        receipt = self.receipts[0]
        self.assertIsNone(receipt["before"])
        self.assertIsNone(receipt["after"])
        self.assertFalse(receipt["replay_qualified"])
        self.assertTrue(
            any("Lease observation failed" in item for item in receipt["incomplete"])
        )
        self.assertTrue(
            any(
                "Before shared-state capture failed" in item
                for item in receipt["incomplete"]
            )
        )
        self.assertEqual(receipt["return_value"], 1)

    def test_writer_failure_cannot_replace_gameplay_exception(self):
        failure = ValueError("gameplay rejection")

        def reject(*args):
            raise failure

        with patch(
            "wakfu_server.combat_incident_capture._enqueue",
            side_effect=RuntimeError("diagnostic writer rejected"),
        ):
            with self.assertRaises(ValueError) as raised:
                self.end(reject)
        self.assertIs(raised.exception, failure)
        self.assertIsNone(current_shared_incident())


if __name__ == "__main__":
    unittest.main()
