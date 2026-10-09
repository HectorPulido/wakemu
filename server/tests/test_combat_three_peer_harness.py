"""Offline coverage for placement/active branches of the three-owner harness."""

import struct
import unittest
from collections import deque

from tools.three_peer_harness import initial_survivor_turns


def turn_packet(fight_id, action_id, actor_id):
    return struct.pack(">iiiq", fight_id, action_id, -1, actor_id) + b"\x00" * 8


class FakePeer:
    def __init__(self, events):
        self.events = deque(events)
        self.sent = []

    def wait(self, opcode, timeout):
        actual, body = self.events.popleft()
        if actual != opcode:
            raise AssertionError(f"expected {opcode}, got {actual}")
        return body, [(actual, body)]

    def wait_any(self, opcodes, timeout):
        event = self.events.popleft()
        if event[0] not in opcodes:
            raise AssertionError(f"unexpected opcode {event[0]}")
        return event, [event]

    def send(self, opcode, body):
        self.sent.append((opcode, body))


class ThreePeerHarnessTurnTests(unittest.TestCase):
    def test_placement_mode_returns_identical_turn_and_keeps_ack_sequence(self):
        body = turn_packet(77, 1, 20)
        peer_b = FakePeer([(13482, body)])
        peer_c = FakePeer([(13482, body)])

        result = initial_survivor_turns(
            "placement", peer_b, peer_c, 77, {20, 30, -400}, {10}, ack_turn=1
        )

        self.assertEqual(result, (body, body, 1))
        self.assertEqual(peer_b.sent, [])
        self.assertEqual(peer_c.sent, [])

    def test_active_mode_acks_withdrawn_turn_and_selects_next_survivor(self):
        withdrawn_turn = turn_packet(77, 1, 10)
        survivor_turn = turn_packet(77, 2, 20)
        events = [
            (13482, withdrawn_turn),
            (12502, b"boundary"),
            (13482, survivor_turn),
        ]
        peer_b = FakePeer(events)
        peer_c = FakePeer(events)

        result = initial_survivor_turns(
            "active", peer_b, peer_c, 77, {20, 30, -400}, {10}, ack_turn=1
        )

        self.assertEqual(result, (survivor_turn, survivor_turn, 2))
        self.assertEqual(peer_b.sent, [(13510, struct.pack(">i", 1))])
        self.assertEqual(peer_c.sent, [(13510, struct.pack(">i", 1))])


if __name__ == "__main__":
    unittest.main()
