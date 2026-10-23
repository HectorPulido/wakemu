"""Original eNZ uses eHg.dnz, including registered null-Qf faV pointers."""
from copy import deepcopy
import unittest


class NativeAreaInFightConditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_combat_runtime_adapter import ServerAdapterTests

        ServerAdapterTests.setUpClass()

    def fixture(self):
        from test_combat_runtime_adapter import ServerAdapterTests
        from wakfu_server.combat_encounter_glyph_bootstrap import SOURCE
        from wakfu_server.combat_environment_glyphs import ensure_environment_glyphs
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        fixture = ServerAdapterTests()
        fixture.setUp()
        fight = fixture.preview
        fight.walkable.add((2, 3, 0))
        fight.native_effect_areas = {}
        initialize_global_pv_collections(fight, tuple(fight.actors))
        fight.native_environment_glyph_constructors = [
            dict(
                uid=901,
                reference=910,
                cell=(2, 3, 0),
                level=0,
                policy="wakemu.unit.in-fight-original-faY.v1",
                source=SOURCE,
                authority="explicit-unit-native-constructor",
                source_url="unit://neutral-pv",
            )
        ]
        ensure_environment_glyphs(fight)
        return fight, fixture.adapter

    def test_actual_neutral_pv_and_clone_use_original_literal_dnz_without_becoming_fighters(
        self,
    ):
        from wakfu_server.combat_conditions import evaluate_condition
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        fight, adapter = self.fixture()
        for candidate in (fight, deepcopy(fight)):
            context = adapter.condition(
                candidate, {}, None, EffectInvocation(235510, 1, 901, 7, (2, 3, 0))
            )
            caster = context.actors["caster"]
            self.assertEqual(caster.actor_id, 901)
            self.assertFalse(caster.is_native_fighter)
            self.assertFalse(caster.is_player)
            self.assertTrue(evaluate_condition("IsInFight()", context))
            self.assertTrue(evaluate_condition('IsInFight("target")', context))
            self.assertNotIn("state_ledger", candidate.native_effect_areas[901])

    def test_retired_original_pointer_stays_true_but_pruned_and_foreign_sources_are_rejected(
        self,
    ):
        from wakfu_server.combat_conditions import evaluate_condition
        from wakfu_server.combat_effect_area import remove_owned_hour_area
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_state_managers import selected_area_pv_scope

        fight, adapter = self.fixture()
        invocation = EffectInvocation(235510, 1, 901, 7, (2, 3, 0))
        with selected_area_pv_scope(fight, (901,)):
            remove_owned_hour_area(fight, 901)
            self.assertNotIn(901, fight.native_effect_areas)
            context = adapter.condition(fight, {}, None, invocation)
            self.assertTrue(evaluate_condition("IsInFight()", context))
        with self.assertRaises(ValueError):
            adapter.condition(fight, {}, None, invocation)
        # No owner or same-valued UID from another fight can supply the PV.
        foreign, _other_adapter = self.fixture()
        self.assertIn(901, foreign.native_effect_areas)
        with self.assertRaises(ValueError):
            adapter.condition(fight, {}, None, invocation)

    def test_fighter_dnz_and_wrapper_fallback_authority_are_preserved(self):
        from wakfu_server.combat_conditions import (
            ConditionActor,
            ConditionContext,
            UnknownCondition,
            evaluate_condition,
        )

        context = ConditionContext(
            {
                "caster": ConditionActor(actor_id=7, in_fight=False),
                "target": ConditionActor(actor_id=8, in_fight=True),
            },
            state_null_fallback_absent=False,
        )
        self.assertFalse(evaluate_condition("IsInFight()", context))
        self.assertFalse(evaluate_condition('IsInFight("other")', context))
        self.assertTrue(evaluate_condition('IsInFight("TARGET")', context))
        # A proven resolved wrapper's eHg membership is authoritative, without
        # replacing it with a positive fighter/default owner membership.
        wrapped = ConditionContext(
            {"caster": ConditionActor(actor_id=7, in_fight=True)},
            state_null_fallback_absent=False,
        )
        self.assertTrue(evaluate_condition("IsInFight()", wrapped))
        absent = ConditionContext(
            {},
            null_actor_aliases=frozenset({"caster"}),
            state_null_fallback_absent=True,
        )
        self.assertFalse(evaluate_condition("IsInFight()", absent))
        for context in (
            ConditionContext({}),
            ConditionContext(
                {},
                null_actor_aliases=frozenset({"caster"}),
                state_null_fallback_absent=False,
            ),
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition("IsInFight()", context)
