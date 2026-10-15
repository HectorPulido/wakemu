import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_displacement import NativeDisplacementHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_simple_area import simple_area_constructor


class GuardedActors(dict):
    def __getitem__(self, identity):
        if identity == 17:
            raise AssertionError("Qq teleport recipient was indexed as fighter")
        return super().__getitem__(identity)

    def get(self, identity, default=None):
        if identity == 17:
            raise AssertionError("Qq teleport recipient was resolved as fighter")
        return super().get(identity, default)


class NativeTeleportAreaGuardTests(unittest.TestCase):
    def fixture(self):
        definition = dict(
            type="SIMPLE",
            native_class="bcW",
            native_type_id=6,
            native_container_type=3,
            native_area_properties=[],
            entry_masks=[],
            native_shape_class="anD",
            native_shape_description="point",
        )
        row = dict(
            uid=17,
            reference=314,
            level=1,
            cell=(2, 2, 0),
            owner_id=None,
            direction=3,
            native_area_contract="fbb",
            native_type_id=6,
            native_simple_constructor=simple_area_constructor(definition),
            native_running_effect_manager=False,
            native_obstacle_id=-1,
        )
        fight = SimpleNamespace(
            actors=GuardedActors(),
            native_effect_areas={17: row},
            native_retired_area_managers={},
        )
        handler = NativeDisplacementHandler(
            fight,
            [],
            action_id=1,
            allocate_uid=lambda: self.fail("Qq recipient must not allocate an effect"),
            authority=lambda *_: self.fail(
                "Qq recipient must not use fighter authority"
            ),
        )
        effect = dict(
            effect_class=302,
            parameters=[],
            parameter_count=0,
            native_effect_flags=[],
        )
        invocation = EffectInvocation(64725, 95, 17, None, (4, 0, 0))
        return definition, row, fight, handler, effect, invocation

    def test_q_q_recipient_is_preserved_without_fighter_lookup_or_mutation(self):
        definition, row, fight, handler, effect, invocation = self.fixture()
        before_row = dict(row)
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"314": definition},
        ):
            geometry, accepted = handler._calculate_teleport(effect, invocation)
            self.assertEqual(geometry, {"actor": None})
            self.assertFalse(accepted)
            with self.assertRaisesRegex(
                ValueError, "Unknown native teleport recipient"
            ):
                handler._calculate_teleport(
                    effect, EffectInvocation(64725, 95, 999, None, (4, 0, 0))
                )
        self.assertEqual(row, before_row)
        self.assertEqual(fight.actors, {})
        self.assertEqual(fight.native_effect_areas, {17: row})
        self.assertEqual(handler.packets, [])

    def test_q_q_owner_redirect_resolves_the_registered_owner_fighter(self):
        definition, row, fight, handler, effect, invocation = self.fixture()
        row["uid"] = 9
        row["owner_id"] = -200
        owner = SimpleNamespace(id=-200, position=(1, 1, 0), team=0)
        fight.actors[-200] = owner
        fight.native_effect_areas = {9: row}
        effect["parameters"] = [1, 0, 1, 0, 1, 0, 1, 0]
        invocation = EffectInvocation(269482, 95, 9, None, (4, 0, 0))
        handler.authority = lambda _fight, actor: SimpleNamespace(
            targeting={"is_eGj": actor is owner}
        )
        expected_geometry = {
            "actor": owner,
            "force": True,
            "carried": True,
            "check_cells": True,
            "destination": invocation.cell,
        }
        from wakfu_server.combat_state_managers import selected_area_pv_scope

        with (
            patch(
                "wakfu_server.combat.combat_effect_area.native_effect_areas",
                return_value={"314": definition},
            ),
            patch(
                "wakfu_server.combat_displacement.displacement_geometry",
                return_value=expected_geometry,
            ) as geometry,
            patch.object(handler, "_teleport_accepted", return_value=True),
        ):
            with selected_area_pv_scope(fight, [9]):
                # Native ordered sibling execution can retire Qs while the
                # selected callback still holds the actual Qq PV pointer.
                fight.native_effect_areas.pop(9)
                calculated, accepted = handler._calculate_teleport(effect, invocation)
        self.assertIs(calculated["actor"], owner)
        self.assertTrue(accepted)
        self.assertIs(geometry.call_args.kwargs["source"], owner)
        self.assertIsNone(geometry.call_args.kwargs["target"])
        self.assertTrue(geometry.call_args.kwargs["teleport_recipient_is_fighter"])
        self.assertEqual(fight.native_effect_areas, {})
        self.assertEqual(handler.packets, [])

    def test_q_q_without_owner_redirect_stays_a_noop(self):
        definition, row, fight, handler, effect, invocation = self.fixture()
        row["uid"] = 9
        row["owner_id"] = -200
        fight.actors[-200] = SimpleNamespace(id=-200)
        fight.native_effect_areas = {9: row}
        effect["parameters"] = [0, 0]
        invocation = EffectInvocation(64725, 95, 9, None, (4, 0, 0))
        with (
            patch(
                "wakfu_server.combat.combat_effect_area.native_effect_areas",
                return_value={"314": definition},
            ),
            patch("wakfu_server.combat_displacement.displacement_geometry") as geometry,
        ):
            calculated, accepted = handler._calculate_teleport(effect, invocation)
        self.assertEqual(calculated, {"actor": None})
        self.assertFalse(accepted)
        geometry.assert_not_called()
        self.assertEqual(handler.packets, [])

    def test_q_q_owner_redirect_with_null_owner_stays_a_noop(self):
        definition, row, fight, handler, effect, invocation = self.fixture()
        row["uid"] = 9
        row["owner_id"] = None
        fight.native_effect_areas = {9: row}
        effect["parameters"] = [1, 0]
        invocation = EffectInvocation(269482, 95, 9, None, (4, 0, 0))
        with (
            patch(
                "wakfu_server.combat_effect_area.native_effect_areas",
                return_value={"314": definition},
            ),
            patch("wakfu_server.combat_displacement.displacement_geometry") as geometry,
        ):
            calculated, accepted = handler._calculate_teleport(effect, invocation)
        self.assertEqual(calculated, {"actor": None})
        self.assertFalse(accepted)
        geometry.assert_not_called()
        self.assertEqual(fight.actors, {})
        self.assertEqual(handler.packets, [])


