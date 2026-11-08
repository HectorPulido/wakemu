"""Both QA consumers share cohort loading and owned native readiness."""
from pathlib import Path
from types import SimpleNamespace
import struct
import queue
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import rift_tls_party_e2e as runner


class ReconnectCohortTests(unittest.TestCase):
    def test_late_native_weapon_response_confirms_all_owners_and_keeps_latency(self):
        from wakfu_server.combat_weapon import animation

        body = animation(390, 123, 161, 29640, 230, (0, 0, 0), False)
        peers = []
        for _ in range(4):
            peer = object.__new__(runner.Peer)
            peer.pending = [(13509, body, 99.0), (13509, body, 120.3)]
            peer.events = queue.Queue()
            peer.wait_metrics = []
            peer.seen = [13509, 13509]
            peers.append(peer)
        with patch.object(runner.time, "monotonic", return_value=121.0):
            runner.wait_weapon_action(
                peers, peers[2], 390, 161, 29640, 100.0, {}, timeout=120
            )
        for peer in peers:
            self.assertEqual(peer.pending, [(13509, body, 99.0)])
            self.assertEqual(peer.wait_metrics[0]["since_send_ms"], 20300)

    def test_resume_rejects_missing_weapon_flag_before_opening_sockets(self):
        owners = [
            dict(username="rfnetqa_" + str(i), account_id=i, character=dict(id=i + 10))
            for i in range(4)
        ]
        state = dict(
            runs=[dict(fight_id=390, members=[10, 11, 12, 13])],
            fight=dict(status="active"),
        )
        args = SimpleNamespace(
            owners=4, wave=3, resume_fight_id=390, weapon_reference=None
        )
        with patch.object(
            runner, "observe", side_effect=[state, {"reference": 29640}]
        ), patch.object(runner, "connect") as connect:
            with self.assertRaisesRegex(ValueError, "--weapon-reference 29640"):
                runner.resume_existing_battle(args, owners, [], {}, {})
        connect.assert_not_called()

    def test_native_weapon_rejection_is_recorded_without_waiting_for_success(self):
        from wakfu_server.wire import chat

        reason = "Unarmed action requires the owned weapon slot to be empty"
        body = chat(dict(id=162, name="Consola local"), reason)

        def wait(opcodes, **kwargs):
            self.assertEqual(opcodes, {674, 13509})
            self.assertTrue(kwargs["predicate"](body))
            return 674, body

        peer = SimpleNamespace(wait=wait)
        result = {}
        with patch.object(runner, "wait_all") as others:
            with self.assertRaisesRegex(ValueError, reason):
                runner.wait_weapon_action([peer], peer, 390, 162, 2145, 1.0, result)
        others.assert_not_called()
        self.assertEqual(result["native_rejections"][0]["reason"], reason)

    def test_all_owners_connect_before_scene_waits_and_no_gameplay_is_issued(self):
        connected, sends, waits = [], [], []
        owners = [dict(account_id=index) for index in range(4)]

        def connect(args, owner, *, reconnect):
            self.assertTrue(reconnect)
            identity = owner["account_id"]
            connected.append(identity)

            def wait(opcode):
                self.assertEqual(connected, [0, 1, 2, 3])
                waits.append((identity, opcode))
                return opcode, b"bootstrap"

            return SimpleNamespace(
                wait=wait, send=lambda opcode: sends.append((identity, opcode))
            )

        control = struct.pack(">iiiq", 390, 0, -1, 151)
        peers = []
        with patch.object(runner, "connect", side_effect=connect), patch(
            "wakfu_server.combat_wire.decode_bootstrap",
            return_value=dict(fight_id=390, myG=struct.pack(">hi", 8, 84)),
        ), patch.object(
            runner, "resumed_control_record", return_value=control
        ) as ready:
            returned, current = runner.reconnect_owned_combat(
                SimpleNamespace(), owners, 390, peers=peers
            )
        self.assertIs(returned, peers)
        self.assertEqual(current, control)
        self.assertEqual(
            sends, [(owner, 12449) for owner in range(4) for _ in range(2)]
        )
        self.assertEqual(
            [opcode for owner, opcode in waits if owner == 0],
            [630, 711, 12436, 711, 12847],
        )
        self.assertEqual(ready.call_args.args[1:], (peers, 390, [84] * 4))
