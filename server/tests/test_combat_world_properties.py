import unittest
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)
from wakfu_server.combat_world_properties import has_world_property, registry


class WorldPropertyTests(unittest.TestCase):
    def test_world_and_fight_fallback_are_separate_live_authorities(self):
        actor = ConditionActor(
            world_properties=frozenset({43}), fight_properties=frozenset()
        )
        self.assertTrue(has_world_property(actor, 43))
        self.assertTrue(has_world_property(actor, 43 + 256))
        self.assertFalse(has_world_property(actor, 49))
        identity, row = next(
            (int(k), v) for k, v in registry().items() if v["fight_property"] != -1
        )
        actor = ConditionActor(
            world_properties=frozenset(),
            fight_properties=frozenset({row["fight_property"]}),
        )
        self.assertTrue(has_world_property(actor, identity))
        with self.assertRaises(ValueError):
            has_world_property(ConditionActor(), 43)

    def test_selector_target_only_and_unknown_string_defaults_caster(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(world_properties=frozenset()),
                "target": ConditionActor(world_properties=frozenset({43})),
            }
        )
        self.assertTrue(evaluate_condition('HasWorldProperty(43,"TaRgEt")', context))
        self.assertFalse(evaluate_condition('HasWorldProperty(43,"invalid")', context))
        self.assertFalse(evaluate_condition("HasWorldProperty(49)", context))
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "HasWorldProperty(43)", ConditionContext({"caster": ConditionActor()})
            )
        self.assertFalse(
            evaluate_condition(
                'HasWorldProperty(43,"target")',
                ConditionContext({}, effect_target_absent=True),
            )
        )

    def test_age_requires_complete_ledger_and_exact_elapsed_boundary(self):
        actor = ConditionActor(
            world_properties=frozenset({43}), world_property_since_ms={43: 1000}
        )
        self.assertFalse(has_world_property(actor, 43, duration_seconds=2, now_ms=2999))
        self.assertTrue(has_world_property(actor, 43, duration_seconds=2, now_ms=3000))
        with self.assertRaises(ValueError):
            has_world_property(
                ConditionActor(world_properties=frozenset({43})),
                43,
                duration_seconds=1,
                now_ms=10000,
            )
        context = ConditionContext({"caster": actor}, world_property_now_ms=3000)
        self.assertTrue(evaluate_condition("HasWorldProperty(43,2)", context))
        self.assertFalse(
            has_world_property(
                ConditionActor(world_properties=frozenset()), 43, duration_seconds=2
            )
        )

    def test_malformed_signature_is_rejected(self):
        for expression in (
            "HasWorldProperty()",
            'HasWorldProperty("43")',
            'HasWorldProperty(43,1,"target")',
            "HasWorldProperty(43,True)",
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, ConditionContext({}))
