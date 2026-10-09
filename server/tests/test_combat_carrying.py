import unittest
import test_combat_qi_fight
from wakfu_server.combat_carrying import (
    carry_registered,
    carrying_relations,
    release_registered,
    set_registered_direction,
)
from wakfu_server.combat_qi_fight import current_registry, move_registered_actor


class CarryingLifecycleTests(unittest.TestCase):
    def fixture(self):
        fixture = test_combat_qi_fight.NativeQIFightLifecycleTests()
        fight, carrier, carried = fixture.fixture(radii=(0, 0))
        fight.native_qi_snapshot["cell_masks"] = [0] * 16
        fixture.initialize(fight)
        carrier.native_los_height = 0
        return fight, carrier, carried

    def test_native_self_carry_rejects_without_relations_or_qi_mutation(self):
        from copy import deepcopy

        fight, carrier, _ = self.fixture()
        before = deepcopy(
            (
                fight.native_qi_slots,
                fight.native_qi_touched_cells,
                fight.native_qi_byte_topology,
                carrier.position,
            )
        )
        self.assertFalse(carry_registered(fight, carrier, carrier, source_uid=1))
        self.assertFalse(carrying_relations(fight, carrier)["is_carrying"])
        self.assertFalse(carrying_relations(fight, carrier)["is_carried"])
        self.assertEqual(
            (
                fight.native_qi_slots,
                fight.native_qi_touched_cells,
                fight.native_qi_byte_topology,
                carrier.position,
            ),
            before,
        )

    def test_reciprocal_carry_move_and_release_preserve_slot(self):
        fight, carrier, carried = self.fixture()
        slot = carried.native_obstacle_id
        self.assertTrue(carry_registered(fight, carrier, carried, source_uid=1))
        self.assertTrue(carrying_relations(fight, carrier)["is_carrying"])
        self.assertTrue(carrying_relations(fight, carried)["is_carried"])
        registry = current_registry(fight)
        self.assertFalse(registry.slots[slot]["indexed"])
        self.assertEqual(
            registry.snapshot().U(0, 0), frozenset({carrier.native_obstacle_id})
        )
        self.assertEqual(registry.snapshot().U(3, 3), frozenset())
        move_registered_actor(fight, carrier, (1, 1, 0))
        self.assertEqual(carried.position, (1, 1, 0))
        self.assertFalse(current_registry(fight).slots[slot]["indexed"])
        self.assertTrue(release_registered(fight, carrier, (2, 1, 0), direction=2))
        self.assertFalse(carrying_relations(fight, carried)["is_carried"])
        self.assertTrue(current_registry(fight).slots[slot]["indexed"])
        self.assertEqual(current_registry(fight).snapshot().U(2, 1), frozenset({slot}))
        self.assertEqual(carried.direction, 2)
        self.assertEqual(carried.native_obstacle_id, slot)

    def test_unknown_raw_relationship_and_stale_coordinates_reject(self):
        fight, carrier, carried = self.fixture()
        carried.native_carrier_id = carrier.id
        with self.assertRaises(ValueError):
            current_registry(fight)
        carried.native_carrier_id = None
        carry_registered(fight, carrier, carried, source_uid=1)
        carried.position = (1, 1, 0)
        with self.assertRaises(ValueError):
            current_registry(fight)

    def test_nested_and_independent_carried_movement_reject_without_changes(self):
        fight, carrier, carried = self.fixture()
        carry_registered(fight, carrier, carried, source_uid=1)
        self.assertFalse(carry_registered(fight, carrier, carried, source_uid=2))
        with self.assertRaises(ValueError):
            move_registered_actor(fight, carried, (1, 0, 0))
        self.assertEqual(carried.position, carrier.position)
        current_registry(fight)

    def test_carrier_direction_delta_propagates_with_wrap(self):
        fight, carrier, carried = self.fixture()
        carrier.direction, carried.direction = 7, 2
        carry_registered(fight, carrier, carried, source_uid=1)
        set_registered_direction(fight, carrier, 1)
        self.assertEqual(carried.direction, 4)
        self.assertTrue(carrying_relations(fight, carried)["is_carried"])

    def test_carry_runner_notifies_after_geometry_before_post_phases(self):
        from types import SimpleNamespace
        from wakfu_server.combat_carry_handler import NativeCarryHandler
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        fight, carrier, carried = self.fixture()
        fight.phase = "active"
        phases, packets = [], []

        class Authority:
            def __call__(self, preview, actor):
                return SimpleNamespace(targeting={"is_eGj": True})

            def properties(self, preview, actor):
                return frozenset()

        class Events:
            def phase(self, effect, invocation, **kwargs):
                phases.append((kwargs["channel"], carried.position))

        handler = NativeCarryHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=iter(range(1, 10)).__next__,
            context=lambda e, i: StatExecutionContext(True, True, None, False, b""),
            authority=Authority(),
            rng=lambda: 0.5,
            delivery=lambda e, i, **kwargs: (12613, b"fixture"),
            selected_height=lambda f, x, y: 0,
        )
        handler.event_lifecycle = Events()
        effect = dict(
            effect_class=334,
            parameters=[],
            parameter_count=0,
            target_masks=[None] * 7,
            native_effect_flags=[],
        )
        invocation = EffectInvocation(1, 1, carrier.id, carried.id, carried.position)
        self.assertTrue(handler(effect, (), invocation))
        self.assertEqual([row[0] for row in phases], [1, 2, 3, 4])
        self.assertEqual(phases[0][1], (3, 3, 0))
        self.assertEqual(phases[2][1], carrier.position)
        self.assertEqual(packets, [(12613, b"fixture")])
        self.assertFalse(handler.prepared)
        # Actual cell-mode eZE has null PV; release the real registered pair.
        throw = dict(
            effect_class=333,
            parameters=[],
            parameter_count=0,
            target_masks=[None] * 7,
            native_effect_flags=[],
        )
        thrown = EffectInvocation(2, 1, carrier.id, None, (2, 1, 0))
        self.assertTrue(handler(throw, (), thrown))
        self.assertFalse(carrying_relations(fight, carrier)["is_carrying"])
        self.assertEqual(carried.position, (2, 1, 0))
        self.assertTrue(
            current_registry(fight).slots[carried.native_obstacle_id]["indexed"]
        )

    def test_composite_authority_scope_preserves_real_reciprocal_population(self):
        from copy import copy
        from wakfu_server.combat_carrying import carry_population_scope

        fight, carrier, carried = self.fixture()
        carry_registered(fight, carrier, carried, source_uid=1)
        ordinary_view = copy(fight)
        ordinary_view.actors = {carrier.id: carrier}
        with self.assertRaises(ValueError):
            carrying_relations(ordinary_view, carrier)
        with carry_population_scope(fight):
            self.assertTrue(carrying_relations(ordinary_view, carrier)["is_carrying"])
            ordinary_view.native_carry_pairs = dict(fight.native_carry_pairs)
            with self.assertRaises(ValueError):
                carrying_relations(ordinary_view, carrier)

    def test_throw_landing_uses_ordered_area_and_actual_selected_height(self):
        from types import SimpleNamespace
        from wakfu_server.combat_carry_handler import NativeCarryHandler

        fight, carrier, carried = self.fixture()
        carry_registered(fight, carrier, carried, source_uid=1)
        selected = []

        def height(preview, x, y):
            selected.append((x, y))
            return 0

        handler = NativeCarryHandler(
            fight,
            [],
            action_id=1,
            allocate_uid=lambda: 2,
            context=None,
            authority=None,
            rng=lambda: 0.5,
            delivery=None,
            selected_height=height,
        )
        # The carrier blocks selected center; native circle order skips OOB
        # offsets and chooses the first real free candidate, not a closest-cell search.
        effect = dict(area_class="anu", area_native="circle-1")
        invocation = SimpleNamespace(cell=(0, 0, 0))
        self.assertEqual(
            handler._landing(effect, invocation, carrier, carried, False), (0, 1, 0)
        )
        self.assertEqual(selected, [(0, 0), (0, 1)])
        self.assertEqual(
            handler._landing(effect, invocation, carrier, carried, True), (0, 0, 0)
        )
