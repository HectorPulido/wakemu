"""Actual position/QI/carry boundaries after spatial adapter retirement."""
from copy import deepcopy
import unittest

import test_combat_qi_fight
from wakfu_server.combat_carrying import carry_registered, carrying_relations
from wakfu_server.combat_qi_fight import current_registry, move_registered_actor


class PositionMutationTests(unittest.TestCase):
    def fixture(self, *, pointer=False, carried=False, arena=True):
        fixture = test_combat_qi_fight.NativeQIFightLifecycleTests()
        fight, actor, other = fixture.fixture(arena=arena, radii=(0, 0))
        if arena:
            fight.native_qi_snapshot["cell_masks"] = [0] * 16
        fixture.initialize(fight)
        actor.native_physical_position = actor.position
        other.native_physical_position = other.position
        actor.native_los_height = 0
        if pointer:
            from wakfu_server.combat_pointer_qi_actor import ActualActorQI
            from wakfu_server.combat_pointer_qi_checkpoint import (
                NativePointerCheckpoint,
            )

            fight.native_pointer_checkpoint = NativePointerCheckpoint(
                ActualActorQI(fight)
            )
        if carried:
            carry_registered(fight, actor, other, source_uid=1)
        return fight, actor.id, other.id

    def projection(self, fight):
        from wakfu_server.combat_reproduction_state import encode_state

        if fight.native_qi_slots is not None:
            current_registry(fight)
        return encode_state(deepcopy(fight))

    def relocate(self, fight, identity, destinations):
        resources = {
            key: (actor.hp, actor.ap, actor.mp) for key, actor in fight.actors.items()
        }
        for destination in destinations:
            move_registered_actor(fight, fight.actors[identity], destination)
            self.assertEqual(fight.actors[identity].position, tuple(destination))
            if fight.native_qi_slots is not None:
                current_registry(fight)
        self.assertEqual(
            {
                key: (actor.hp, actor.ap, actor.mp)
                for key, actor in fight.actors.items()
            },
            resources,
        )
        return fight

    def test_serialized_and_pointer_qi_match_for_ordered_relocations(self):
        for pointer in (False, True):
            with self.subTest(pointer=pointer):
                fight, actor, other = self.fixture(pointer=pointer)
                other_position = fight.actors[other].position
                self.relocate(fight, actor, [(1, 1, 2), (1, 1, -1), (2, 0, 0)])
                self.assertEqual(
                    fight.actors[actor].native_physical_position, (2, 0, 0)
                )
                self.assertEqual(fight.actors[other].position, other_position)

    def test_carried_recursion_matches_in_both_qi_representations(self):
        for pointer in (False, True):
            with self.subTest(pointer=pointer):
                fight, actor, carried = self.fixture(pointer=pointer, carried=True)
                self.relocate(fight, actor, [(1, 1, 2), (2, 0, -1)])
                self.assertEqual(fight.actors[actor].position, (2, 0, -1))
                self.assertEqual(fight.actors[carried].position, (2, 0, -1))
                self.assertTrue(
                    carrying_relations(fight, fight.actors[carried])["is_carried"]
                )
                if pointer:
                    checkpoint = fight.native_pointer_checkpoint
                    checkpoint.validate(fight)
                    self.assertIs(
                        checkpoint._qi.objects[actor].actor, fight.actors[actor]
                    )

    def test_no_qi_keeps_physical_and_permissive_fixture_coordinates(self):
        fight, actor, _ = self.fixture(arena=False)
        self.relocate(fight, actor, [(1, 2, 3), (4, 5)])
        self.assertIsNone(fight.native_qi_slots)
        self.assertEqual(fight.actors[actor].native_physical_position, (4, 5))

    def test_list_destinations_preserve_complete_graph_and_coordinate_aliases(self):
        for pointer in (False, True):
            fight, actor, _ = self.fixture(pointer=pointer)
            self.relocate(fight, actor, [[1, 1, 2], [2, 0, -1]])
            moved = fight.actors[actor]
            self.assertEqual(moved.position, moved.native_physical_position)
            self.assertIsNot(moved.position, moved.native_physical_position)

    def test_one_shot_destination_preserves_historical_consumption(self):
        for arena in (False, True):
            fight, actor, _ = self.fixture(arena=arena)
            move_registered_actor(fight, fight.actors[actor], iter((1, 1, 2)))
            self.assertEqual(fight.actors[actor].native_physical_position, ())
            self.assertEqual(fight.actors[actor].position, () if arena else (1, 1, 2))
            # Keep the actual historical iterable outcome, including invalid
            # post-publication QI coordinates; do not silently repair it.
            from wakfu_server.combat_reproduction_state import encode_state

            self.assertFalse(encode_state(fight)["services"])

    def test_rejected_carried_movement_leaves_actual_topology_unchanged(self):
        for pointer in (False, True):
            fight, _, carried = self.fixture(pointer=pointer, carried=True)
            before = self.projection(fight)
            with self.assertRaisesRegex(ValueError, "Independent carried"):
                move_registered_actor(fight, fight.actors[carried], (1, 1, 0))
            self.assertEqual(self.projection(fight), before)

    def test_stale_qi_error_precedes_invalid_destination(self):
        fight, actor, _ = self.fixture()
        fight.actors[actor].position = (1, 0, 0)
        with self.assertRaisesRegex(ValueError, "lifecycle update"):
            move_registered_actor(fight, fight.actors[actor], (False, 0, 0))

    def test_invalid_registered_destination_rejects_before_publication(self):
        fight, actor, _ = self.fixture()
        before = self.projection(fight)
        with self.assertRaises(ValueError):
            move_registered_actor(fight, fight.actors[actor], (False, 0, 0))
        self.assertEqual(self.projection(fight), before)

    def test_registered_carrier_updates_actual_partner_and_pointer_identity(self):
        fight, actor, carried = self.fixture(pointer=True, carried=True)
        move_registered_actor(fight, fight.actors[actor], (1, 1, 0))
        fight.native_pointer_checkpoint.validate(fight)
        self.assertEqual(fight.actors[actor].position, (1, 1, 0))
        self.assertEqual(fight.actors[carried].position, (1, 1, 0))
        self.assertIs(
            fight.native_pointer_checkpoint._qi.objects[carried].actor,
            fight.actors[carried],
        )
        self.assertEqual(fight.actors[carried].native_carrier_id, actor)
        self.assertTrue(carrying_relations(fight, fight.actors[carried])["is_carried"])
