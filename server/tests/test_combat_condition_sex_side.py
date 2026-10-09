import unittest
from types import SimpleNamespace as N
from dataclasses import replace
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)
from wakfu_server.combat_condition_facing import native_sidestabbed


class SexAndSideConditionTests(unittest.TestCase):
    def test_actual_pc_source_and_detached_summon_constructor_are_distinct(self):
        from wakfu_server.combat_ordinary_authority import ordinary_native_sex
        from wakfu_server.combat_summon_creation import native_fresh_summon_authority

        for value in (0, 1):
            self.assertEqual(ordinary_native_sex({"sex": value}, True), value)
        self.assertIsNone(ordinary_native_sex({}, True))
        self.assertEqual(ordinary_native_sex({}, False), 0)
        for value in (False, True):
            self.assertEqual(ordinary_native_sex({"sex": value}, True), int(value))
            self.assertIs(type(ordinary_native_sex({"sex": value}, True)), int)
        for value in (-1, 2, "Female"):
            with self.assertRaises(ValueError):
                ordinary_native_sex({"sex": value}, True)
        actor = N(id=7, effective_level=20, native_controlled_by_ai=True)
        self.assertEqual(native_fresh_summon_authority(actor, 3789).native_sex, 0)

    def test_sex_exact_native_strings_and_selector_defaults(self):
        actors = dict(
            caster=ConditionActor(is_native_fighter=True, native_sex=0),
            target=ConditionActor(is_native_fighter=True, native_sex=1),
        )
        context = ConditionContext(actors)
        for label, expected in (
            ("Male", 0),
            ("mAlE", 0),
            ("Female", 1),
            ("unknown", 1),
            ("", 1),
        ):
            for selector, sex in (
                (None, 0),
                ("target", 1),
                ("TARGET", 1),
                ("other", 0),
                ("caster", 0),
            ):
                expression = f'IsSex("{label}"' + (
                    ")" if selector is None else f',"{selector}")'
                )
                self.assertEqual(
                    evaluate_condition(expression, context), sex == expected
                )

    def test_sex_null_nonfighter_missingbyte_and_signature_guards(self):
        self.assertFalse(
            evaluate_condition(
                'IsSex("Male","target")',
                ConditionContext({}, null_actor_aliases=frozenset({"target"})),
            )
        )
        self.assertFalse(
            evaluate_condition(
                'IsSex("Female")',
                ConditionContext({"caster": ConditionActor(is_native_fighter=False)}),
            )
        )
        for byte in (None, True, 128, -129):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(
                    'IsSex("Male")',
                    ConditionContext(
                        {
                            "caster": ConditionActor(
                                is_native_fighter=True, native_sex=byte
                            )
                        }
                    ),
                )
        for expression in (
            "True or IsSex()",
            "False and IsSex(1)",
            'IsSex("Male",1)',
            'IsSex("Male","target","caster")',
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, ConditionContext({}))

    def test_side_live_geometry_selector_and_locator_guards(self):
        caster = N(position=(0, 0, 0), direction=1)
        target = N(position=(0, 1, 0), direction=1)
        fight = N(actors={7: caster, -7: target}, native_effect_areas={})
        metadata = ConditionActor(is_native_fighter=True, fight_properties=frozenset())

        def query(selector):
            selected, opposite = (-7, 7) if selector == "target" else (7, -7)
            return native_sidestabbed(fight, selected, opposite, metadata)

        context = ConditionContext({}, sidestabbed_query=query)
        self.assertTrue(evaluate_condition("IsSidestabbed()", context))
        self.assertTrue(evaluate_condition('IsSidestabbed("TARGET")', context))
        target.position = (0, -1, 0)
        self.assertTrue(evaluate_condition('IsSidestabbed("other")', context))
        target.position = (-1, 0, 0)
        self.assertFalse(evaluate_condition("IsSidestabbed()", context))
        hidden = replace(metadata, fight_properties=frozenset({47}))
        self.assertFalse(native_sidestabbed(fight, 7, -7, hidden))
        self.assertFalse(native_sidestabbed(fight, 7, None, metadata))
        for expression in (
            "True or IsSidestabbed(1)",
            'IsSidestabbed("target","caster")',
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, context)
