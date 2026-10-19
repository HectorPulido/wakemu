"""A real end callback may settle its current actor before turn synchronization."""
from copy import deepcopy
import struct
import unittest

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_timeline_snapshot import current_wire_turn


class PreEndDeathTests(unittest.TestCase):
    def test_direct_server_turn_fallback_finalizes_reaction_death_before_ack(self):
        from wakfu_server.combat_death import newly_registered_death_messages

        fight = self.fixture(controlled=False)
        before_turn = fight.turn_id
        from wakfu_server.combat_native_death_status import (
            initialize_fresh_bje_death_status,
        )

        fight.actors[-200].native_world_properties = frozenset()
        initialize_fresh_bje_death_status(fight.actors[-200])

        def poison(candidate, *, actor_id, action_id):
            candidate = deepcopy(candidate)
            candidate.apply_effect_damage(101, -200, candidate.actors[-200].hp)
            return candidate, []

        runtime = RuntimeMessages(fight, turn_end_provider=poison)
        # This is the direct runtime path used after the AI deadline expires;
        # there is deliberately no oracle to add death presentation packets.
        packets = runtime.end_server_turn(100, before_turn)
        deaths = [
            struct.unpack(">iiiqB", body)[3:] for op, body in packets if op == 12727
        ]
        self.assertEqual(deaths, [(-200, 0), (-200, 2)])
        close_index = next(
            index for index, (op, _) in enumerate(packets) if op == 12502
        )
        self.assertTrue(
            all(
                index < close_index
                for index, (op, _) in enumerate(packets)
                if op == 12727
            )
        )
        self.assertEqual(fight.actors[-200].hp, 0)
        self.assertTrue(fight.actors[-200].native_death_status["mwD"])
        self.assertEqual(runtime.awaiting_ack, before_turn)
        self.assertTrue(runtime.pending)
        self.assertEqual(newly_registered_death_messages(runtime, after_sequence=0), [])
        after_ack = runtime.acknowledge_turn(struct.pack(">i", before_turn))
        self.assertFalse(any(op == 12727 for op, _ in after_ack))
        native_ids = [
            struct.unpack_from(">i", body, 4)[0]
            for op, body in packets
            if op in (12502, 12727)
        ]
        self.assertEqual(native_ids, sorted(set(native_ids)))
        self.assertIsNone(runtime.awaiting_ack)

    def test_reaction_death_allocation_failure_preserves_authoritative_state(self):
        from wakfu_server.combat_native_action_ids import MAX_NATIVE_ACTION_ID

        fight = self.fixture(controlled=False)
        before_turn = fight.turn_id

        def poison(candidate, *, actor_id, action_id):
            candidate = deepcopy(candidate)
            candidate.apply_effect_damage(101, -200, candidate.actors[-200].hp)
            return candidate, []

        runtime = RuntimeMessages(fight, turn_end_provider=poison)
        runtime.native_action_id = MAX_NATIVE_ACTION_ID - 1
        with self.assertRaises(ValueError):
            runtime.end_server_turn(100, before_turn)
        self.assertEqual(fight.actors[-200].hp, 60)
        self.assertEqual(fight.turn_id, before_turn)
        self.assertIsNone(runtime.awaiting_ack)
        self.assertEqual(runtime.pending, [])
        self.assertEqual(runtime.native_action_id, MAX_NATIVE_ACTION_ID - 1)
        self.assertFalse(getattr(runtime, "_reported_deaths", set()))

    def test_prepared_turn_close_rejects_new_death_insertion_without_committing_ids(
        self,
    ):
        from wakfu_server.combat_native_action_ids import native_delivery_boundary

        fight = self.fixture(controlled=False)
        runtime = RuntimeMessages(fight)

        @native_delivery_boundary
        def already_prepared(candidate):
            candidate.fight.apply_effect_damage(101, -200, 60)
            return candidate.prepare_delivery(
                [
                    (12502, candidate._prefix() + struct.pack(">qii", 100, -1, 0)),
                    candidate._flush(),
                ]
            )

        with self.assertRaisesRegex(ValueError, "Prepared turn transition"):
            already_prepared(runtime)
        self.assertEqual(fight.actors[-200].hp, 60)
        self.assertEqual(runtime.native_action_id, 0)
        self.assertEqual(runtime.action_id, 0)
        self.assertFalse(getattr(runtime, "_reported_deaths", set()))
        self.assertIsNone(runtime.awaiting_ack)
        self.assertEqual(runtime.pending, [])
        fresh = runtime.prepare_delivery(
            [(12502, runtime._prefix() + struct.pack(">qii", 100, -1, 0))]
        )
        self.assertEqual(fresh.native_actions[0]["native_action_id"], 1)

    def fixture(self, controlled=True):
        actors = [
            Actor(
                100,
                0 if controlled else 1,
                (0, 0, 0),
                60,
                6,
                3,
                1000,
                1,
                1 if controlled else None,
                controlled,
            ),
            Actor(101, 0, (1, 0, 0), 60, 6, 3, 900, 1, 1, True),
            Actor(-200, 1, (2, 0, 0), 60, 6, 3, 10, 1),
        ]
        cells = {a.position for a in actors}
        fight = Fight(
            7,
            actors,
            cells,
            {
                team: {actor.position for actor in actors if actor.team == team}
                for team in (0, 1)
            },
        )
        fight.ready(1)
        if not controlled:
            current = fight.current
            fight.end_turn(current.owner_id, current.id, current.turn_count)
        self.assertEqual(fight.current.id, 100)
        return fight

    def test_owned_and_server_end_death_advance_once_and_wait_for_real_ack(self):
        for controlled in (True, False):
            with self.subTest(controlled=controlled):
                fight = self.fixture(controlled)
                before_turn = fight.turn_id
                successor = fight.order[(fight.turn_index + 1) % len(fight.order)]
                calls = []

                def end(candidate, *, actor_id, action_id):
                    calls.append(actor_id)
                    candidate = deepcopy(candidate)
                    actor = candidate.actors[actor_id]
                    candidate.apply_effect_damage(101, actor_id, actor.hp)
                    return candidate, [(13420, struct.pack(">i", candidate.id))]

                runtime = RuntimeMessages(
                    fight, clock=lambda: 0.0, turn_end_provider=end
                )
                packets = (
                    runtime.end_turn(1, 100, current_wire_turn(fight))
                    if controlled
                    else runtime.end_server_turn(100, before_turn)
                )
                self.assertEqual(calls, [100])
                self.assertEqual(fight.turn_id, before_turn + 1)
                self.assertEqual(fight.current.id, successor)
                self.assertEqual(fight.actors[100].hp, 0)
                self.assertEqual([op for op, _ in packets].count(12502), 1)
                self.assertEqual(runtime.awaiting_ack, before_turn)
                self.assertIsNone(runtime.turn_deadline)
                self.assertTrue(runtime.pending)
                runtime.acknowledge_turn(struct.pack(">i", before_turn))
                self.assertEqual(fight.turn_id, before_turn + 1)
                self.assertIsNone(runtime.awaiting_ack)
                self.assertFalse(runtime.pending)
                with self.assertRaises(ValueError):
                    runtime.acknowledge_turn(struct.pack(">i", before_turn))

    def test_alive_or_multiple_transition_callback_rejected_atomically(self):
        for advances in (1, 2):
            with self.subTest(advances=advances):
                fight = self.fixture()
                old_order, old_turn = list(fight.order), fight.turn_id

                def end(candidate, *, actor_id, action_id):
                    candidate = deepcopy(candidate)
                    if advances == 2:
                        candidate.apply_effect_damage(
                            101, actor_id, candidate.actors[actor_id].hp
                        )
                        current = candidate.current
                        if current.controlled:
                            candidate.end_turn(
                                current.owner_id, current.id, current.turn_count
                            )
                        else:
                            candidate.end_server_turn(current.id, candidate.turn_id)
                    else:
                        candidate.end_turn(
                            1, actor_id, candidate.actors[actor_id].turn_count
                        )
                    return candidate, []

                runtime = RuntimeMessages(fight, turn_end_provider=end)
                with self.assertRaisesRegex(ValueError, "Unsupported turn transition"):
                    runtime.end_turn(1, 100, current_wire_turn(fight))
                self.assertEqual(fight.order, old_order)
                self.assertEqual(fight.turn_id, old_turn)
                self.assertEqual(fight.actors[100].hp, 60)
                self.assertIsNone(runtime.awaiting_ack)
                self.assertEqual(runtime.pending, [])
