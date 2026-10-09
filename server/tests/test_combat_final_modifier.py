import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_final_modifier import (
    NativeFinalModifier,
    NativeFinalModifierHandler,
    final_modifier_source,
    update_triggering_final,
)
from wakfu_server.combat_event_replay import NativeEventSource
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_damage_healing import damage_amount, healing_amount


def source(modifier=None, family=1):
    return NativeEventSource(
        901,
        339526,
        0,
        7,
        -7,
        (1, 0, 0),
        (0, 2),
        1,
        -7,
        None,
        False,
        False,
        False,
        True,
        effect_action_id=family,
        final_modifier=modifier,
    )


class FinalModifierTests(unittest.TestCase):
    def test_actual_source_identity_addition_nested_scope_and_overflow(self):
        state = NativeFinalModifier(901, 1)
        invocation = EffectInvocation(
            411428, 1, 7, -7, (1, 0, 0), native_trigger_context={"uid": 901}
        )
        with final_modifier_source(source(state)):
            self.assertTrue(update_triggering_final(invocation, 50))
            with final_modifier_source(source(family=400)):
                self.assertFalse(update_triggering_final(invocation, 50))
            self.assertTrue(update_triggering_final(invocation, 50))
        self.assertEqual(state.value, 100)
        with self.assertRaisesRegex(ValueError, "live native"):
            update_triggering_final(invocation, 1)
        state.value = (1 << 31) - 1
        state.add(50)
        self.assertEqual(state.value, -(1 << 31) + 49)

    def test_registry_inheritance_includes_specialized_native_runners(self):
        # Full original eVi registry probe: these derive eXt/eXs as well.
        for family in (917, 1083, 1084):
            with self.subTest(family=family):
                modifier = NativeFinalModifier(901, family)
                invocation = EffectInvocation(
                    411428, 1, 7, -7, (1, 0, 0), native_trigger_context={"uid": 901}
                )
                with final_modifier_source(source(modifier, family)):
                    self.assertTrue(update_triggering_final(invocation, 23))
                self.assertEqual(modifier.value, 23)
        with self.assertRaisesRegex(ValueError, "faq"):
            NativeFinalModifier(901, 48).validate()

    def test_life_steal_inherits_native_faq_accumulator(self):
        # eVi action24 -> eXv extends eXs implements faq; SX inherited.
        modifier = NativeFinalModifier(901, 24)
        modifier.validate()
        self.assertEqual(modifier.add(17), 17)

    def test_compatible_source_without_accumulator_rejects_not_silently_ignored(self):
        invocation = EffectInvocation(
            411428, 1, 7, -7, (1, 0, 0), native_trigger_context={"uid": 901}
        )
        with final_modifier_source(source()):
            with self.assertRaisesRegex(ValueError, "exact native faq"):
                update_triggering_final(invocation, 50)
        self.assertFalse(
            update_triggering_final(EffectInvocation(411428, 1, 7, -7, (1, 0, 0)), 50)
        )

    def test_handler_parameter_and_native_application_without_actor_bonus(self):
        fight = SimpleNamespace(
            id=100,
            phase="active",
            actors={7: object(), -7: object()},
            owned_stat_effects={},
        )
        packets = []
        handler = NativeFinalModifierHandler(
            fight,
            packets,
            action_id=200,
            allocate_uid=lambda: 902,
            context=lambda *a: StatExecutionContext(True, True, None, False, b"", None),
        )
        modifier = NativeFinalModifier(901, 1)
        invocation = EffectInvocation(
            411428, 1, 7, -7, (1, 0, 0), native_trigger_context={"uid": 901}
        )
        effect = {
            "effect_class": 1093,
            "parameters": [50.0, 0.0],
            "native_effect_flags": [],
        }
        with final_modifier_source(source(modifier)):
            self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual(modifier.value, 50)
        self.assertEqual(packets[0][0], 13497)
        self.assertFalse(fight.owned_stat_effects)
        self.assertEqual(set(fight.actors), {7, -7})

    def test_modifier_accepts_verified_area_pv_without_actor_statistics_or_qf(self):
        fight = SimpleNamespace(
            id=100, phase="active", actors={7: object()}, owned_stat_effects={}
        )
        packets = []
        handler = NativeFinalModifierHandler(
            fight,
            packets,
            action_id=200,
            allocate_uid=lambda: 902,
            context=lambda *a: StatExecutionContext(True, True, None, False, b"", None),
        )
        modifier = NativeFinalModifier(901, 1)
        invocation = EffectInvocation(
            411428, 1, 7, 81, (1, 0, 0), native_trigger_context={"uid": 901}
        )
        effect = {
            "effect_class": 1093,
            "parameters": [50.0, 0.0],
            "native_effect_flags": [],
        }
        with patch(
            "wakfu_server.combat_state_managers.registered_area_pv",
            return_value=SimpleNamespace(id=81, native_running_effect_manager=False),
        ), final_modifier_source(source(modifier)):
            self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual(modifier.value, 50)
        self.assertEqual(set(fight.actors), {7})
        self.assertEqual(fight.owned_stat_effects, {})

        with patch(
            "wakfu_server.combat_state_managers.registered_area_pv", return_value=None
        ), self.assertRaisesRegex(ValueError, "owned native PVs"):
            handler(effect, {}, invocation)

    def test_damage_modifier_applies_before_native_rounding_and_obeys_mode(self):
        context = dict(
            critical=False,
            front=True,
            indirect=False,
            ignore_resistance_cap=False,
            melee=True,
            single_target=True,
            area=False,
            berserk=False,
            additional_final=50,
        )
        self.assertEqual(
            damage_amount(
                10,
                1,
                {},
                {},
                coefficient_mask=3,
                rng=lambda: 0,
                arithmetic_context=context,
            ),
            15,
        )
        self.assertEqual(
            damage_amount(
                10,
                1,
                {},
                {},
                coefficient_mask=0,
                rng=lambda: 0,
                arithmetic_context=context,
            ),
            10,
        )
        self.assertEqual(
            healing_amount(
                10,
                1,
                {},
                {},
                coefficient_mask=3,
                rng=lambda: 0,
                critical=False,
                single_target=True,
                area=False,
                melee=True,
                ranged=False,
                berserk=False,
                additional_mastery=0,
                additional_final=50,
            ),
            15,
        )
