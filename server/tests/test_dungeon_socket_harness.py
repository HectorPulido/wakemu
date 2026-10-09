"""Regression checks for native rejection responses in the TLS harness."""
import sys
from pathlib import Path
import unittest
import struct
import queue
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import candidate_dungeon_socket_smoke as harness


class DoorRejectionTests(unittest.TestCase):
    def test_initial_reconnect_is_limited_to_entry_phase(self):
        self.assertTrue(harness.initial_reconnect_enabled("entry"))
        self.assertFalse(harness.initial_reconnect_enabled("full"))
        with self.assertRaises(ValueError):
            harness.initial_reconnect_enabled("unknown")

    def test_background_tls_failure_is_reported_before_join_send(self):
        peer = object.__new__(harness.Peer)
        peer.events = queue.Queue()
        peer.pending = []
        peer.events.put((None, EOFError("native peer closed")))
        with self.assertRaisesRegex(
            AssertionError, "opcode 13241: EOFError: native peer closed"
        ):
            peer.send(13241, b"")
        self.assertEqual(peer.events.qsize(), 1)

    def bootstrap(self, x):
        entity = struct.pack(
            ">BqBqiihqBBiihq", 28, 1, 0, 1, x, 0, 0, 1086, 3, 1, 0, 0, 0, 0
        )
        return struct.pack(">H", len(entity)) + entity

    def test_auto_room_accepts_already_consumed_native_return(self):
        peer = Mock()
        with patch.object(harness, "world_context", return_value=(1086, {})):
            harness.await_room_bootstrap(peer, self.bootstrap(5), 1086, {(5, 0, 0)})
        peer.wait.assert_not_called()

    def test_auto_room_waits_after_old_room_return(self):
        peer = Mock()
        peer.wait.return_value = (self.bootstrap(5), [])
        with patch.object(harness, "world_context", return_value=(1086, {})):
            harness.await_room_bootstrap(peer, self.bootstrap(0), 1086, {(5, 0, 0)})
        self.assertEqual(peer.wait.call_args.args, (13974,))

    def exercise(self, states):
        position = {"map_id": 1086, "instance_id": 7, "x": 0, "y": -27, "z": 0}
        peers = [Mock(), Mock()]
        with patch.object(
            harness.generic_transports, "source", return_value={}
        ), patch.object(harness, "approach_source"), patch.object(
            harness, "character_position", return_value=(position, (0, -27, 0))
        ), patch.object(
            harness, "room_state", side_effect=states
        ), patch.object(
            harness, "drain_bootstrap"
        ) as bootstrap:
            harness.door_request(
                Mock(),
                peers,
                [1, 2],
                1086,
                {"source_id": 26845, "destination_id": 2506},
                expect_rejection=True,
            )
            bootstrap.assert_called_once_with(peers[0], 1086)
            peers[0].wait.assert_not_called()

    def test_rejection_uses_bootstrap_and_preserves_durable_state(self):
        state = ({"current_room": 1}, [{"status": "available"}])
        self.exercise([state, state])

    def test_rejection_detects_unexpected_progression(self):
        with self.assertRaisesRegex(AssertionError, "changed dungeon progression"):
            self.exercise([({"current_room": 1}, []), ({"current_room": 2}, [])])
