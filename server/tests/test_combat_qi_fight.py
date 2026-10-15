import unittest
from unittest.mock import patch

from wakfu_server.combat_qi_fight import (
    current_registry,
    install_fresh_actor_slots,
    prepare_fresh_actor_slots,
    register_effect_area_obstacle,
)
from wakfu_server.combat_qi_snapshot import NativeQISnapshot
from wakfu_server.combat_state import Actor, Fight


class NativeQIFightLifecycleTests(unittest.TestCase):
    def fixture(self, *, arena=True, radii=(1, 0)):
        pc = Actor(7, 0, (0, 0, 0), 20, 6, 3, 10, 10, owner_id=1, controlled=True)
        npc = Actor(-7, 1, (3, 3, 0), 30, 0, 0, 1, 10)
        pc.physical_radius, npc.physical_radius = radii
        cells = {(x, y, 0) for x in range(4) for y in range(4)}
        fight = Fight(
            99,
            [pc, npc],
            cells,
            {0: {pc.position}, 1: {npc.position}},
        )
        if arena:
            fight.native_qi_snapshot = {
                "x": 0,
                "y": 0,
                "width": 4,
                "height": 4,
                "cell_masks": [0x100 | (i & 0x3F) for i in range(16)],
            }
        return fight, pc, npc

    def initialize(self, fight):
        prepared = prepare_fresh_actor_slots(
            fight,
            physical_radii={
                identity: actor.physical_radius
                for identity, actor in fight.actors.items()
            },
        )
        install_fresh_actor_slots(fight, prepared)

    def test_fresh_fight_without_serialized_arena_keeps_qi_unknown(self):
        fight, _, _ = self.fixture(arena=False)

        self.initialize(fight)

        self.assertIsNone(fight.native_qi_slots)
        self.assertIsNone(fight.native_qi_fresh_actor_order)
        with self.assertRaisesRegex(ValueError, "population"):
            current_registry(fight)

    def test_fresh_actor_slots_use_real_mask_copy_and_radius_footprints(self):
        fight, pc, npc = self.fixture()
        original_masks = list(fight.native_qi_snapshot["cell_masks"])

        self.initialize(fight)
        registry = current_registry(fight)
        occupancy = registry.snapshot()

        self.assertEqual(pc.native_obstacle_id, 0)
        self.assertEqual(npc.native_obstacle_id, 1)
        self.assertEqual(fight.native_qi_snapshot["cell_masks"], original_masks)
        self.assertEqual(occupancy.U(0, 0), frozenset({0}))
        self.assertEqual(occupancy.U(1, 1), frozenset({0}))
        self.assertEqual(occupancy.U(3, 3), frozenset({1}))
        self.assertTrue(registry.slots[0]["movement_blocking"])
        self.assertEqual(registry.slots[0]["radius"], 1)

    def test_invalid_radius_rejects_without_consuming_fresh_boundary(self):
        fight, pc, _ = self.fixture()
        pc.physical_radius = 128
        pending = fight.native_qi_fresh_actor_order

        radii = {
            identity: actor.physical_radius for identity, actor in fight.actors.items()
        }
        radii[pc.id] = 128
        with self.assertRaisesRegex(ValueError, "registration facts"):
            prepare_fresh_actor_slots(fight, physical_radii=radii)

        self.assertIsNone(fight.native_qi_slots)
        self.assertEqual(fight.native_qi_fresh_actor_order, pending)

    def test_preflight_rejects_missing_or_stale_actor_authority_without_uid(self):
        fight, pc, npc = self.fixture()
        self.initialize(fight)
        fight.native_effect_uid_next = 400
        # QK registration preflight consumes the typed native obstacle
        # constructor facts, not a movement flag in isolation.
        constructor = {"obstacle": True, "movement_blocking": True}

        self.assertIsNone(register_effect_area_obstacle(fight, None, constructor))
        self.assertEqual(fight.native_effect_uid_next, 400)

        original = pc.position
        pc.position = (1, 0, 0)
        with self.assertRaisesRegex(ValueError, "lifecycle update"):
            register_effect_area_obstacle(fight, None, constructor)
        pc.position = original

        npc.hp = 0
        with self.assertRaisesRegex(ValueError, "lifecycle update"):
            register_effect_area_obstacle(fight, None, constructor)
        self.assertEqual(fight.native_effect_uid_next, 400)

    def test_changed_roster_and_missing_population_reject_preflight(self):
        fight, pc, _ = self.fixture()
        self.initialize(fight)
        constructor = {"obstacle": True, "movement_blocking": True}

        del fight.actors[pc.id]
        with self.assertRaisesRegex(ValueError, "lifecycle update"):
            register_effect_area_obstacle(fight, None, constructor)
        fight.native_qi_slots = None
        with self.assertRaisesRegex(ValueError, "population"):
            register_effect_area_obstacle(fight, None, constructor)

    def test_fight_move_hook_updates_native_qi_position_and_occupancy(self):
        fight, pc, npc = self.fixture(radii=(0, 0))
        npc.position = (3, 0, 0)
        fight.walkable = {(x, 0, 0) for x in range(4)}
        fight.placement = {0: {pc.position}, 1: {npc.position}}
        fight.native_qi_snapshot = {
            "x": 0,
            "y": 0,
            "width": 4,
            "height": 1,
            "cell_masks": [0] * 4,
        }
        self.initialize(fight)
        fight.phase = "active"
        fight.order = [pc.id, npc.id]
        fight.turn_index = 0
        fight.turn_id = 1
        pc.turn_count = 1
        fight.move(1, pc.id, [(1, 0, 0)])

        self.assertEqual(pc.position, (1, 0, 0))
        occupancy = current_registry(fight).snapshot()
        self.assertEqual(occupancy.U(0, 0), frozenset())
        self.assertEqual(occupancy.U(1, 0), frozenset({pc.native_obstacle_id}))

    @patch(
        "wakfu_server.combat.combat_trove_byte_set.protocol_catalog.load",
        return_value={
            "initial_capacity": 23,
            "initial_compact_removes": 10,
            "load_factor": 0.5,
            "auto_compaction_factor": 0.5,
            "prime_capacities": [3, 5, 7, 11, 17, 23, 31],
        },
    )
    def test_ordinary_movement_respects_qi_radius_and_temporary_exclusions(
        self, _contract
    ):
        fight, pc, npc = self.fixture(radii=(0, 1))
        # Put the blocker on the far edge so (1,0) is walkable and its exact
        # actor coordinate differs from the QI radius footprint.
        npc.position = (1, 1, 0)
        fight.walkable = {(x, y, 0) for x in range(4) for y in range(4)}
        fight.edges = {
            (source, target)
            for source in fight.walkable
            for target in fight.walkable
            if abs(source[0] - target[0]) + abs(source[1] - target[1]) == 1
        }
        fight.placement = {0: {pc.position}, 1: {npc.position}}
        fight.native_qi_snapshot = {
            "x": 0,
            "y": 0,
            "width": 4,
            "height": 4,
            "cell_masks": [0] * 16,
        }
        self.initialize(fight)
        fight.phase = "active"
        fight.order = [pc.id, npc.id]
        fight.turn_index = 0
        fight.turn_id = 1
        pc.turn_count = 1

        from wakfu_server.combat.combat_tactical_ai import _distances

        self.assertNotIn((1, 0, 0), _distances(fight, pc.position, pc.id))
        with self.assertRaisesRegex(ValueError, "Invalid combat movement path"):
            fight.move(1, pc.id, [(1, 0, 0)])
        self.assertEqual(pc.position, (0, 0, 0))
        self.assertEqual(pc.mp, 3)

        fight.native_qi_movement_override = True
        fight.native_qi_snapshot["cell_masks"][1] = 768
        self.assertNotIn((1, 0, 0), _distances(fight, pc.position, pc.id))
        with self.assertRaisesRegex(ValueError, "Invalid combat movement path"):
            fight.move(1, pc.id, [(1, 0, 0)])
        fight.native_qi_snapshot["cell_masks"][1] = 0

        # biN can make an occupied actor cell passable. When owned QI exists,
        # movement must not reapply the legacy HP/exact-coordinate heuristic.
        exact, mover, blocker = self.fixture(arena=False, radii=(0, 0))
        mover.position = (0, 1, 0)
        blocker.position = (1, 1, 0)
        exact.walkable = {(0, 1, 0), (1, 1, 0), (2, 1, 0)}
        exact.edges = {
            ((0, 1, 0), (1, 1, 0)),
            ((1, 1, 0), (0, 1, 0)),
            ((1, 1, 0), (2, 1, 0)),
            ((2, 1, 0), (1, 1, 0)),
        }
        exact.placement = {0: {mover.position}, 1: {blocker.position}}
        exact.native_qi_snapshot = {
            "x": 0,
            "y": 1,
            "width": 3,
            "height": 1,
            "cell_masks": [0] * 3,
        }
        self.initialize(exact)
        exact.phase = "active"
        exact.order = [mover.id, blocker.id]
        exact.turn_index = 0
        exact.turn_id = 1
        mover.turn_count = 1
        exact.native_qi_ignored_slots = [blocker.native_obstacle_id]
        exact.move(1, mover.id, [(1, 1, 0)])
        self.assertEqual(mover.position, blocker.position)

        fight.native_qi_movement_override = False
        fight.native_qi_ignored_slots = [npc.native_obstacle_id]
        self.assertIn((1, 0, 0), _distances(fight, pc.position, pc.id))
        fight.move(1, pc.id, [(1, 0, 0)])
        self.assertEqual(pc.position, (1, 0, 0))

    def test_current_registry_rejects_dead_or_unregistered_actor(self):
        fight, pc, npc = self.fixture()
        self.initialize(fight)

        pc.hp = 0
        with self.assertRaisesRegex(ValueError, "lifecycle update"):
            current_registry(fight)
        pc.hp = 20
        del fight.actors[npc.id]
        with self.assertRaisesRegex(ValueError, "lifecycle update"):
            current_registry(fight)


if __name__ == "__main__":
    unittest.main()
