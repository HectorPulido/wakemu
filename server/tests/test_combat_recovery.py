import unittest, struct
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_recovery import recovery_packet, timeline


class RecoveryTests(unittest.TestCase):
    def state(self):
        actors = [
            Actor(5, 0, (0, 0, 0), 60, 6, 3, 0, 1, 9, True),
            Actor(-200, 1, (1, 0, 0), 12, 6, 3, 5, 1),
            Actor(-201, 1, (0, 1, 0), 12, 6, 3, 5, 1),
        ]
        f = Fight(
            190982470,
            actors,
            {a.position for a in actors},
            {0: {actors[0].position}, 1: {actors[1].position, actors[2].position}},
        )
        f.ready(9)
        while not f.current.controlled:
            f.end_server_turn(f.current.id, f.turn_id)
        return f, RuntimeMessages(f)

    def test_death_recovery_preserves_live_turn_and_exact_ack(self):
        f, r = self.state()
        f.apply_damage(5, -200, 12)
        r.end_turn(9, 5, f.current.turn_count)
        packets = r.recover(9, struct.pack(">i", f.id), now_ms=1000)
        self.assertEqual([x[0] for x in packets], [12053, 13482, 13420])
        self.assertIsNone(r.awaiting_ack)
        self.assertEqual(r.pending, [])
        raw = packets[0][1]
        self.assertEqual(struct.unpack_from(">ih", raw), (f.id, len(raw) - 6))
        self.assertEqual(raw[6:13], struct.pack(">BBiB", 1, 0, 6, 0))
        state = timeline(f, deadline_ms=31000)
        self.assertEqual(raw[15:], state)
        self.assertEqual(
            struct.unpack_from(">hiBq", state),
            (f.current.turn_count, f.turn_id, 1, 31000),
        )
        count = state[15]
        native_order = list(struct.unpack_from(">" + str(count) + "q", state, 16))
        self.assertEqual(native_order, f.order)
        self.assertEqual(native_order[f.order.index(f.current.id)], f.current.id)
        with self.assertRaises(ValueError):
            r.acknowledge_turn(struct.pack(">i", 1))
        previous = f.turn_id
        r.end_server_turn(f.current.id, previous)
        with self.assertRaises(ValueError):
            r.acknowledge_turn(struct.pack(">i", previous - 1))
        r.acknowledge_turn(struct.pack(">i", previous))

    def test_foreign_or_wrong_fight_cannot_clear_barrier(self):
        f, r = self.state()
        r.awaiting_ack = 4
        for owner, identity in [(11, f.id), (9, f.id + 1)]:
            with self.assertRaises(ValueError):
                r.recover(owner, struct.pack(">i", identity), now_ms=1000)
        self.assertEqual(r.awaiting_ack, 4)
