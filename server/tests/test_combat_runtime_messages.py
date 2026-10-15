from copy import deepcopy
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

    @staticmethod
    def _initial_restore_with_innate_summon(
        enemy_initiative, *, summon_controlled=True
    ):
        main = Actor(100, 0, (0, 0, 0), 60, 6, 3, 1000, 1, 1, True)
        hero = Actor(200, 0, (1, 0, 0), 60, 6, 3, 900, 1, 1, True)
        enemy = Actor(-200, 1, (3, 0, 0), 20, 4, 2, enemy_initiative, 1)
        actors = [main, hero, enemy]
        fight = Fight(
            89,
            actors,
            {actor.position for actor in actors},
            {
                0: {actor.position for actor in actors if actor.team == 0},
                1: {enemy.position},
            },
        )
        fight.ready(1)
        summon = Actor(
            300,
            0,
            (2, 0, 0),
            30,
            4,
            2,
            max(actor.initiative for actor in actors) + 100,
            1,
            1,
            summon_controlled,
        )
        summon.native_summon_source = {"ref": 2382, "caster_id": main.id}
        from wakfu_server.combat_summon import (
            SummonSpecification,
            fresh_summon_insertion,
        )

        specification = SummonSpecification(
            2382, 200, summon_controlled, 0, 0, "caster", 0
        )
        current_id_before_insertion = fight.current.id
        current_index_before_insertion = fight.turn_index
        new_order, new_turn_index = fresh_summon_insertion(
            fight, specification, caster_id=main.id, actor_id=summon.id
        )
        fight.actors[summon.id] = summon
        fight.order, fight.turn_index = new_order, new_turn_index
        RuntimeMessageTests._assert_current_survives_faster_summon_insertion(
            fight,
            summon,
            current_id_before_insertion,
            current_index_before_insertion,
        )
        from wakfu_server.combat_timeline_snapshot import insert

        insert(fight, summon.id, new_order.index(summon.id))

        from wakfu_server.combat_summon_codec import summon_application

        creation = summon_application(
            89,
            1,
            uid=901,
            base_uid=901,
            effect_reference=96363,
            caster_id=main.id,
            cell=summon.position,
            specification=specification,
            actor_id=summon.id,
            obstacle_index=5,
            properties=(),
            timing_payload=b"",
            container_type=1,
            container_id=3799,
        )
        fight.native_summon_creation_deliveries = {
            summon.id: {"opcode": creation[0], "payload_hex": creation[1].hex()}
        }
        fight.native_summon_registrations = {
            summon.id: {"actor_id": summon.id, "fight_properties": frozenset()}
        }
        runtime = RuntimeMessages(
            fight,
            clock=lambda: 0.0,
            turn_start_provider=lambda candidate, **_: (
                deepcopy(candidate),
                [(13827, b"turn-start callback")],
            ),
        )
        baseline = {
            main.id: (b"main stats", b"main effects"),
            hero.id: (b"hero stats", b"hero effects"),
            enemy.id: (b"enemy stats", b"enemy effects"),
        }

        packets = runtime.combat_started(baseline, initialization_packets=[creation])
        return fight, summon, packets

    @staticmethod
    def _assert_current_survives_faster_summon_insertion(
        fight, summon, current_id, previous_index
    ):
        if summon.initiative <= fight.actors[current_id].initiative:
            raise AssertionError("Regression fixture requires a faster newborn")
        if fight.current.id != current_id:
            raise AssertionError("Fresh summon insertion displaced the current actor")
        insertion_index = fight.order.index(summon.id)
        expected_index = previous_index + (insertion_index <= previous_index)
        if fight.turn_index != expected_index:
            raise AssertionError("Fresh summon insertion changed the current slot")

    def test_same_account_baseline_pcs_restore_timeline_with_innate_summon(self):
        for enemy_initiative, current_is_controlled in ((100, True), (1200, False)):
            for summon_controlled in (True, False):
                with self.subTest(
                    current_is_controlled=current_is_controlled,
                    summon_controlled=summon_controlled,
                ):
                    fight, summon, packets = self._initial_restore_with_innate_summon(
                        enemy_initiative,
                        summon_controlled=summon_controlled,
                    )
                    self.assertEqual(fight.current.controlled, current_is_controlled)

                    opcodes = [opcode for opcode, _ in packets]
                    self.assertEqual(opcodes.count(12053), 1)
                    self.assertEqual(opcodes.count(12613), 1)
                    self.assertLess(opcodes.index(12053), opcodes.index(12613))
                    self.assertLess(opcodes.index(12613), opcodes.index(13827))
                    action_indices = [
                        index for index, opcode in enumerate(opcodes) if opcode == 12514
                    ]
                    self.assertEqual(len(action_indices), 2)
                    self.assertLess(action_indices[0], opcodes.index(12053))
                    self.assertLess(opcodes.index(13827), action_indices[1])
                    self.assertNotIn(13477, opcodes)
                    recovery_body = next(
                        body for opcode, body in packets if opcode == 12053
                    )
                    envelope_size = struct.unpack_from(">h", recovery_body, 4)[0]
                    envelope = recovery_body[6 : 6 + envelope_size]
                    state = envelope[9:]
                    self.assertEqual(struct.unpack_from(">h", state, 0)[0], 1)
                    cursor = struct.calcsize(">hiBq")
                    member_count = struct.unpack_from(">b", state, cursor)[0]
                    cursor += 1
                    restored_order = tuple(
                        struct.unpack_from(">q", state, cursor + offset * 8)[0]
                        for offset in range(member_count)
                    )
                    expected_baseline = tuple(
                        identity for identity in fight.order if identity != summon.id
                    )
                    self.assertEqual(restored_order, expected_baseline)
                    self.assertNotIn(summon.id, restored_order)
                    self.assertIn(fight.current.id, restored_order)
                    self.assertEqual(len(restored_order), len(set(restored_order)))
                    cursor += member_count * 8
                    next_member_count = struct.unpack_from(">b", state, cursor)[0]
                    cursor += 1
                    next_order = tuple(
                        struct.unpack_from(">q", state, cursor + offset * 8)[0]
                        for offset in range(next_member_count)
                    )
                    self.assertEqual(next_order, expected_baseline)
                    self.assertNotIn(summon.id, next_order)
                    self.assertEqual(len(next_order), len(set(next_order)))
                    cursor += next_member_count * 8
                    progress_count = struct.unpack_from(">b", state, cursor)[0]
                    progress_rows = tuple(
                        struct.unpack_from(">qh", state, cursor + 1 + offset * 10)
                        for offset in range(progress_count)
                    )
                    progress = dict(progress_rows)
                    expected_progress = {
                        int(identity): value
                        for identity, value in fight.native_timeline_member_counters.items()
                        if int(identity) != summon.id
                    }
                    self.assertEqual(progress, expected_progress)
                    self.assertEqual(len(progress_rows), len(progress))
                    self.assertNotIn(summon.id, progress)
                    self.assertEqual(set(progress), set(restored_order))
                    cursor += 1 + progress_count * struct.calcsize(">qh")
                    self.assertEqual(
                        state[cursor], restored_order.index(fight.current.id)
                    )
                    cursor += 1
                    removed_count = struct.unpack_from(">b", state, cursor)[0]
                    cursor += 1 + removed_count * struct.calcsize(">qhih")
                    actor_count = struct.unpack_from(">b", state, cursor)[0]
                    cursor += 1
                    recovered_actor_ids = tuple(
                        struct.unpack_from(">q", state, cursor + offset * 12)[0]
                        for offset in range(actor_count)
                    )
                    expected_roster_ids = tuple(
                        actor.id
                        for actor in fight.actors.values()
                        if actor.id != summon.id
                    )
                    self.assertEqual(recovered_actor_ids, expected_roster_ids)
                    self.assertEqual(
                        len(recovered_actor_ids), len(set(recovered_actor_ids))
                    )

    def test_initial_recovery_exclusion_requires_exact_registered_birth(self):
        from copy import deepcopy
        from wakfu_server.combat_recovery import timeline

        fight, summon, _ = self._initial_restore_with_innate_summon(1200)
        fight.native_summon_registrations[summon.id]["actor_id"] = summon.id + 1
        with self.assertRaisesRegex(ValueError, "Unverified initial summon"):
            timeline(fight, deadline_ms=1, excluded_actor_ids=(summon.id,))

        current_summon = deepcopy(fight)
        current_summon.native_summon_registrations[summon.id]["actor_id"] = summon.id
        current_summon.turn_index = current_summon.order.index(summon.id)
        with self.assertRaisesRegex(ValueError, "Unverified initial summon"):
            timeline(
                current_summon,
                deadline_ms=1,
                excluded_actor_ids=(summon.id,),
            )

    def test_initial_recovery_projection_keeps_pb114_out_of_timeline_and_roster(self):
        from wakfu_server.combat_recovery import timeline

        fight, summon, _ = self._initial_restore_with_innate_summon(1200)
        slot = fight.order.index(summon.id)
        fight.order.pop(slot)
        if slot < fight.turn_index:
            fight.turn_index -= 1
        fight.native_timeline_member_counters.pop(str(summon.id))
        fight.native_summon_registrations[summon.id]["fight_properties"] = (114,)

        state = timeline(fight, deadline_ms=1, excluded_actor_ids=(summon.id,))
        order_count = struct.unpack_from(">b", state, 15)[0]
        order = struct.unpack_from(">" + "q" * order_count, state, 16)
        self.assertNotIn(summon.id, order)
        cursor = 16 + order_count * 8
        next_order_count = struct.unpack_from(">b", state, cursor)[0]
        cursor += 1 + next_order_count * 8
        progress_count = struct.unpack_from(">b", state, cursor)[0]
        cursor += 1 + progress_count * struct.calcsize(">qh") + 1
        removed_count = struct.unpack_from(">b", state, cursor)[0]
        cursor += 1 + removed_count * struct.calcsize(">qhih")
        actor_count = struct.unpack_from(">b", state, cursor)[0]
        cursor += 1
        actor_ids = tuple(
            struct.unpack_from(">q", state, cursor + offset * 12)[0]
            for offset in range(actor_count)
        )
        self.assertNotIn(summon.id, actor_ids)

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

    def test_turn_end_accepts_only_registered_summon_with_exact_creation_delivery(self):
        creation = (89, b"native summon creation")

        def provider_for(
            *, registration=True, delivery=True, event=True, payload_hex=None
        ):
            def provider(source, **_):
                candidate = deepcopy(source)
                candidate.phase = "finished"
                summon = Actor(300, 0, (2, 0, 0), 30, 4, 2, 20, 1, 1, True)
                candidate.actors[summon.id] = summon
                if registration:
                    candidate.native_summon_registrations = {
                        summon.id: {"actor_id": summon.id}
                    }
                if delivery:
                    candidate.native_summon_creation_deliveries = {
                        summon.id: {
                            "opcode": creation[0],
                            "payload_hex": (
                                creation[1].hex()
                                if payload_hex is None
                                else payload_hex
                            ),
                        }
                    }
                return candidate, [creation] if event else []

            return provider

        fight, _ = self.state()
        wire = RuntimeMessages(fight, turn_end_provider=provider_for())
        packets = wire._end_owned(fight.current)
        self.assertEqual(packets[0], creation)
        self.assertEqual(sum(packet == creation for packet in packets), 1)
        self.assertIn(300, fight.actors)

        invalid = (
            ("unregistered", provider_for(registration=False)),
            ("missing delivery", provider_for(delivery=False)),
            ("malformed delivery", provider_for(payload_hex="not-hex")),
            ("unpublished packet", provider_for(event=False)),
        )
        for label, provider in invalid:
            with self.subTest(label=label):
                fight, _ = self.state()
                wire = RuntimeMessages(fight, turn_end_provider=provider)
                with self.assertRaisesRegex(ValueError, "turn-end actor creation"):
                    wire._end_owned(fight.current)
                self.assertNotIn(300, fight.actors)

        fight, _ = self.state()

        def removing_provider(source, **_):
            candidate = deepcopy(source)
            candidate.phase = "finished"
            candidate.actors.pop(-200)
            return candidate, []

        wire = RuntimeMessages(fight, turn_end_provider=removing_provider)
        with self.assertRaisesRegex(ValueError, "removed an actor"):
            wire._end_owned(fight.current)
        self.assertIn(-200, fight.actors)

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
