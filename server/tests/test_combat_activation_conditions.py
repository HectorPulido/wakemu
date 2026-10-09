import unittest
from types import SimpleNamespace
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat.combat_activation_conditions import (
    NativeActivationSnapshot,
    current_activation,
)
from wakfu_server.combat.combat_active_spell import active_spell_scope
from wakfu_server import native_catalog


class ActivationPredicateTests(unittest.TestCase):
    def test_activation_spell_id_and_container_are_independent(self):
        snapshot = NativeActivationSnapshot(True, spell_id=42, container_present=False)
        context = ConditionContext({}, activation_query=snapshot.evaluate)
        self.assertTrue(evaluate_condition("IsActivatedBySpell(4294967338)", context))
        self.assertFalse(evaluate_condition("IsActivatedBySpell()", context))
        self.assertFalse(evaluate_condition("IsActivatedBySpell(43)", context))

    def test_stasis_flag_overrides_element(self):
        for stasis, expected in ((False, 4), (True, 6)):
            snapshot = NativeActivationSnapshot(
                True, element=4, is_spell_activation=True, stasis=stasis
            )
            context = ConditionContext({}, activation_query=snapshot.evaluate)
            self.assertTrue(
                evaluate_condition(f"IsActivatedByElement({expected})", context)
            )
            self.assertFalse(
                evaluate_condition(
                    f"IsActivatedByElement({6 if expected == 4 else 4})", context
                )
            )

    def test_unknown_activation_rejects_but_actual_absence_is_false(self):
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsActivatedBySpell()", ConditionContext({}))
        absent = ConditionContext(
            {}, activation_query=NativeActivationSnapshot(False).evaluate
        )
        self.assertFalse(evaluate_condition("IsActivatedBySpell()", absent))
        self.assertFalse(evaluate_condition("IsActivatedByElement(4)", absent))
        incomplete = ConditionContext(
            {}, activation_query=NativeActivationSnapshot(True, element=4).evaluate
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsActivatedByElement(4)", incomplete)

    def test_bool_native_signatures(self):
        context = ConditionContext(
            {}, activation_query=NativeActivationSnapshot(False).evaluate
        )
        for expression in (
            "IsActivatedByElement()",
            "IsActivatedBySpell(1,2)",
            'IsActivatedBySpell("caster")',
            "IsTriggeringEffectCritical(1)",
            "IsTriggeringEffectBlocked(1)",
            "IsActivatedBySpell() == 0",
        ):
            with self.subTest(expression=expression), self.assertRaises(
                UnknownCondition
            ):
                evaluate_condition(expression, context)

    def test_trigger_variant_bit_and_actual_status(self):
        for variant in (0, 1, 2, 3, -1):
            context = ConditionContext(
                {},
                triggering_effect_present=True,
                triggering_effect_definition_present=True,
                triggering_effect_variant=variant,
            )
            self.assertEqual(
                evaluate_condition("IsTriggeringEffectCritical()", context),
                bool(variant & 1),
            )
        for status in (-1, 0, 7, 8):
            context = ConditionContext(
                {},
                triggering_effect_present=True,
                triggering_effect_execution_status=status,
            )
            self.assertEqual(
                evaluate_condition("IsTriggeringEffectBlocked()", context), status == 7
            )

    def test_unknown_source_metadata_is_not_false(self):
        context = ConditionContext({}, triggering_effect_present=True)
        for name in ("IsTriggeringEffectCritical()", "IsTriggeringEffectBlocked()"):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(name, context)
            self.assertFalse(
                evaluate_condition(
                    name, ConditionContext({}, triggering_effect_present=False)
                )
            )
        context = ConditionContext(
            {},
            triggering_effect_present=True,
            triggering_effect_definition_present=False,
        )
        self.assertFalse(evaluate_condition("IsTriggeringEffectCritical()", context))

    def test_current_fight_activation_scope_restores_native_container(self):
        fight = SimpleNamespace(
            native_active_spell_id=None, native_active_spell_container=None
        )
        self.assertFalse(current_activation(fight, "IsActivatedBySpell", -1))
        with active_spell_scope(fight, 42, level=10):
            self.assertTrue(current_activation(fight, "IsActivatedBySpell", 42))
            self.assertTrue(current_activation(fight, "IsActivatedBySpell", -1))
            with active_spell_scope(fight, 43, level=20):
                self.assertFalse(current_activation(fight, "IsActivatedBySpell", 42))
            self.assertTrue(current_activation(fight, "IsActivatedBySpell", 42))
        self.assertFalse(current_activation(fight, "IsActivatedBySpell", -1))

    def test_current_activation_uses_bulk_native_metadata(self):
        import json
        from wakfu_server.paths import DATA_ROOT

        rows = json.loads(
            native_catalog.read_text(DATA_ROOT / "native-spell-activation.json")
        )["spells"]
        self.assertEqual(len(rows), 4143)
        selected = [
            next((key, row) for key, row in rows.items() if row["stasis"] is flag)
            for flag in (False, True)
        ]
        fight = SimpleNamespace(
            native_active_spell_id=None, native_active_spell_container=None
        )
        for key, row in selected:
            with active_spell_scope(fight, int(key), level=10):
                expected = 6 if row["stasis"] else row["native_element"]
                self.assertTrue(
                    current_activation(fight, "IsActivatedByElement", expected)
                )
                self.assertFalse(
                    current_activation(fight, "IsActivatedByElement", 12345)
                )

    def test_source_descriptor_propagates_exact_observations(self):
        from wakfu_server.combat_trigger_identifiers import condition_identifiers

        source = dict(
            native_definition_present=True,
            native_definition_variant=1,
            native_execution_blocked=True,
        )
        context = ConditionContext({}, **condition_identifiers(source))
        self.assertTrue(evaluate_condition("IsTriggeringEffectCritical()", context))
        self.assertTrue(evaluate_condition("IsTriggeringEffectBlocked()", context))
        for invalid in (
            dict(native_definition_variant=True),
            dict(native_execution_status=128),
            dict(native_execution_status=0, native_execution_blocked=True),
        ):
            with self.assertRaises(ValueError):
                condition_identifiers(invalid)
