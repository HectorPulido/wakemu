"""Original class2 captured dependency source, zero roots, and nested307 construction."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from wakfu_server.combat_captured_dependencies import (
    nested_profiles,
    captured_effect_catalog,
    captured_zero_catalog,
    merge_zero_component,
)
from wakfu_server.combat_summon_spellbook import profile_abilities, fresh_action_book
from wakfu_server.combat_summon_initial_states import native_initial_states
from wakfu_server.combat_summon_creation import NativeSummonBuilder
from wakfu_server.combat_summon import SummonSpecification


class CapturedClassDependencyTests(unittest.TestCase):
    def test_nested_profiles_extend_construction_without_becoming_capturable_roster(
        self,
    ):
        from wakfu_server.combat_captured_profiles import native_captured_profiles

        nested = nested_profiles()
        self.assertEqual(
            set(map(int, nested)), {1267, 1268, 1269, 1270, 4250, 4745, 4755, 5115}
        )
        self.assertFalse(set(nested) & set(native_captured_profiles()))
        for reference, profile in nested.items():
            self.assertEqual(
                profile_abilities()[reference]["abilities"], profile["abilities"]
            )
            self.assertEqual(
                native_initial_states()[reference]["initial_state_triples"],
                profile["initial_state_triples"],
            )
            self.assertEqual(
                len(fresh_action_book(int(reference), 153)["actions"]),
                len(profile["abilities"]),
            )

    def test_attested_remote_active_metadata_fills_missing_without_changing_identity(
        self,
    ):
        from wakfu_server.combat_captured_dependencies import merge_captured_effects

        source = captured_effect_catalog()["effects"]["293383"]
        previous = dict(source)
        previous.pop("native_active_effect")
        merged = merge_captured_effects({"293383": previous})
        self.assertEqual(merged["293383"], source)
        self.assertNotIn("native_active_effect", previous)
        with self.assertRaises(ValueError):
            merge_captured_effects(
                {
                    "293383": {
                        **source,
                        "native_active_effect": not source["native_active_effect"],
                    }
                }
            )

    def test_original_typed_closure_contains_all_native_zero_roots_and_children(self):
        effects = captured_effect_catalog()["effects"]
        zero = captured_zero_catalog()
        self.assertEqual(len(zero["spells"]), 195)
        for row in zero["spells"].values():
            self.assertTrue(set(map(str, row[2])) <= set(effects))
        for effect in effects.values():
            self.assertTrue(set(map(str, effect["children"])) <= set(effects))
        with self.assertRaises(ValueError):
            merge_zero_component({"1": [1]}, {"1": [2]})

    def test_real_nested5115_constructor_keeps_fresh_origin_and_original_initial_states(
        self,
    ):
        fixture = json.loads(
            (
                Path(__file__).parent / "fixtures/captured-class-nested-native.json"
            ).read_text()
        )
        profile = fixture["native_profile_export"]["profiles"]["5115"]

        class Authority:
            def __call__(self, fight, actor):
                return SimpleNamespace(summon_root_id=42, native_instance_id=1)

            def world_properties(self, fight, actor):
                return frozenset()

        caster = SimpleNamespace(id=42, owner_id=3, controlled=True)
        preview = SimpleNamespace(actors={42: caster})
        initialized = []
        builder = NativeSummonBuilder(
            Authority(),
            characteristics=fixture["actor_catalog"],
            properties={"npc": {"5115": profile}},
            initialize_states=lambda fight, actor, plan: initialized.extend(plan),
        )
        with patch(
            "wakfu_server.combat_summon_creation.register_fresh_summon_obstacle",
            side_effect=lambda fight, actor: setattr(actor, "native_obstacle_id", 1),
        ):
            actor, registration = builder(
                preview,
                SummonSpecification(5115, 153, False, 3, 0, "caster", 1),
                42,
                901,
                (3, 4, 0),
            )
        self.assertEqual([row.state_id for row in initialized], [6175])
        self.assertFalse(actor.native_summoned_from_symbiot)
        self.assertEqual(actor.native_summon_action_book["actions"], [])
        self.assertEqual(
            registration.fight_properties, frozenset(profile["fight_properties"])
        )

    def test_native_nested307_effect_dispatches_original_profile_and_packet(self):
        from wakfu_server.combat_summon_handler import NativeSummonHandler
        from wakfu_server.combat_summon import RegisteredSummonAuthority
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_effect_dispatch import (
            EffectDispatcher,
            EffectInvocation,
        )
        from wakfu_server.combat_conditions import ConditionContext
        import sys

        fixture = json.loads(
            (
                Path(__file__).parent / "fixtures/captured-class-nested-native.json"
            ).read_text()
        )
        profile = fixture["native_profile_export"]["profiles"]["5115"]

        class Preview(SimpleNamespace):
            @property
            def current(self):
                return self.actors[self.order[self.turn_index]]

        class Authority:
            def __call__(self, fight, actor):
                return SimpleNamespace(summon_root_id=42, native_instance_id=1)

            def world_properties(self, fight, actor):
                return frozenset()

        class FixtureRegistration(RegisteredSummonAuthority):
            def __call__(self, fight, actor):
                return self.ordinary(fight, actor)

        caster = SimpleNamespace(
            id=42,
            owner_id=3,
            controlled=True,
            native_obstacle_id=0,
            hp=40,
            position=(0, 0, 0),
            effective_level=153,
            direction=3,
            team=0,
        )
        preview = Preview(
            id=1,
            actors={42: caster},
            phase="active",
            order=[42],
            turn_index=0,
            walkable={(3, 4, 0)},
        )
        ids = iter((900, 901))
        packets = []
        initialized = []
        with patch(
            "wakfu_server.combat_summon_creation.native_actor_catalog",
            return_value=fixture["actor_catalog"],
        ), patch(
            "wakfu_server.combat_summon_handler.native_actor_catalog",
            return_value=fixture["actor_catalog"],
        ), patch(
            "wakfu_server.combat_summon_creation.native_property_catalog",
            return_value={"npc": {"5115": profile}},
        ), patch(
            "wakfu_server.combat_summon_creation.register_fresh_summon_obstacle",
            side_effect=lambda fight, actor: setattr(actor, "native_obstacle_id", 1),
        ), patch.dict(
            sys.modules,
            {
                "wakfu_server.monsters": SimpleNamespace(
                    reference=lambda ref: {"min_level": profile["minimum_level"]}
                )
            },
        ):
            handler = NativeSummonHandler(
                preview,
                packets,
                action_id=2,
                allocate_uid=lambda: next(ids),
                context=lambda *args: StatExecutionContext(
                    True, True, None, False, b""
                ),
                actor_authority=FixtureRegistration(Authority()),
                container_level=lambda inv: (False, 0),
                container=lambda inv: ({"container_type": 1}, 42),
            )
            handler.builder.initialize_states = (
                lambda fight, actor, plan: initialized.extend(plan)
            )
            native = captured_effect_catalog()["effects"]["293383"]
            dispatcher = EffectDispatcher(
                {"293383": native},
                {307: handler},
                resolve=lambda effect, inv: (inv,),
                condition_context=lambda inv: ConditionContext({}),
                probability_accepts=lambda *args: True,
                group_cells=lambda *args: (),
                actor_position=lambda identity: preview.actors[identity].position,
            )
            self.assertTrue(
                dispatcher.execute(EffectInvocation(293383, 153, 42, None, (3, 4, 0)))
            )
        actor = preview.actors[901]
        self.assertFalse(actor.native_summoned_from_symbiot)
        self.assertEqual(actor.effective_level, profile["minimum_level"])
        self.assertEqual(actor.native_controller_id, actor.id)
        self.assertEqual([row.state_id for row in initialized], [6175])
        self.assertEqual(len(packets), 1)
        self.assertEqual(preview.order, [42, 901])
