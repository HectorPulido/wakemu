"""Native eNu/eII selector regression from Viktoria spell 4944."""
import unittest

from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class MonsterBreedTriggerPredicateTests(unittest.TestCase):
    def test_native_trigger_and_controller_selectors_read_selected_actor(self):
        for selector in ("triggeringTarget", "triggeringCaster", "casterController"):
            with self.subTest(selector=selector):
                context = ConditionContext(
                    {
                        "caster": ConditionActor(breed_id=1),
                        "target": ConditionActor(breed_id=2),
                        selector.lower(): ConditionActor(breed_id=3732),
                    },
                    triggering_effect_present=True,
                )
                self.assertTrue(
                    evaluate_condition(f'IsBreedId("{selector}", 3732)', context)
                )
                self.assertFalse(
                    evaluate_condition(f'IsBreedId("{selector}", 5235)', context)
                )

    def test_proven_absent_trigger_returns_false(self):
        for selector in ("triggeringTarget", "triggeringCaster"):
            with self.subTest(selector=selector):
                context = ConditionContext({}, triggering_effect_present=False)
                self.assertFalse(
                    evaluate_condition(f'IsBreedId("{selector}", 3732)', context)
                )
                self.assertTrue(
                    evaluate_condition(f'not IsBreedId("{selector}", 3732)', context)
                )

    def test_unknown_trigger_or_controller_remains_unknown(self):
        for selector in ("triggeringTarget", "triggeringCaster", "casterController"):
            for present in (None, True):
                with self.subTest(selector=selector, present=present):
                    with self.assertRaises(UnknownCondition):
                        evaluate_condition(
                            f'IsBreedId("{selector}", 3732)',
                            ConditionContext({}, triggering_effect_present=present),
                        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                'IsBreedId("casterController", 3732)',
                ConditionContext({}, triggering_effect_present=False),
            )

    def test_selected_actor_unknown_breed_remains_unknown(self):
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                'IsBreedId("triggeringTarget", 3732)',
                ConditionContext({"triggeringtarget": ConditionActor()}),
            )

    def test_registered_area_or_explicit_null_has_no_breed(self):
        self.assertFalse(
            evaluate_condition(
                'IsBreedId("triggeringTarget", 3732)',
                ConditionContext(
                    {"triggeringtarget": ConditionActor(is_native_fighter=False)}
                ),
            )
        )
        self.assertFalse(
            evaluate_condition(
                'IsBreedId("triggeringTarget", 3732)',
                ConditionContext(
                    {}, null_actor_aliases=frozenset({"triggeringtarget"})
                ),
            )
        )

    def test_old_literals_short_conversion_and_validation_remain(self):
        context = ConditionContext({"target": ConditionActor(breed_id=1)})
        self.assertTrue(evaluate_condition('IsBreedId("target", 65537)', context))
        for criterion in (
            'IsBreedId(3732, "target")',
            'IsBreedId("unknown", 3732)',
            'True or IsBreedId("triggeringTarget", "3732")',
        ):
            with self.subTest(criterion=criterion), self.assertRaises(UnknownCondition):
                evaluate_condition(criterion, context)


if __name__ == "__main__":
    unittest.main()
