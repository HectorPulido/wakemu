import struct, unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from protocol_codec import decode_body
from wakfu_server.combat_wire import decode_actor_state


class RuntimeMessageTests(unittest.TestCase):
    def test_terminal_start_reaction_ack_delivers_pending_without_turn_owner(self):
        fight, _ = self.state()
        wire = RuntimeMessages(fight, clock=lambda: 0.0)
        wire.awaiting_ack = fight.turn_id
        wire.pending = [(13420, b"terminal reaction")]
        wire.native_timeline_restore_pending_turn = fight.turn_id
        wire.turn_deadline, wire.deadline_turn = 30, fight.turn_id
        fight.phase = "finished"
        result = wire.acknowledge_turn(struct.pack(">i", fight.turn_id))
        self.assertEqual(list(result), [(13420, b"terminal reaction")])
        self.assertIsNone(wire.awaiting_ack)
        self.assertEqual(wire.pending, [])
        self.assertIsNone(wire.turn_deadline)
        self.assertIsNone(wire.deadline_turn)
        self.assertIsNone(wire.native_timeline_restore_pending_turn)

    def test_multiowner_initial_start_restores_authoritative_su_once(self):
        actors = [
            Actor(100, 0, (0, 0, 0), 60, 6, 3, 1000, 1, 1, True),
            Actor(200, 0, (1, 0, 0), 60, 6, 3, 900, 1, 2, True),
            Actor(-200, 1, (2, 0, 0), 20, 4, 2, 100, 1),
        ]
        cells = {actor.position for actor in actors}
        fight = Fight(
            88,
            actors,
            cells,
            {0: {actors[0].position, actors[1].position}, 1: {actors[2].position}},
        )
        fight.ready(1)
        fight.ready(2)
        server_order = tuple(fight.order)
        server_current = fight.current.id
        runtime = RuntimeMessages(fight, clock=lambda: 0.0)

        packets = runtime.combat_started(
            {actor.id: (b"native-stats", b"native-effects") for actor in actors}
        )
        opcodes = [opcode for opcode, _ in packets]
        self.assertEqual(opcodes.count(12053), 1)
        self.assertIn(12514, opcodes)
        action_transitions = [
            index for index, opcode in enumerate(opcodes) if opcode == 12514
        ]
        self.assertEqual(len(action_transitions), 2)
        self.assertLess(opcodes.index(12514), opcodes.index(12053))
        self.assertLess(opcodes.index(12053), action_transitions[-1])
        self.assertNotIn(13337, opcodes)
        self.assertNotIn(13482, opcodes)
        recovery_body = next(body for opcode, body in packets if opcode == 12053)
        envelope_size = struct.unpack_from(">h", recovery_body, 4)[0]
        envelope = recovery_body[6 : 6 + envelope_size]
        state = envelope[9:]
        restored_round, restored_turn, _, _ = struct.unpack_from(">hiBq", state)
        self.assertEqual((restored_round, restored_turn), (1, 1))
        cursor = struct.calcsize(">hiBq")
        member_count = struct.unpack_from(">b", state, cursor)[0]
        cursor += 1
        restored_order = tuple(
            struct.unpack_from(">q", state, cursor + offset * 8)[0]
            for offset in range(member_count)
        )
        self.assertEqual(restored_order, server_order)
        self.assertEqual(fight.current.id, server_current)
        self.assertEqual(fight.turn_id, restored_turn)

        ended = runtime.end_turn(
            fight.current.owner_id, fight.current.id, fight.current.turn_count
        )
        self.assertNotIn(12053, [opcode for opcode, _ in ended])
        self.assertIn(13337, [opcode for opcode, _ in runtime.pending])
        self.assertIn(13482, [opcode for opcode, _ in runtime.pending])
        acknowledged = runtime.acknowledge_turn(struct.pack(">i", 1))
        self.assertNotIn(12053, [opcode for opcode, _ in acknowledged])
        self.assertEqual(fight.turn_id, 2)

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
        self.assertEqual([op for op, _ in packets], [12053, 12514, 13420])
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

    def test_registered_copy_stats_use_current_atomic_fight_on_turn_and_recovery(self):
        from dataclasses import asdict
        from unittest.mock import patch
        from wakfu_server.combat_runtime_adapter import NativeActorAuthority
        from wakfu_server.combat_summon_stats import registered_summon_stats

        fight, _ = self.state()
        actor = fight.current
        source = dict(
            ref=2382,
            level=200,
            caster_id=12,
            controller_id=12,
            native_relation_source="big.new_bje.fdt_initial_registration",
        )
        actor.native_summon_source = source
        actor.native_controller_id = 12
        actor.native_obstacle_id = 5
        actor.native_controlled_by_ai = False
        actor.native_fight_property_counts = {}
        authority = NativeActorAuthority(
            targeting={},
            is_player=False,
            deck_spell_ids=frozenset(),
            excluded_deck_spell_ids=frozenset(),
            is_carried=False,
            breed_id=2382,
            summon_count=0,
            summon_counts_by_breed={},
            occupant_blocks=True,
            is_summon=True,
            native_real_level=200,
            native_controller_id=12,
            native_actor_type=1,
        )
        fight.native_summon_registrations = {
            actor.id: dict(
                actor_id=actor.id,
                caster_id=12,
                controller_id=12,
                authority=asdict(authority),
            )
        }
        observed = []

        def serialize(current_actor, current_fight):
            self.assertIs(current_fight.actors[current_actor.id], current_actor)
            self.assertIsNot(current_fight, fight)
            observed.append(current_actor.id)
            return registered_summon_stats(current_actor, current_fight, 1134)

        def stale_unary(_actor):
            self.fail("Runtime must use the current-Fight serializer")

        runtime = RuntimeMessages(
            fight, stats_serializer=stale_unary, runtime_stats_serializer=serialize
        )
        with patch(
            "wakfu_server.combat_summon_stats.snapshot_characteristics",
            return_value=b"\x00\x00",
        ):
            turn = runtime.turn_started()
            recovery = runtime.recover(1, struct.pack(">i", fight.id), now_ms=0)
        self.assertIn(12873, [op for op, _ in turn])
        self.assertIn(12873, [op for op, _ in recovery])
        self.assertEqual(observed, [actor.id, actor.id])

    def test_start_and_end_use_ack_barrier_not_actor_turn_counter(self):
        fight, wire = self.state()
        packets = wire.combat_started(
            {100: (b"ownPC", b"\0\0"), -200: (b"ownNPC", b"\0\0")}
        )
        self.assertEqual(
            [op for op, b in packets],
            [
                13912,
                12873,
                13912,
                12873,
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
        self.assertEqual(decode_actor_state(13912, packets[0][1])["state"], b"\0\0")
        self.assertEqual(decode_actor_state(12873, packets[1][1])["state"], b"ownPC")
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
