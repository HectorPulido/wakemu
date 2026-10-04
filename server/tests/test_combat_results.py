import struct, unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_results import (
    fight_report,
    finish_messages,
    continuation,
    outside_fight_updates,
)
from wakfu_server.wire import proto_fields


class FightResultTests(unittest.TestCase):
    def state(self):
        f = Fight(
            7,
            [
                Actor(100, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
                Actor(-200, 1, (1, 0, 0), 12, 4, 2, 10, 1),
            ],
            [(0, 0, 0), (1, 0, 0)],
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        f.ready(1)
        f.apply_damage(100, -200, 12)
        metadata = {
            100: dict(
                kind="player", account_id=1, name="Prueba local", breed=2, is_male=True
            ),
            -200: dict(kind="monster", ref=5525),
        }
        return f, RuntimeMessages(f), metadata

    def test_report_includes_required_fields_own_ids_and_no_loot(self):
        f, r, m = self.state()
        report = fight_report(
            f, m, duration_ms=6000, fight_instance_id=8, initiator_id=100
        )
        fields = dict(proto_fields(report))
        self.assertEqual(set(fields), {8, 16, 24, 32, 42, 50, 56, 64, 112})
        self.assertEqual(
            (fields[8], fields[32], fields[56], fields[112]), (7, 0, 100, 8)
        )
        team0 = dict(proto_fields(fields[42]))
        player = dict(proto_fields(team0[18]))
        self.assertEqual(
            (player[8], player[16], player[26], player[72]),
            (100, 1, b"Prueba local", 0),
        )
        self.assertNotIn(58, player)  # No FightLoot entries.
        team1 = dict(proto_fields(fields[50]))
        npc = dict(proto_fields(team1[26]))
        self.assertEqual((npc[8] - (1 << 64), npc[24]), (-200, 5525))
        packets = finish_messages(
            r, m, duration_ms=6000, fight_instance_id=8, initiator_id=100
        )
        self.assertEqual([op for op, b in packets], [12238, 12755])
        self.assertEqual(
            packets[0][1][12:],
            b"\0\1" + struct.pack(">q", 100) + b"\1" + struct.pack(">q", -200) + b"\0",
        )
        self.assertTrue(continuation(7, struct.pack(">iB", 7, 1)))
        with self.assertRaises(ValueError):
            continuation(7, struct.pack(">iB", 8, 1))
        self.assertEqual(
            outside_fight_updates(f)[0][1],
            struct.pack(">qh", 100, 5) + b"\x11\xff\xff\xff\xff",
        )

    def test_report_turn_count_is_rounds_not_global_actor_turns(self):
        f, r, m = self.state()
        f.phase = "active"
        f.winner = None
        f.actors[-200].hp = 12
        f.order = [100, -200]
        f.end_turn(1, 100, 1)
        f.end_server_turn(-200, 2)
        f.apply_damage(100, -200, 12)
        self.assertEqual(f.turn_id, 3)
        report = fight_report(
            f, m, duration_ms=1, fight_instance_id=8, initiator_id=100
        )
        self.assertEqual(dict(proto_fields(report))[24], 2)

    def test_rejects_unfinished_state_and_foreign_owner(self):
        f, r, m = self.state()
        m[100]["account_id"] = 2
        with self.assertRaises(ValueError):
            fight_report(f, m, duration_ms=6000, fight_instance_id=8, initiator_id=100)
        m[100]["account_id"] = 1
        f.phase = "active"
        with self.assertRaises(ValueError):
            fight_report(f, m, duration_ms=6000, fight_instance_id=8, initiator_id=100)
