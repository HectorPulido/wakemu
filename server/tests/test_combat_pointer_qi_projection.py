"""Fresh canonical QI projections without repeated full-population allocation."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import PropertyMock, patch

from wakfu_server.combat_pointer_qi_registry import (
    PointerRegistryCompatibility,
    registered_slot,
    registered_terrain,
    registered_population,
)
from wakfu_server.combat_qi_fight import current_registry


class CountingCell:
    def __init__(self, values):
        self.values = tuple(values)
        self.reads = 0

    def order(self):
        self.reads += 1
        return self.values


class PointerQIProjectionTests(unittest.TestCase):
    def synthetic_registry(self):
        objects = [
            SimpleNamespace(kind="actor", identity=i + 1, x=i, y=0, radius=0)
            for i in range(12)
        ]
        cells = {(i, 0): CountingCell((i,)) for i in range(12)}
        cells[(12, 0)] = CountingCell(())  # Touched-empty is retained.
        qi = SimpleNamespace(
            fight=SimpleNamespace(
                native_qi_snapshot=dict(
                    x=0, y=0, width=13, height=1, cell_masks=[0] * 13
                )
            ),
            slots=objects + [None] * (127 - len(objects)),
            cells=cells,
            movement_blocking={id(obj): i % 2 == 0 for i, obj in enumerate(objects)},
        )
        return PointerRegistryCompatibility(qi)

    def real_registry(self):
        from wakfu_server.combat_state import Actor, Fight
        from native_combat_fixture import initialize_fixture_qi
        from wakfu_server.combat_pointer_qi_actor import ActualActorQI
        from wakfu_server.combat_pointer_qi_checkpoint import NativePointerCheckpoint

        actor = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True)
        other = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1)
        cells = {(x, 0, 0) for x in range(4)}
        fight = Fight(
            77, (actor, other), cells, {0: {actor.position}, 1: {other.position}}
        )
        initialize_fixture_qi(fight)
        actor.native_physical_position = actor.position
        other.native_physical_position = other.position
        fight.native_pointer_checkpoint = NativePointerCheckpoint(ActualActorQI(fight))
        return fight, current_registry(fight), actor, other

    def test_bulk_rows_scan_each_cell_once_and_match_complete_legacy_projection(self):
        registry = self.synthetic_registry()
        rows = registry.slots
        self.assertEqual(len(rows), 127)
        self.assertEqual(sum(cell.reads for cell in registry.qi.cells.values()), 13)
        expected = [
            None
            if obj is None
            else dict(
                identity=[obj.kind, obj.identity],
                position=[obj.x, obj.y],
                radius=obj.radius,
                indexed=any(byte in cell.values for cell in registry.qi.cells.values()),
                movement_blocking=registry.qi.movement_blocking[id(obj)],
            )
            for byte, obj in enumerate(registry.qi.slots)
        ]
        self.assertEqual(rows, expected)
        rows[0]["identity"][1] = 1000
        rows[0]["position"][0] = 1000
        self.assertEqual(registry.slot_row(0)["identity"], ["actor", 1])
        self.assertEqual(registry.slot_row(0)["position"], [0, 0])

    def test_single_slot_does_not_project_unrelated_rows(self):
        registry = self.synthetic_registry()
        with patch.object(
            PointerRegistryCompatibility,
            "slots",
            new_callable=PropertyMock,
            side_effect=AssertionError("full projection"),
        ):
            self.assertEqual(registered_slot(registry, 8)["identity"], ["actor", 9])
            self.assertIsNone(registered_slot(registry, 126))
        self.assertEqual(registered_slot(registry, -1), registry.slots[-1])
        with self.assertRaises(IndexError):
            registered_slot(registry, 127)

    def test_rows_and_terrain_stay_fresh_after_move_toggle_and_mask_update(self):
        fight, registry, actor, other = self.real_registry()
        qi = registry.qi
        original = registered_slot(registry, actor.native_obstacle_id)
        qi.move_actor(actor, (2, 0, 0))
        fight.native_pointer_checkpoint.publish()
        current_registry(
            fight
        )  # Existing ownership and topology validation still runs.
        self.assertEqual(original["position"], [0, 0])
        self.assertEqual(
            registered_slot(registry, actor.native_obstacle_id)["position"], [2, 0]
        )
        self.assertEqual(registry.ordered_U(0, 0), ())
        registry.toggle(actor.native_obstacle_id, ["actor", actor.id], False)
        self.assertFalse(registered_slot(registry, actor.native_obstacle_id)["indexed"])
        registry.toggle(actor.native_obstacle_id, ["actor", actor.id], True)
        self.assertTrue(registered_slot(registry, actor.native_obstacle_id)["indexed"])
        fight.native_qi_snapshot["cell_masks"][2] = 768
        self.assertTrue(registered_terrain(registry).Z(2, 0))
        self.assertTrue(registry.native_g(2, 0))
        self.assertEqual(
            registered_slot(registry, other.native_obstacle_id)["position"], [1, 0]
        )

    def test_null_slot_order_and_empty_touched_cells_survive_fresh_reads(self):
        fight, registry, actor, other = self.real_registry()
        qi = registry.qi
        byte = other.native_obstacle_id
        registry.toggle(byte, ["actor", other.id], False)
        self.assertIn((1, 0), registry.snapshot().occupancy)
        self.assertEqual(registry.snapshot().U(1, 0), frozenset())
        registry.toggle(byte, ["actor", other.id], True)
        order = registry.ordered_U(1, 0)
        self.assertEqual(order, (byte,))
        qi.slots[
            byte
        ] = None  # Explicit native null-slot observation, not roster recovery.
        self.assertIsNone(registered_slot(registry, byte))
        self.assertEqual(registry.ordered_U(1, 0), order)
        self.assertEqual(registry.snapshot().U(1, 0), frozenset(order))

    def test_reacquisition_keeps_stale_canonical_actor_rejection(self):
        fight, registry, actor, _ = self.real_registry()
        self.assertIs(registry.qi.objects[actor.id].actor, actor)
        fight.actors[actor.id] = deepcopy(actor)
        with self.assertRaisesRegex(ValueError, "actor object was replaced"):
            current_registry(fight)

    def test_los_reads_masks_and_order_without_full_snapshot_or_slot_projection(self):
        from wakfu_server.combat_casting_los import native_casting_ray

        fight, registry, actor, other = self.real_registry()
        properties = set()
        authority = SimpleNamespace(properties=lambda fight, actor: properties)
        with patch(
            "wakfu_server.combat_qi_fight.current_registry", return_value=registry
        ), patch(
            "wakfu_server.combat_native_los_ray.cast_rays",
            return_value=((True, ((1, 0),)),),
        ), patch.object(
            registry, "snapshot", side_effect=AssertionError("full occupancy")
        ), patch.object(
            PointerRegistryCompatibility,
            "slots",
            new_callable=PropertyMock,
            side_effect=AssertionError("full slots"),
        ):

            def cast(ignored=()):
                return native_casting_ray(
                    fight,
                    authority,
                    1,
                    actor.position,
                    (3, 0, 0),
                    source_height=0,
                    target_height=0,
                    ignored_slots=ignored,
                )

            self.assertFalse(cast())
            self.assertTrue(cast((other.native_obstacle_id,)))
            properties.add(5)  # Current visibility is never memoized.
            self.assertTrue(cast())
            properties.clear()
            registry.toggle(other.native_obstacle_id, ["actor", other.id], False)
            self.assertTrue(cast())

    def test_casting_mask_and_collision_queries_do_not_allocate_occupancy(self):
        from wakfu_server.combat_casting_context import NativeOwnedCastingContext

        fight, registry, actor, other = self.real_registry()
        fight.native_qi_ignored_slots = []
        fight.native_qi_movement_override = False
        context = NativeOwnedCastingContext(
            None,
            fight,
            {},
            SimpleNamespace(caster_id=actor.id, cell=(1, 0, 0)),
            None,
            {},
        )
        context._registry = registry
        with patch.object(
            registry, "snapshot", side_effect=AssertionError("full occupancy")
        ):
            self.assertTrue(context.qi_in_bounds())
            self.assertFalse(context.qi_p())
            self.assertTrue(context.qi_r())
            self.assertTrue(context.qi_g())
            fight.native_qi_ignored_slots = [other.native_obstacle_id]
            self.assertFalse(context.qi_g())
            registry.toggle(other.native_obstacle_id, ["actor", other.id], False)
            self.assertFalse(context.qi_g())

    def test_legacy_population_keeps_snapshot_membership_without_byte_topology(self):
        from wakfu_server.combat_qi_registry import NativeQIRegistry
        from wakfu_server.combat_casting_context import NativeOwnedCastingContext

        fight, _, actor, _ = self.real_registry()
        legacy = NativeQIRegistry(
            fight.native_qi_snapshot,
            fight.native_qi_slots,
            touched_cells=fight.native_qi_touched_cells,
        )
        self.assertIsNone(legacy.byte_topology)
        with patch.object(legacy, "snapshot", wraps=legacy.snapshot) as snapshot:
            terrain, occupants = registered_population(legacy)
            self.assertTrue(terrain.R(0, 0))
            self.assertEqual(occupants(0, 0), frozenset({actor.native_obstacle_id}))
            self.assertFalse(occupants(3, 0))
            self.assertEqual(snapshot.call_count, 1)
        context = NativeOwnedCastingContext(
            None,
            fight,
            {},
            SimpleNamespace(caster_id=actor.id, cell=(3, 0, 0)),
            None,
            {},
        )
        context._registry = legacy
        context.root_record = lambda _: dict(
            native_casting_collision_area=dict(
                area_class="anD",
                area_native="point",
            )
        )
        self.assertTrue(context.root_collision_clear(1))


if __name__ == "__main__":
    unittest.main()
