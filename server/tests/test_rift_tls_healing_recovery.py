import queue
import struct
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server" / "tools"))

import rift_tls_party_e2e as runner


def timeline_packet(fight_id, *, phase, turn, current):
    # Native SU timeline fixture consumed by decode_core_packet(12053).
    su = (
        struct.pack(">hiBq", phase, turn, 1, current)
        + b"\x01"
        + struct.pack(">q", current)
        + b"\x01"
        + struct.pack(">q", current)
        + b"\x01"
        + struct.pack(">qh", current, 1)
        + b"\x00"  # index into the one-member order
        + b"\x00"  # removed members
        + b"\x00"
    )  # bonuses
    envelope = struct.pack(">BBiBh", 1, 0, 6, 0, len(su)) + su
    return struct.pack(">ih", fight_id, len(envelope)) + envelope


class FakePeer:
    def __init__(self, events=()):
        self.pending = list(events)
        self.events = queue.Queue()
        self.sent = []
        self.last_received_at = None

    def send(self, opcode, body=b""):
        self.sent.append((opcode, body))
        return 5.0


class RiftTLSHealingRecoveryTests(unittest.TestCase):
    def test_native_between_recovery_requires_all_real_start_turn_events(self):
        from test_combat_recovery import RecoveryTests
        from wakfu_server.combat_recovery import timeline
        from wakfu_server.combat_core_reconstruction import UnknownCoreLayout

        fight, _ = RecoveryTests().state()
        payload = timeline(fight, deadline_ms=31000, new_turn=True)
        envelope = struct.pack(">BBiBh", 1, 0, 6, 0, len(payload)) + payload
        body = struct.pack(">ih", fight.id, len(envelope)) + envelope
        decoded = runner.decode_owned_recovery(body)
        self.assertEqual(decoded["timeline"]["phase"], 2)
        self.assertIsNone(decoded["timeline"]["current"])
        self.assertEqual(decoded["timeline"]["turn"], fight.turn_id - 1)
        start = struct.pack(">iiiq", fight.id, 37, -1, fight.current.id)
        peers = [FakePeer([(12053, body, 7.0), (13482, start, 8.0)]) for _ in range(4)]
        checkpoint = dict(
            phase="active",
            turn_id=fight.turn_id,
            current_actor_id=fight.current.id,
            runtime={"awaiting_ack": None},
        )
        with patch.object(runner, "observe", return_value=checkpoint):
            record = runner.resumed_control_record(
                SimpleNamespace(wave=3), peers, fight.id, [1] * 4
            )
        self.assertEqual(record, start)
        self.assertTrue(all(not peer.pending and not peer.sent for peer in peers))
        unknown = bytearray(body)
        unknown[21] = 3
        with self.assertRaises(UnknownCoreLayout):
            runner.decode_owned_recovery(bytes(unknown))
        with self.assertRaises(ValueError):
            runner.decode_owned_recovery(body[:-1])

    def test_critical_hp_can_approach_distant_orb_using_only_remaining_mp(self):
        cells = [[x, 0, 0] for x in range(6)]
        checkpoint = dict(
            phase="active",
            current_actor_id=10,
            movement_actor_id=10,
            movement_blocked_cells=[],
            runtime={"awaiting_ack": None},
            actors={"10": dict(id=10, hp=29, max_hp=100, mp=3, position=cells[0])},
            healing_orbs=[
                dict(
                    reference=1574,
                    native_area_contract="faY",
                    native_qq_bhi=False,
                    cell=cells[-1],
                )
            ],
            walkable=cells,
            edges=[[cells[x], cells[x + 1]] for x in range(5)],
        )
        self.assertEqual(
            runner.healing_orb_route(checkpoint, {}, 10),
            [tuple(cell) for cell in cells[1:4]],
        )
        checkpoint["actors"]["10"]["hp"] = 70
        self.assertEqual(runner.healing_orb_route(checkpoint, {}, 10), [])
        checkpoint["actors"]["10"]["hp"] = 29
        checkpoint["actors"]["20"] = dict(id=20, hp=50, position=cells[2])
        checkpoint["movement_blocked_cells"] = [cells[2]]
        self.assertEqual(runner.healing_orb_route(checkpoint, {}, 10), [])

    def test_orb_route_uses_native_faY_area_and_only_when_injured(self):
        checkpoint = {
            "phase": "active",
            "current_actor_id": 10,
            "movement_actor_id": 10,
            "movement_blocked_cells": [],
            "runtime": {"awaiting_ack": None},
            "actors": {
                "10": {"id": 10, "hp": 40, "max_hp": 100, "mp": 2, "position": [0, 0]},
                "20": {"id": 20, "hp": 50, "max_hp": 100, "position": [3, 0]},
            },
            "healing_orbs": [
                {
                    "reference": 1574,
                    "native_area_contract": "faY",
                    "native_qq_bhi": True,
                    "cell": [1, 0],
                },
                {
                    "reference": 1574,
                    "native_area_contract": "faY",
                    "native_qq_bhi": True,
                    "cell": [0, 1],
                },
                {
                    "reference": 1574,
                    "native_area_contract": "faY",
                    "native_qq_bhi": False,
                    "cell": [1, 0],
                },
                {
                    "reference": 1574,
                    "native_area_contract": "faY",
                    "native_qq_bhi": False,
                    "cell": [3, 0],
                    "executing": True,
                },
                {
                    "reference": 1574,
                    "native_area_contract": "faY",
                    "native_qq_bhi": False,
                    "cell": [2, 0],
                    "remaining_activations": 0,
                },
            ],
            "walkable": [[0, 0], [1, 0], [0, 1], [2, 0]],
            "edges": [[[0, 0], [1, 0]], [[0, 0], [0, 1]], [[1, 0], [2, 0]]],
        }
        self.assertEqual(runner.healing_orb_route(checkpoint, {}, 10), [(1, 0)])
        checkpoint["actors"]["10"]["hp"] = 70
        self.assertEqual(runner.healing_orb_route(checkpoint, {}, 10), [])
        checkpoint["actors"]["10"]["hp"] = 40
        checkpoint["runtime"]["awaiting_ack"] = 3
        self.assertEqual(runner.healing_orb_route(checkpoint, {}, 10), [])

    def test_resumed_core_timeline_returns_local_control_without_forged_packet(self):
        body = timeline_packet(390, phase=1, turn=4, current=151)
        peers = [FakePeer([(12053, body, 7.0)]) for _ in range(4)]
        checkpoint = {
            "phase": "active",
            "turn_id": 4,
            "current_actor_id": 151,
            "runtime": {"awaiting_ack": None},
        }
        with patch.object(runner, "observe", return_value=checkpoint):
            record = runner.resumed_control_record(
                SimpleNamespace(wave=3), peers, 390, [3] * 4
            )
        self.assertEqual(struct.unpack(">iiiq", record), (390, 0, -1, 151))
        self.assertTrue(all(peer.sent == [] for peer in peers))

    def test_native_ack_marker_acks_durable_counter_before_accepting_timeline(self):
        old = timeline_packet(390, phase=0, turn=3, current=151)
        current = timeline_packet(390, phase=1, turn=4, current=151)
        peers = [FakePeer([(12502, b"", 6.0), (12053, current, 7.0)]) for _ in range(4)]
        awaiting = {
            "phase": "active",
            "turn_id": 4,
            "current_actor_id": 151,
            "runtime": {"awaiting_ack": 3},
        }
        ready = {
            "phase": "active",
            "turn_id": 4,
            "current_actor_id": 151,
            "runtime": {"awaiting_ack": None},
        }
        with patch.object(runner, "observe", side_effect=[awaiting, ready]) as observe:
            record = runner.resumed_control_record(
                SimpleNamespace(wave=3), peers, 390, [2] * 4
            )
        self.assertEqual(struct.unpack(">iiiq", record), (390, 0, -1, 151))
        self.assertEqual(
            [peer.sent for peer in peers],
            [[(13510, struct.pack(">i", 3))] for _ in peers],
        )
        self.assertEqual(observe.call_count, 2)


if __name__ == "__main__":
    unittest.main()
