"""Forced collision observes actual QK population before shared AP reactions."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_displacement import NativeDisplacementHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation


class DisplacementAuthority:
    def __call__(self, fight, actor):
        return SimpleNamespace(
            is_carried=False,
            is_carrying=False,
            native_instance_id=None,
        )

    def properties(self, fight, actor):
        return frozenset()


class ForcedCollisionQITests(unittest.TestCase):
    def setUp(self):
        self.actor = SimpleNamespace(
            id=7,
            position=(0, 0, 0),
            team=0,
            hp=10,
            native_obstacle_id=0,
            physical_radius=0,
        )
        self.collider = SimpleNamespace(
            id=8,
            position=(2, 0, 0),
            team=1,
            hp=10,
            native_obstacle_id=1,
            physical_radius=0,
        )
        slots = [None] * 127
        for actor in (self.actor, self.collider):
            slots[actor.native_obstacle_id] = dict(
                identity=["actor", actor.id],
                position=list(actor.position[:2]),
                radius=0,
                indexed=True,
                movement_blocking=True,
            )
        self.fight = SimpleNamespace(
            phase="active",
            current=7,
            actors={7: self.actor, 8: self.collider},
            id=1,
            walkable={(x, 0, 0) for x in range(4)},
            edges=None,
            native_qi_snapshot=dict(
                x=0, y=0, width=4, height=1, cell_masks=[0, 0, 0, 0]
            ),
            native_qi_slots=slots,
            native_qi_touched_cells=[],
            native_qi_movement_override=False,
            native_qi_ignored_slots=[],
            _event=lambda *args, **kwargs: None,
        )
        self.packets = []
        self.handler = NativeDisplacementHandler(
            self.fight,
            self.packets,
            action_id=1,
            allocate_uid=lambda: 10,
            authority=DisplacementAuthority(),
        )
        self.handler._ordinary = lambda actor, **kwargs: set()

    def test_singleton_collider_is_actual_registered_actor(self):
        self.assertEqual(
            self.handler._forced_obstruction(self.actor, (2, 0, 99)), (True, 8)
        )

    def test_ignored_slot_disables_obstruction_without_changing_population(self):
        self.fight.native_qi_ignored_slots = [1]
        self.assertEqual(
            self.handler._forced_obstruction(self.actor, (2, 0, 0)), (False, None)
        )
        self.assertIsNotNone(self.fight.native_qi_slots[1])

    def test_terrain_obstruction_retains_unfiltered_qi_v_recipient(self):
        self.fight.native_qi_snapshot["cell_masks"][2] = 256
        self.fight.native_qi_slots[1]["movement_blocking"] = False
        self.assertEqual(
            self.handler._forced_obstruction(self.actor, (2, 0, 0)), (True, 8)
        )

    def test_multiple_slots_refuse_unproven_trove_iteration(self):
        self.collider.position = (0, 0, 0)
        self.fight.native_qi_slots[1]["position"] = [0, 0]
        with self.assertRaisesRegex(ValueError, "byte iterator topology"):
            self.handler._forced_obstruction(self.actor, (0, 0, 0))

    def test_multiple_slots_select_actual_trove_first_instead_of_smallest_slot(self):
        from wakfu_server.combat_qi_fight import current_registry

        self.collider.position = (0, 0, 0)
        self.fight.native_qi_slots[1]["position"] = [0, 0]
        registry = current_registry(self.fight)
        registry.capture_fresh_cell_topology([0, 1])
        self.fight.native_qi_byte_topology = registry.serialized_byte_topology()
        self.assertEqual(registry.ordered_U(0, 0), (1, 0))
        self.assertEqual(
            self.handler._forced_obstruction(self.actor, (0, 0, 0)), (True, 8)
        )

    def test_actual_registered_fake_fighter_is_pv_without_actor_fabrication(self):
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_fake_fighter import fake_fighter_constructor
        from wakfu_server.combat_state_ledger import StateLedger

        definition = native_effect_areas()["1034"]
        constructor = fake_fighter_constructor(definition)
        self.fight.native_effect_areas = {
            91: dict(
                uid=91,
                reference=1034,
                cell=(2, 0, 0),
                native_area_contract="faW",
                native_obstacle_id=2,
                native_obstacle_source="QI.f(QK)",
                native_faw_constructor=constructor,
                native_running_effect_manager=True,
                state_ledger=StateLedger(91),
            )
        }
        self.fight.native_qi_slots[2] = dict(
            identity=["effect_area", 91],
            position=[2, 0],
            radius=0,
            indexed=True,
            movement_blocking=True,
        )
        self.collider.position = (3, 0, 0)
        self.fight.native_qi_slots[1]["position"] = [3, 0]
        self.assertEqual(
            self.handler._forced_obstruction(self.actor, (2, 0, 0)), (True, 91)
        )
        self.assertNotIn(91, self.fight.actors)

    def execute(self, effect_class):
        effect = dict(effect_class=effect_class, native_effect_flags=[])
        geometry = dict(
            actor=self.actor,
            distance=3,
            vector=(1, 0),
            stop=None,
            loss_ap=True,
            collision_reactions=effect_class in (300, 301),
        )
        with patch("wakfu_server.combat_displacement.native_definition_timing"), patch(
            "wakfu_server.combat_displacement.displacement_geometry",
            return_value=geometry,
        ):
            return self.handler(effect, None, EffectInvocation(1, 1, 7, 7, (3, 0, 0)))

    def test_collision_callback_observes_committed_geometry_before_l3(self):
        events = []

        def collision(effect, invocation, **context):
            events.append(("collision", self.actor.position, context))

        self.handler.collision_executor = collision
        self.handler._finish_events = lambda *args: events.append(("finish",))
        self.assertTrue(self.execute(300))
        self.assertEqual(events[0][0:2], ("collision", (1, 0, 0)))
        self.assertEqual(
            events[0][2],
            dict(uid=10, value=1, displaced_id=7, collider_id=8, loss_ap=True),
        )
        self.assertEqual(events[1], ("finish",))
        self.assertEqual(tuple(self.fight.native_qi_slots[0]["position"]), (1, 0))

    def test_nonreactive_331_and_305_truncate_without_collision_callback(self):
        for effect_class in (331, 305):
            with self.subTest(effect_class=effect_class):
                self.setUp()
                self.handler.collision_executor = lambda *a, **kw: self.fail(
                    "fOs=false"
                )
                self.assertTrue(self.execute(effect_class))
                self.assertEqual(self.actor.position, (1, 0, 0))


if __name__ == "__main__":
    unittest.main()
