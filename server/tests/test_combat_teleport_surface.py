"""Teleport consumes actual selected Vy identity independently of occupancy."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_displacement import NativeDisplacementHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_qi_snapshot import NativeQISnapshot
from wakfu_server.combat_qi_surfaces import NativeQISurfaces


class TeleportSelectedSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.actor = SimpleNamespace(id=7, position=(0, 0, 0), team=0)
        self.fight = SimpleNamespace(
            phase="active",
            current=7,
            actors={7: self.actor},
            id=1,
            walkable=set(),
            _event=lambda *a, **k: None,
        )
        self.qi = NativeQISnapshot(dict(x=0, y=0, width=2, height=1, cell_masks=[0, 1]))
        self.surfaces = NativeQISurfaces(
            dict(
                schema="native-QI-Vy-columns-v1",
                map_id=1,
                source_sha256="a" * 64,
                chunks=[
                    dict(
                        x=0,
                        y=0,
                        width=2,
                        height=1,
                        columns=[[1, 0, [[-4, 0], [19, -1]]]],
                    )
                ],
            ),
            map_id=1,
            source_sha256="a" * 64,
        )
        self.packets = []
        self.handler = NativeDisplacementHandler(
            self.fight,
            self.packets,
            action_id=1,
            allocate_uid=lambda: 2,
            # This fixture isolates Vy selection; the actor has no native
            # movement-blocking properties in the independent property gate.
            authority=SimpleNamespace(properties=lambda fight, actor: set()),
            selected_surface=lambda fight, cell: self.surfaces.i(self.qi, *cell),
        )
        self.handler._ordinary = lambda actor, **kwargs: set()

    def execute(self, cell, check_cells=False):
        effect = dict(effect_class=302, native_effect_flags=[])
        geometry = dict(
            actor=self.actor, force=False, destination=cell, check_cells=check_cells
        )
        with patch("wakfu_server.combat_displacement.native_definition_timing"), patch(
            "wakfu_server.combat_displacement.displacement_geometry",
            return_value=geometry,
        ):
            return self.handler(effect, None, EffectInvocation(1, 1, 7, None, cell))

    def test_bypass_accepts_selected_blocked_surface_and_updates_actual_actor(self):
        self.assertTrue(self.execute((1, 0, 19)))
        self.assertEqual(self.actor.position, (1, 0, 19))
        self.assertEqual(len(self.packets), 1)

    def test_bypass_rejects_wrong_selected_altitude_and_outside_arena(self):
        for cell in ((1, 0, -4), (2, 0, 19)):
            with self.subTest(cell=cell):
                self.assertFalse(self.execute(cell))
                self.assertEqual(self.actor.position, (0, 0, 0))
                self.assertEqual(self.packets, [])

    def registered(self, *, mask=1, override=False):
        self.actor.native_obstacle_id = 0
        self.actor.physical_radius = 0
        self.actor.hp = 10
        self.fight.native_qi_snapshot = dict(
            x=0, y=0, width=2, height=1, cell_masks=[0, mask]
        )
        self.fight.native_qi_slots = [None] * 127
        self.fight.native_qi_slots[0] = dict(
            identity=["actor", 7],
            position=[0, 0],
            radius=0,
            indexed=True,
            movement_blocking=True,
        )
        self.fight.native_qi_touched_cells = []
        self.fight.native_qi_movement_override = override
        self.fight.native_qi_ignored_slots = []

    def test_check_cells_requires_registered_population(self):
        with self.assertRaisesRegex(ValueError, "complete owned native QI"):
            self.execute((1, 0, 19), check_cells=True)
        self.assertEqual(self.actor.position, (0, 0, 0))

    def test_check_cells_uses_mask_not_bld_or_walkability(self):
        self.registered()
        self.assertTrue(self.execute((1, 0, 19), check_cells=True))
        self.assertEqual(self.actor.position, (1, 0, 19))

    def test_mask_blocking_remains_even_with_movement_override(self):
        self.registered(mask=257, override=True)
        self.assertFalse(self.execute((1, 0, 19), check_cells=True))
        self.assertEqual(self.actor.position, (0, 0, 0))

    def test_own_qk_is_temporarily_excluded_from_occupancy(self):
        self.registered()
        self.actor.position = (1, 0, 19)
        self.fight.native_qi_slots[0]["position"] = [1, 0]
        self.assertTrue(self.execute((1, 0, 19), check_cells=True))

    def test_prepared_surface_acceptance_precedes_l2_and_is_not_recomputed(self):
        events = []
        enabled = [True]

        def surface(fight, cell):
            events.append("surface")
            return self.surfaces.i(self.qi, *cell) if enabled[0] else None

        def phase(effect, invocation, **context):
            events.append(context["channel"])
            if context["channel"] == 2:
                enabled[0] = False

        self.handler.selected_surface = surface
        self.handler.event_lifecycle = SimpleNamespace(
            phase=phase, displacement_completed=lambda *a, **kw: None
        )
        self.assertTrue(self.execute((1, 0, 19)))
        self.assertEqual(events, [1, "surface", 2, 3, 4])
        self.assertEqual(self.handler.prepared_teleports, {})

    def test_prepared_refusal_finishes_lifecycle_without_movement_or_packet(self):
        events = []
        self.handler.event_lifecycle = SimpleNamespace(
            phase=lambda *a, **kw: events.append(kw["channel"])
        )
        self.assertFalse(self.execute((1, 0, -4)))
        self.assertEqual(events, [1, 2, 3, 4])
        self.assertEqual(self.actor.position, (0, 0, 0))
        self.assertEqual(self.packets, [])
        self.assertEqual(self.handler.prepared_teleports, {})

    def test_cancel_prepared_discards_calculation_when_dispatcher_skips_execution(self):
        self.handler.event_lifecycle = SimpleNamespace(phase=lambda *a, **kw: None)
        effect = dict(effect_class=302, native_effect_flags=[])
        geometry = dict(
            actor=self.actor, force=False, destination=(1, 0, 19), check_cells=False
        )
        with patch(
            "wakfu_server.combat_displacement.displacement_geometry",
            return_value=geometry,
        ):
            invocation = self.handler.prepare(
                effect, None, EffectInvocation(1, 1, 7, None, (1, 0, 19))
            )
        self.assertIn(invocation.native_running_uid, self.handler.prepared_teleports)
        self.handler.cancel_prepared(invocation)
        self.assertEqual(self.handler.prepared_teleports, {})

    def test_native_qe_amount_modifier_at_l2_does_not_modify_destination(self):
        from wakfu_server.combat_final_modifier import final_modifier_source
        from wakfu_server.combat_trigger_value_modifier import mutate_triggering_runner

        def phase(effect, invocation, **context):
            if context["channel"] == 2:
                source = SimpleNamespace(effect_action_id=302)
                with final_modifier_source(source):
                    self.assertFalse(mutate_triggering_runner(1, 999, True))

        self.handler.event_lifecycle = SimpleNamespace(
            phase=phase, displacement_completed=lambda *a, **kw: None
        )
        self.assertTrue(self.execute((1, 0, 19)))
        self.assertEqual(self.actor.position, (1, 0, 19))


if __name__ == "__main__":
    unittest.main()
