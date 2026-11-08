"""A rejected old input consumes real successor barriers, never retries itself."""
from pathlib import Path
from types import SimpleNamespace
import queue
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import rift_tls_party_e2e as runner
from wakfu_server.combat_weapon import animation
from wakfu_server.wire import chat


class StaleTurnRecoveryTests(unittest.TestCase):
    def test_native_rejection_drains_queued_boundary_before_next_owned_action(self):
        next_turn = struct.pack(">iiiq", 390, 250, -1, 159)
        reason = "Acción rechazada: Not current owned turn"
        peers, sends = [], []
        for index in range(4):
            peer = object.__new__(runner.Peer)
            peer.pending = [
                (12502, struct.pack(">iiiqii", 390, 250, -1, 162, -1, 0), 10.5)
            ]
            peer.events, peer.wait_metrics, peer.seen = queue.Queue(), [], []
            peer.last_received_at = 10.0

            def send(opcode, body, owner=index, target=peer):
                sends.append((owner, opcode, body))
                target.pending.append((13482, next_turn, 13.0))
                return 12.5

            peer.send = send
            peers.append(peer)
        peers[2].pending.append(
            (674, chat(dict(id=162, name="Consola local"), reason), 12.0)
        )
        result, actions = {}, {"acks_sent": 0}
        previous = dict(
            phase="active",
            turn_id=197,
            current_actor_id=162,
            runtime={"awaiting_ack": None},
        )
        changed = dict(
            id=390,
            phase="active",
            turn_id=198,
            current_actor_id=159,
            runtime={"awaiting_ack": 197, "native_action_id": 250},
        )
        with patch.object(runner.time, "monotonic", return_value=14.0), patch.object(
            runner, "observe", return_value=changed
        ):
            with self.assertRaises(runner.NativeActionRejected) as caught:
                runner.wait_weapon_action(
                    peers, peers[2], 390, 162, 29640, 11.0, result
                )
            current = runner.recover_stale_weapon_turn(
                SimpleNamespace(wave=3, action_timeout=1),
                peers,
                390,
                162,
                previous,
                caught.exception,
                since=[10.0] * 4,
                actions=actions,
                result=result,
            )
            self.assertEqual(current, next_turn)
            self.assertEqual(
                sends, [(i, 13510, struct.pack(">i", 197)) for i in range(4)]
            )
            self.assertEqual(actions["acks_sent"], 4)
            body = animation(390, 251, 159, 29640, 230, (0, 0, 0), False)
            for peer in peers:
                peer.pending.append((13509, body, 13.5))
            runner.wait_weapon_action(peers, peers[0], 390, 159, 29640, 13.1, result)
        self.assertEqual(len(result["native_rejections"]), 1)
        self.assertEqual(len(result["stale_turn_recoveries"]), 1)

    def test_unrelated_or_unconfirmed_rejection_is_not_suppressed(self):
        previous = dict(
            phase="active",
            turn_id=197,
            current_actor_id=162,
            runtime={"awaiting_ack": None},
        )
        for reason in ("Not current owned turn", "Invalid weapon target"):
            with self.subTest(reason=reason), patch.object(
                runner, "observe", return_value=previous
            ), patch.object(runner, "drain_turn_boundaries") as drain:
                with self.assertRaises(runner.NativeActionRejected):
                    runner.recover_stale_weapon_turn(
                        SimpleNamespace(wave=3),
                        [],
                        390,
                        162,
                        previous,
                        runner.NativeActionRejected(reason),
                        since=[],
                        actions={},
                        result={},
                    )
                drain.assert_not_called()
