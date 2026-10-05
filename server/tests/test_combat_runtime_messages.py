import struct, unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from protocol_codec import decode_body
from wakfu_server.combat_wire import decode_actor_state


class RuntimeMessageTests(unittest.TestCase):
    def test_inactivity_expiration_once_keeps_ack_and_starts_next_clock_on_ack(self):
        fight, _ = self.state()
        now = [10.0]
        wire = RuntimeMessages(fight, clock=lambda: now[0])
        wire.turn_started()
        self.assertEqual(wire.turn_deadline, 40)
        now[0] = 39.99
        self.assertEqual(wire.expire_current_once(), [])
        now[0] = 40
        self.assertEqual([op for op, _ in wire.expire_current_once()], [12502, 13420])
        self.assertEqual((fight.turn_id, wire.awaiting_ack), (2, 1))
        now[0] = 1000
        self.assertEqual(wire.expire_current_once(), [])
        self.assertIsNone(wire.turn_deadline)
        with self.assertRaises(ValueError):
            wire.end_turn(1, 100, 1)
        wire.acknowledge_turn(struct.pack(">i", 1))
        self.assertEqual(wire.turn_deadline, 1030)
        # AI turns are advanced by the AI owner, not the player idle policy.
        now[0] = 2000
        self.assertEqual(wire.expire_current_once(), [])
        wire.end_server_turn(-200, 2)
        now[0] = 3000
        wire.acknowledge_turn(struct.pack(">i", 2))
        self.assertEqual(wire.turn_deadline, 3030)
        wire.end_turn(1, 100, 2)
        self.assertEqual(wire.expire_current_once(), [])

    def test_rejected_expiry_recovers_same_turn_and_rearms_without_partial_commit(self):
        from wakfu_server.combat_conditions import UnknownCondition
        from wakfu_server.combat_geometry_snapshot import source_snapshot

        fight, _ = self.state()
        now = [0.0]
        calls = []

        def reject(candidate, **boundary):
            calls.append(boundary["actor_id"])
            candidate.current.hp -= 5
            candidate.current.ap = 0
            raise UnknownCondition("unverified native predicate")

        wire = RuntimeMessages(fight, clock=lambda: now[0], turn_end_provider=reject)
        wire.turn_started()
        before = source_snapshot(fight)
        now[0] = 31.0
        packets, error = wire.expire_current_or_recover(1, now_ms=31000)
        self.assertEqual(error, "unverified native predicate")
        self.assertEqual([op for op, _ in packets], [12053, 13482, 13420])
        self.assertEqual(source_snapshot(fight), before)
        self.assertEqual((fight.turn_id, fight.current.id), (1, 100))
        self.assertIsNone(wire.awaiting_ack)
        self.assertEqual(wire.pending, [])
        self.assertEqual(wire.turn_deadline, 61.0)
        self.assertEqual(wire.expire_current_or_recover(1, now_ms=31000), ([], None))
        self.assertEqual(calls, [100])
        with self.assertRaises(UnknownCondition):
            wire.end_turn(1, 100, 1)
        self.assertEqual(source_snapshot(fight), before)

    def test_dead_or_terminal_actor_cannot_expire(self):
        fight, _ = self.state()
        now = [0.0]
        wire = RuntimeMessages(fight, clock=lambda: now[0])
        wire.turn_started()
        now[0] = 31
        fight.current.hp = 0
        self.assertEqual(wire.expire_current_once(), [])
        fight.current.hp = 60
        fight.phase = "finished"
        self.assertEqual(wire.expire_current_once(), [])

    def state(self):
        cells = {(0, 0, 0), (1, 0, 0)}
        f = Fight(
            7,
            [
                Actor(100, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
                Actor(-200, 1, (1, 0, 0), 20, 4, 2, 10, 1),
            ],
            cells,
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        f.ready(1)
        return f, RuntimeMessages(f)

    def test_start_and_end_use_ack_barrier_not_actor_turn_counter(self):
        fight, wire = self.state()
        packets = wire.combat_started(
            {100: (b"ownPC", b"\0\0"), -200: (b"ownNPC", b"\0\0")}
        )
        self.assertEqual(
            [op for op, b in packets],
            [
                12873,
                13912,
                12873,
                13912,
                12233,
                12514,
                13477,
                13420,
                13337,
                13420,
                13482,
                13420,
            ],
        )
        self.assertEqual(
            decode_body("in", 13337, next(body for op, body in packets if op == 13337))[
                "actor_id"
            ],
            100,
        )
        self.assertEqual(decode_actor_state(12873, packets[0][1])["state"], b"ownPC")
        self.assertEqual(decode_actor_state(13912, packets[1][1])["state"], b"\0\0")
        self.assertEqual(
            struct.unpack(">h", next(body for op, body in packets if op == 13477)[12:])[
                0
            ],
            1,
        )
        ended = wire.end_turn(1, 100, 1)
        self.assertEqual([op for op, b in ended], [12502, 13420])
        with self.assertRaises(ValueError):
            wire.acknowledge_turn(struct.pack(">i", 99))
        self.assertEqual(wire.awaiting_ack, 1)
        next_turn = wire.acknowledge_turn(struct.pack(">i", 1))
        self.assertEqual(decode_body("in", 13337, next_turn[0][1])["actor_id"], -200)
        wire.end_server_turn(-200, 2)
        second_round = wire.acknowledge_turn(struct.pack(">i", 2))
        self.assertEqual(second_round[0][0], 13477)
        self.assertEqual(struct.unpack(">h", second_round[0][1][12:])[0], 2)
        self.assertEqual((fight.turn_id, fight.current.turn_count), (3, 2))
        with self.assertRaises(ValueError):
            wire.end_turn(1, 100, 3)
        wire.end_turn(1, 100, 2)

    def test_interruption_clears_pending_and_emits_native_outside_fight(self):
        f, wire = self.state()
        wire.end_turn(1, 100, 1)
        messages = wire.interrupted_cleanup(100)
        self.assertEqual([op for op, b in messages], [12238, 13420, 13046])
        self.assertEqual(messages[0][1][-1], 1)
        self.assertEqual(
            messages[-1][1], struct.pack(">qh", 100, 5) + b"\x11\xff\xff\xff\xff"
        )
        self.assertIsNone(wire.awaiting_ack)
        self.assertEqual(f.phase, "finished")

    def test_next_turn_stats_refreshes_replenished_resources_after_ack(self):
        fight, _ = self.state()
        wire = RuntimeMessages(
            fight, stats_serializer=lambda actor: struct.pack(">ii", actor.ap, actor.mp)
        )
        fight.spend(1, 100, mp=1)
        self.assertEqual(fight.actors[100].mp, 2)
        wire.end_turn(1, 100, 1)
        next_packets = wire.acknowledge_turn(struct.pack(">i", 1))
        self.assertEqual(next_packets[0][0], 12873)
        npc = fight.current
        wire.end_server_turn(npc.id, fight.turn_id)
        packets = wire.acknowledge_turn(struct.pack(">i", 2))
        self.assertEqual(fight.current.id, 100)
        decoded = decode_actor_state(12873, packets[0][1])
        self.assertEqual(struct.unpack(">ii", decoded["state"]), (6, 3))
