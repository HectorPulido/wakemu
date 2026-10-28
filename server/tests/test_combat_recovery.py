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
        # Keep this exact recovery assertion pinned to its explicit 31s
        # deadline instead of coupling it to the product default.
        return f, RuntimeMessages(f, turn_duration_ms=30000)

    def test_death_recovery_preserves_live_turn_and_exact_ack(self):
        f, r = self.state()
        f.apply_damage(5, -200, 12)
        r.end_turn(9, 5, f.current.turn_count)
        packets = r.recover(9, struct.pack(">i", f.id), now_ms=1000)
        opcodes = [x[0] for x in packets]
        self.assertEqual(opcodes.count(12053), 1)
        self.assertEqual(opcodes.count(13482), 1)
        self.assertEqual(opcodes.count(13337), 1)
        self.assertNotIn(12514, opcodes)
        self.assertLess(opcodes.index(12053), opcodes.index(13482))
        self.assertEqual(opcodes[-2:], [13482, 13420])
        self.assertIsNone(r.awaiting_ack)
        self.assertEqual(r.pending, [])
        raw = next(body for opcode, body in packets if opcode == 12053)
        self.assertEqual(struct.unpack_from(">ih", raw), (f.id, len(raw) - 6))
        self.assertEqual(raw[6:13], struct.pack(">BBiB", 1, 0, 6, 0))
        state = timeline(f, deadline_ms=31000, new_turn=True)
        self.assertEqual(raw[15:], state)
        self.assertEqual(
            struct.unpack_from(">hiBq", state),
            (f.current.turn_count, f.turn_id - 1, 2, 31000),
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

    def test_restored_new_turn_prepares_each_cursor_without_advancing_gameplay(self):
        f, _ = self.state()

        def cursor(state):
            offset = 15
            for _ in range(2):
                count = state[offset]
                offset += 1 + count * 8
            count = state[offset]
            offset += 1 + count * 10
            return struct.unpack_from(">b", state, offset)[0]

        for index, identity in enumerate(f.order):
            with self.subTest(index=index, identity=identity):
                f.turn_index = index
                before = (f.turn_id, dict(f.native_timeline_member_counters))
                starting = timeline(f, deadline_ms=123_456, new_turn=True)
                ongoing = timeline(f, deadline_ms=123_456)
                self.assertEqual(cursor(starting), index - 1)
                self.assertEqual(cursor(ongoing), index)
                self.assertEqual(
                    struct.unpack_from(">hiBq", starting),
                    (f.native_timeline_round, f.turn_id - 1, 2, 123_456),
                )
                self.assertEqual(
                    struct.unpack_from(">hiBq", ongoing),
                    (f.native_timeline_round, f.turn_id, 1, 123_456),
                )
                self.assertEqual(f.current.id, identity)
                self.assertEqual(before, (f.turn_id, f.native_timeline_member_counters))

    def test_shared_withdrawal_is_not_fabricated_as_a_native_death(self):
        from wakfu_server.combat_pve_withdraw import plan
        from wakfu_server.combat_shared import Session

        actors = [
            Actor(5, 0, (0, 0, 0), 60, 6, 3, 100, 1, 9, True),
            Actor(6, 0, (1, 0, 0), 60, 6, 3, 90, 1, 10, True),
            Actor(-200, 1, (2, 0, 0), 30, 4, 2, 10, 1),
        ]
        fight = Fight(
            77,
            actors,
            {(x, 0, 0) for x in range(3)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(2, 0, 0)}},
        )
        fight.ready(9)
        fight.ready(10)
        runtime = RuntimeMessages(fight)

        transition = plan(Session(9, 5, "owner", 527, 0), fight, runtime)

        withdrawn = transition.fight.actors[5]
        self.assertTrue(withdrawn.pve_withdrawn)
        self.assertEqual(withdrawn.hp, 0)
        self.assertTrue(
            any(
                event.get("kind") == "withdrawn" and event.get("actor_id") == 5
                for event in transition.fight.events
            )
        )
        self.assertFalse(
            any(
                event.get("kind") == "death" and event.get("actor_id") == 5
                for event in transition.fight.events
            )
        )
        # Recovery reconstructs the live order without requiring a death row
        # that the authoritative event history never contained.
        self.assertTrue(timeline(transition.fight, deadline_ms=31_000))

    def test_beacon_roster_is_separate_from_current_and_next_timeline(self):
        from dataclasses import replace

        f, _ = self.state()
        beacon = replace(f.actors[5], id=114, controlled=False, owner_id=None)
        f.actors[114] = beacon
        f.native_summon_registrations = {114: dict(fight_properties=(114,))}
        f.native_base_turn_order = list(f.order)
        f.order.insert(f.turn_index + 1, f.current.id)
        raw = timeline(f, deadline_ms=1)
        self.assertEqual(struct.unpack_from(">h", raw)[0], f.native_timeline_round)
        first_count = raw[15]
        self.assertEqual(first_count, len(f.order))
        second_offset = 16 + first_count * 8
        self.assertEqual(raw[second_offset], len(f.native_base_turn_order))
        self.assertNotIn("114", f.native_timeline_member_counters)

    def test_inserted_actor_progress_survives_json_checkpoint_and_exact_removal(self):
        import json
        from dataclasses import replace
        from wakfu_server.combat_timeline_snapshot import insert

        f, _ = self.state()
        identity = 123
        slot = f.turn_index
        insert(f, identity, slot)
        self.assertEqual(
            f.native_timeline_member_counters[str(identity)],
            f.native_timeline_round + 1,
        )
        actor = replace(f.actors[-200], id=identity, hp=12)
        f.actors[identity] = actor
        f.order.insert(slot, identity)
        f.turn_index += 1
        f.native_timeline_member_counters = json.loads(
            json.dumps(f.native_timeline_member_counters)
        )
        self.assertTrue(timeline(f, deadline_ms=1))
        f.apply_effect_damage(f.current.id, identity, 12)
        row = f.native_timeline_removed[-1]
        self.assertEqual(
            (row["actor_id"], row["position"], row["progress"]),
            (identity, slot, f.native_timeline_round + 1),
        )
        self.assertNotIn(str(identity), f.native_timeline_member_counters)
        self.assertTrue(timeline(f, deadline_ms=1))

    def test_missing_progress_cannot_be_reconstructed_from_roster(self):
        f, _ = self.state()
        del f.native_timeline_snapshot_source
        with self.assertRaisesRegex(ValueError, "progress snapshot"):
            timeline(f, deadline_ms=1)

    def test_beacon_multi_kill_then_endturn_ack_restores_live_client_timeline_once(
        self,
    ):
        actors = [
            Actor(5, 0, (0, 0, 0), 60, 6, 3, 100, 1, 9, True),
            Actor(6, 0, (1, 0, 0), 60, 6, 3, 90, 1, 10, True),
            Actor(-200, 1, (2, 0, 0), 12, 6, 3, 50, 1),
            Actor(-201, 1, (3, 0, 0), 12, 6, 3, 40, 1),
            Actor(-202, 1, (4, 0, 0), 12, 6, 3, 30, 1),
        ]
        fight = Fight(
            80,
            actors,
            {(x, 0, 0) for x in range(6)},
            {
                0: {actors[0].position, actors[1].position},
                1: {actor.position for actor in actors[2:]},
            },
        )
        fight.ready(9)
        fight.ready(10)
        self.assertEqual(fight.current.id, 5)

        # A native beacon remains in the fighter roster but never enters Tc/SY.
        beacon = Actor(114, 1, (5, 0, 0), 30, 0, 0, 0, 1)
        fight.actors[114] = beacon
        fight.native_summon_registrations = {114: dict(fight_properties=(114,))}
        clock = [1.0]
        runtime = RuntimeMessages(fight, clock=lambda: clock[0])
        runtime.turn_started(arm_deadline=False)

        # The off-timeline beacon kills two NPCs in one settled native chain.
        with fight.effect_resolution():
            fight.apply_effect_damage(114, -200, 12)
            fight.apply_effect_damage(114, -201, 12)
        self.assertEqual(beacon.hp, 30)
        self.assertEqual(fight.current.id, 5)
        self.assertEqual(fight.order, [5, 6, -202])
        self.assertEqual(
            [row["actor_id"] for row in fight.native_timeline_removed],
            [-200, -201],
        )

        previous_turn = fight.turn_id
        end_packets = runtime.end_turn(9, 5, fight.actors[5].turn_count)
        self.assertEqual([opcode for opcode, _ in end_packets], [12502, 13420])
        self.assertEqual(runtime.awaiting_ack, previous_turn)
        pending_opcodes = [opcode for opcode, _ in runtime.pending]
        self.assertEqual(pending_opcodes, [12053, 13420, 13337, 13420, 13482, 13420])
        self.assertEqual(pending_opcodes.count(13337), 1)
        self.assertEqual(pending_opcodes.count(13482), 1)

        with self.assertRaisesRegex(ValueError, "Invalid or stale turn"):
            runtime.acknowledge_turn(struct.pack(">i", previous_turn - 1))
        clock[0] = 2.0
        acknowledged = runtime.acknowledge_turn(struct.pack(">i", previous_turn))
        self.assertEqual(
            [opcode for opcode, _ in acknowledged],
            [12053, 13420, 13337, 13420, 13482, 13420],
        )
        self.assertEqual(runtime.awaiting_ack, None)
        self.assertEqual(fight.current.id, 6)

        # The authoritative recovery and the client consumer agree on current
        # and next order, while the living beacon is roster-only.
        raw = acknowledged[0][1]
        state = raw[15:]
        first_count = state[15]
        current_order = list(
            struct.unpack_from(">" + str(first_count) + "q", state, 16)
        )
        next_offset = 16 + first_count * 8
        next_count = state[next_offset]
        next_order = list(
            struct.unpack_from(">" + str(next_count) + "q", state, next_offset + 1)
        )
        self.assertEqual(current_order, [5, 6, -202])
        self.assertEqual(next_order, current_order)
        self.assertNotIn(114, current_order)
        self.assertNotIn("114", fight.native_timeline_member_counters)
        self.assertEqual(runtime.native_timeline_removal_delivery_count, 2)

        # Once the removal snapshot has been delivered and ACKed, the next
        # living actor follows the ordinary timeline path without a duplicate.
        normal_end = runtime.end_turn(10, 6, fight.actors[6].turn_count)
        self.assertEqual([opcode for opcode, _ in normal_end], [12502, 13420])
        self.assertEqual(
            [opcode for opcode, _ in runtime.pending], [13337, 13420, 13482, 13420]
        )
        self.assertNotIn(12053, [opcode for opcode, _ in runtime.pending])
        normal_ack = runtime.acknowledge_turn(struct.pack(">i", fight.turn_id - 1))
        self.assertEqual(
            [opcode for opcode, _ in normal_ack], [13337, 13420, 13482, 13420]
        )
        self.assertEqual(fight.current.id, -202)