class NativeTeleportRegisteredCorpseTests(unittest.TestCase):
    def test_registered_caster_corpse_moves_without_revival_or_resource_changes(self):
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
            set_global_fighter_status,
        )
        from wakfu_server.combat_displacement import NativeDisplacementHandler
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from unittest.mock import Mock

        corpse = SimpleNamespace(
            id=7,
            hp=0,
            position=(0, 0, 0),
            team=0,
            physical_radius=0,
            native_obstacle_id=9,
            ap=3,
            mp=2,
        )
        selected = SimpleNamespace(
            id=8,
            hp=100,
            position=(2, 0, 0),
            team=1,
            physical_radius=0,
            native_obstacle_id=10,
            ap=6,
            mp=4,
        )
        fight = SimpleNamespace(
            actors={7: corpse, 8: selected},
            events=[
                dict(
                    kind="damage",
                    source_id=8,
                    target_id=7,
                    hp=0,
                    sequence=1,
                ),
                dict(kind="death", actor_id=7, sequence=2),
            ],
            phase="active",
            current=selected,
            id=3,
            native_qi_slots=None,
            _event=lambda *_args, **_kwargs: None,
        )
        initialize_global_pv_collections(fight, (7, 8))
        set_global_fighter_status(fight, 7, "OFF_PLAY")
        from wakfu_server.combat.combat_qi_registry import NativeQIRegistry

        slots = [None] * 127
        slots[9] = dict(
            identity=("actor", 7),
            indexed=True,
            movement_blocking=True,
            position=(0, 0),
            radius=0,
        )
        registry = NativeQIRegistry(
            dict(x=0, y=0, width=5, height=5, cell_masks=[0] * 25), slots
        )
        authority = lambda _fight, actor: SimpleNamespace(
            targeting={
                "baF": actor.hp > 0,
                "baG": actor.hp == 0,
                "baK": False,
                "is_eGj": True,
            },
            is_carried=False,
            is_carrying=False,
        )
        authority.properties = lambda _fight, _actor: ()
        handler = NativeDisplacementHandler(
            fight,
            [],
            action_id=42,
            allocate_uid=lambda: 501,
            authority=authority,
            selected_surface=lambda _fight, _cell: True,
        )
        effect = dict(
            effect_class=302,
            parameters=[0, 0, 0, 0, 0, 0, 0, 0],
            parameter_count=4,
            native_effect_flags=[],
            minimum_level=0,
            maximum_level=32767,
        )
        invocation = EffectInvocation(64725, 95, 7, 8, (4, 0, 0))

        with (
            patch(
                "wakfu_server.combat_qi_fight.current_registry",
                return_value=registry,
            ),
            patch(
                "wakfu_server.combat_displacement.native_definition_timing",
                return_value=None,
            ),
            patch(
                "wakfu_server.combat_displacement_retention.retained_displacement_context",
                return_value=None,
            ),
        ):
            self.assertTrue(handler.native_eligibility(effect, invocation))
            self.assertTrue(handler(effect, (), invocation))

        self.assertEqual(corpse.position, (4, 0, 0))
        self.assertEqual(corpse.hp, 0)
        self.assertEqual((corpse.ap, corpse.mp), (3, 2))
        self.assertEqual((selected.hp, selected.ap, selected.mp), (100, 6, 4))
        self.assertEqual(registry._owned(9, ("actor", 7))["identity"], ("actor", 7))
        self.assertEqual(len(handler.packets), 1)

    def test_unregistered_hp0_recipient_is_rejected_before_qk_or_move(self):
        from wakfu_server.combat_displacement import NativeDisplacementHandler
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
            set_global_fighter_status,
        )
        from unittest.mock import Mock

        corpse = SimpleNamespace(
            id=7,
            hp=0,
            position=(0, 0, 0),
            physical_radius=0,
            native_obstacle_id=9,
        )
        source = SimpleNamespace(
            id=8,
            hp=100,
            position=(2, 0, 0),
            physical_radius=0,
            native_obstacle_id=10,
        )
        fight = SimpleNamespace(
            actors={7: corpse, 8: source},
            events=[],
        )
        initialize_global_pv_collections(fight, (7, 8))
        set_global_fighter_status(fight, 7, "IN_PLAY")
        handler = object.__new__(NativeDisplacementHandler)
        handler.fight = fight
        handler.authority = lambda _fight, _actor: SimpleNamespace(
            targeting={"baF": False, "baG": False, "baK": False},
            is_carried=False,
            is_carrying=False,
        )
        handler.authority.properties = lambda _fight, _actor: ()
        registry = Mock()
        with (
            patch(
                "wakfu_server.combat_qi_fight.current_registry",
                return_value=registry,
            ),
            self.assertRaisesRegex(ValueError, "living ordinary"),
        ):
            handler._ordinary(
                corpse,
                allow_radius=True,
                allow_carrying=True,
                allow_ordinary_corpse=True,
            )
        registry._owned.assert_not_called()
        self.assertEqual(corpse.position, (0, 0, 0))
        self.assertEqual(corpse.hp, 0)

    def test_registered_corpse_without_actual_qk_slot_is_rejected(self):
        from wakfu_server.combat_displacement import NativeDisplacementHandler
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
            set_global_fighter_status,
        )
        from wakfu_server.combat.combat_qi_registry import NativeQIRegistry

        corpse = SimpleNamespace(
            id=7,
            hp=0,
            position=(0, 0, 0),
            physical_radius=0,
            native_obstacle_id=9,
        )
        source = SimpleNamespace(
            id=8,
            hp=100,
            position=(2, 0, 0),
            physical_radius=0,
            native_obstacle_id=10,
        )
        fight = SimpleNamespace(
            actors={7: corpse, 8: source},
            events=[
                dict(kind="damage", source_id=8, target_id=7, hp=0, sequence=1),
                dict(kind="death", actor_id=7, sequence=2),
            ],
        )
        initialize_global_pv_collections(fight, (7, 8))
        set_global_fighter_status(fight, 7, "OFF_PLAY")
        registry = NativeQIRegistry(
            dict(x=0, y=0, width=5, height=5, cell_masks=[0] * 25),
            [None] * 127,
        )
        handler = object.__new__(NativeDisplacementHandler)
        handler.fight = fight
        handler.authority = lambda _fight, _actor: SimpleNamespace(
            targeting={"baF": False, "baG": True, "baK": False},
            is_carried=False,
            is_carrying=False,
        )
        handler.authority.properties = lambda _fight, _actor: ()
        with (
            patch(
                "wakfu_server.combat_qi_fight.current_registry",
                return_value=registry,
            ),
            self.assertRaisesRegex(ValueError, "slot identity mismatch"),
        ):
            handler._ordinary(
                corpse,
                allow_radius=True,
                allow_carrying=True,
                allow_ordinary_corpse=True,
            )
        self.assertEqual(corpse.position, (0, 0, 0))
        self.assertEqual(corpse.hp, 0)

    def test_selected_dead_target_remains_subject_to_native_guard(self):
        from wakfu_server.combat_displacement import NativeDisplacementHandler
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        selected = SimpleNamespace(id=8, hp=0)
        fight = SimpleNamespace(actors={8: selected})
        handler = object.__new__(NativeDisplacementHandler)
        handler.fight = fight
        effect = {"effect_class": 302, "native_effect_flags": []}
        invocation = EffectInvocation(64725, 95, 7, 8, (4, 0, 0))
        with patch(
            "wakfu_server.combat_runner_target_life.runner_target_life_eligible",
            return_value=False,
        ) as selected_guard:
            self.assertFalse(handler.native_eligibility(effect, invocation))
        selected_guard.assert_called_once_with(
            fight, selected, effect, invocation=invocation
        )


if __name__ == "__main__":
    unittest.main()
