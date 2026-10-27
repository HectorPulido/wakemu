"""Current canonical QK queries agree with complete legacy projections."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class QueryLocalQIProjectionTests(unittest.TestCase):
    def test_movement_los_fresh_footprints_null_flags_and_stale_authority(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_pointer_qi_actor import ActualActorQI
        from wakfu_server.combat_pointer_qi_checkpoint import NativePointerCheckpoint
        from wakfu_server.combat_pointer_qi_registry import (
            registered_obstacle,
            registered_slot,
        )
        from wakfu_server.combat_qi_registry import NativeQIRegistry
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.combat_qi_movement import movement_blocked_cells
        from wakfu_server.combat_casting_los import native_casting_ray

        # Declared flat native-QI fixture: radius1 source and stacked-Z queries
        # exercise complete XY footprints, not a claim about a published map.
        actor = Actor(7, 0, (1, 1, 0), 100, 6, 3, 10, 1, 3, True)
        actor.physical_radius = 1
        other = Actor(-7, 1, (4, 3, 0), 100, 6, 3, 5, 1)
        other.physical_radius = 0
        cells = {(x, y, 0) for x in range(7) for y in range(7)}
        fight = Fight(
            601, (actor, other), cells, {0: {actor.position}, 1: {other.position}}
        )
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_qi_fight import (
            prepare_fresh_actor_slots,
            install_fresh_actor_slots,
        )

        fight.native_qi_snapshot = dict(
            x=0, y=0, width=7, height=7, cell_masks=[0] * 49
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        actor.native_obstacle_id = 0
        other.native_obstacle_id = 1
        install_fresh_actor_slots(
            fight, prepare_fresh_actor_slots(fight, physical_radii={7: 1, -7: 0})
        )
        for member in fight.actors.values():
            member.native_physical_position = member.position
        fight.native_pointer_checkpoint = NativePointerCheckpoint(ActualActorQI(fight))
        registry = current_registry(fight)
        fight.native_qi_movement_override = False
        fight.native_qi_ignored_slots = []
        queries = set(cells) | {(3, 3, 1), (0, 0, 1)}

        def compare():
            # The old whole-population representation remains an independent
            # authoritative legacy path; no movement or registry result is faked.
            current_registry(fight)
            legacy = NativeQIRegistry(
                fight.native_qi_snapshot,
                registry.slots,
                touched_cells=tuple(registry.qi.cells),
            )
            actual = movement_blocked_cells(fight, actor, queries)
            with patch(
                "wakfu_server.combat_qi_fight.current_registry", return_value=legacy
            ):
                expected = movement_blocked_cells(fight, actor, queries)
            self.assertEqual(actual, expected)
            return actual

        blocked = compare()
        self.assertIn((0, 0, 0), blocked)  # Radius1 intersects exterior terrain.
        self.assertIn((3, 3, 0), blocked)  # Radius1 intersects actual other QK.
        self.assertIn((3, 3, 1), blocked)  # XY occupancy is independent of query Z.
        self.assertNotIn((2, 2, 0), blocked)
        original = registered_obstacle(registry, other.native_obstacle_id)
        complete = registered_slot(registry, other.native_obstacle_id)
        self.assertEqual(
            original, {k: value for k, value in complete.items() if k != "indexed"}
        )
        original["position"][0] = 999
        self.assertEqual(
            registered_obstacle(registry, other.native_obstacle_id)["position"], [4, 3]
        )
        registry.qi.move_actor(other, (5, 5, 0))
        fight.native_pointer_checkpoint.publish()
        self.assertNotIn((3, 3, 0), compare())
        self.assertEqual(
            registered_obstacle(registry, other.native_obstacle_id)["position"], [5, 5]
        )
        registry.toggle(other.native_obstacle_id, ["actor", other.id], False)
        fight.native_pointer_checkpoint.publish()
        self.assertNotIn((4, 4, 0), compare())
        registry.toggle(other.native_obstacle_id, ["actor", other.id], True)
        fight.native_pointer_checkpoint.publish()
        self.assertIn((4, 4, 0), compare())
        fight.native_qi_ignored_slots = [other.native_obstacle_id]
        self.assertNotIn((4, 4, 0), compare())
        fight.native_qi_ignored_slots = []
        fight.native_qi_movement_override = True
        self.assertNotIn((4, 4, 0), compare())
        self.assertIn((0, 0, 0), compare())  # Override cannot bypass arena masks.
        fight.native_qi_movement_override = False
        width = fight.native_qi_snapshot["width"]
        x0, y0 = fight.native_qi_snapshot["x"], fight.native_qi_snapshot["y"]
        fight.native_qi_snapshot["cell_masks"][(2 - y0) * width + 2 - x0] = 768
        self.assertIn((2, 2, 0), compare())

        # LOS reads current object properties, never a cached indexed verdict.
        properties = set()
        authority = SimpleNamespace(properties=lambda current, selected: properties)
        with patch(
            "wakfu_server.combat_native_los_ray.cast_rays",
            return_value=((True, ((5, 5),)),),
        ):

            def cast(ignored=()):
                return native_casting_ray(
                    fight,
                    authority,
                    1,
                    (1, 1, 0),
                    (6, 6, 0),
                    source_height=0,
                    target_height=0,
                    ignored_slots=ignored,
                )

            self.assertFalse(cast())
            self.assertTrue(cast((other.native_obstacle_id,)))
            properties.add(5)
            self.assertTrue(cast())
            properties.clear()
            # Observe actual null QK; native QI.h stops on null without deriving
            # a population from actor HP or recovering the historical actor.
            byte = other.native_obstacle_id
            registry.qi.slots[byte] = None
            fight.native_pointer_checkpoint.publish()
            self.assertIsNone(registered_obstacle(registry, byte))
            self.assertTrue(cast())
        # Use a separate fresh ownership fixture for stale-object rejection.
        from test_combat_pointer_qi_projection import PointerQIProjectionTests

        fresh, _, main, _ = PointerQIProjectionTests().real_registry()
        fresh.actors[main.id] = deepcopy(main)
        with self.assertRaisesRegex(ValueError, "actor object was replaced"):
            current_registry(fresh)
        fight.native_qi_ignored_slots = [True]
        with self.assertRaises(ValueError):
            movement_blocked_cells(fight, actor, cells)
