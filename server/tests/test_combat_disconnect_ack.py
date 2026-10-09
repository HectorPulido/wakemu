"""Disconnect removes a transport obligation, never fabricates a peer ACK."""
import struct
import unittest
import test_combat_shared as shared_fixtures


class Runtime:
    def __init__(self, fight):
        self.fight = fight
        self.awaiting_ack = 7
        self.calls = []

    def acknowledge_turn(self, body):
        self.calls.append(struct.unpack(">i", body)[0])
        self.awaiting_ack = None
        return [(13482, b"actual-next-turn")]


class DisconnectAckTests(unittest.TestCase):
    def setUp(self):
        setup = shared_fixtures.SharedCombatTests()
        setup.setUp()
        setup.join()
        self.registry, self.shared = setup.registry, setup.shared
        self.one, self.two = setup.one, setup.two
        self.shared.runtime = Runtime(self.shared.fight)
        self.registry.arm_ack(self.shared.fight.id, 7)

    def test_disconnect_waits_for_actual_remaining_peer_ack(self):
        self.registry.disconnect(self.one)
        self.assertEqual(self.shared.ack.expected, {2: "second"})
        self.assertEqual(self.shared.ack.received, set())
        self.assertEqual(self.shared.runtime.calls, [])
        released = self.registry.acknowledge(
            self.shared.fight.id,
            self.two,
            struct.pack(">i", 7),
            lambda fight, runtime, body: runtime.acknowledge_turn(body),
        )
        self.assertTrue(released)
        self.assertEqual(self.shared.runtime.calls, [7])

    def test_already_received_peer_ack_releases_once_on_disconnect(self):
        self.assertFalse(
            self.registry.acknowledge(
                self.shared.fight.id,
                self.two,
                struct.pack(">i", 7),
                lambda *args: self.fail("Other recipient still pending"),
            )
        )
        self.registry.disconnect(self.one)
        self.assertEqual(self.shared.runtime.calls, [7])
        self.assertIsNone(self.shared.ack.turn)
        self.registry.disconnect(self.one)
        self.assertEqual(self.shared.runtime.calls, [7])

    def test_last_owner_disconnect_preserves_reconnect_ack(self):
        self.registry.disconnect(self.one)
        self.registry.disconnect(self.two)
        self.assertEqual(self.shared.ack.expected, {2: "second"})
        self.assertEqual(self.shared.runtime.calls, [])
