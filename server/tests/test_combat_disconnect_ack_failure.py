"""Transport removal survives a failed private native ACK release."""
import struct
import unittest
from unittest.mock import patch

import test_combat_shared_reproduction as shared_fixture
from wakfu_server.combat_reproduction import controlled_environment
from wakfu_server.combat_reproduction_state import encode_state
from wakfu_server.combat_runtime_messages import RuntimeMessages


class DisconnectAckFailureTests(unittest.TestCase):
    def test_failed_disconnect_release_keeps_departed_owner_fenced_and_real_ack_retryable(
        self,
    ):
        fixture = shared_fixture.SharedReproductionTests()
        fixture.setUp()
        registry, shared = fixture.registry, fixture.shared
        with controlled_environment(shared_fixture.CLOCKS, shared_fixture.POLICIES):
            fixture.end_turn()
            body = struct.pack(">i", shared.ack.turn)
            release = lambda fight, runtime, value: runtime.acknowledge_turn(value)
            self.assertFalse(registry.acknowledge(88, fixture.one, body, release))
            registry.drain(88, fixture.one)
            registry.drain(88, fixture.two)
            fight, runtime = shared.fight, shared.runtime
            before = encode_state(runtime)
            sequence = shared.sequence
            original = RuntimeMessages.acknowledge_turn
            attempts = []

            def fail_after_private_release(candidate, value):
                packets = original(candidate, value)
                self.assertTrue(packets)
                self.assertIsNot(candidate, runtime)
                self.assertIsNot(candidate.fight, fight)
                attempts.append(value)
                raise ValueError("injected private release failure")

            with patch.object(
                RuntimeMessages, "acknowledge_turn", fail_after_private_release
            ):
                with self.assertRaisesRegex(ValueError, "private release failure"):
                    registry.disconnect(fixture.two)
            self.assertEqual(attempts, [body])
            self.assertEqual(shared.connected, {fixture.one.account_id})
            self.assertEqual(shared.ack.expected, {1: "first"})
            self.assertEqual(shared.ack.received, {1})
            self.assertTrue(shared.ack.complete)
            self.assertIsNotNone(shared.ack.turn)
            self.assertIs(shared.fight, fight)
            self.assertIs(shared.runtime, runtime)
            self.assertEqual(encode_state(runtime), before)
            self.assertEqual(shared.sequence, sequence)
            self.assertFalse(shared.outboxes[1])
            self.assertFalse(shared.outboxes[2])
            with self.assertRaisesRegex(ValueError, "membership"):
                registry.acknowledge(88, fixture.two, body, release)
            self.assertEqual(encode_state(runtime), before)
            # A's duplicate real ACK retries the native release. No transport
            # departure manufactures an ACK or a turn transition on failure.
            self.assertTrue(registry.acknowledge(88, fixture.one, body, release))
            self.assertIsNone(shared.ack.turn)
            self.assertIsNone(shared.runtime.awaiting_ack)
            self.assertEqual(shared.sequence, sequence + 1)
            self.assertEqual(len(shared.outboxes[1]), 1)
            self.assertFalse(shared.outboxes[2])
            completed = encode_state(shared.runtime)
            with self.assertRaisesRegex(ValueError, "stale shared turn ACK"):
                registry.acknowledge(88, fixture.one, body, release)
            self.assertEqual(encode_state(shared.runtime), completed)
            self.assertEqual(shared.sequence, sequence + 1)
