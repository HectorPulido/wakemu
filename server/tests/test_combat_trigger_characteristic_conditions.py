"""Native eJy/eJA/eJz actor selectors use the shared eII relationships."""
import unittest
from dataclasses import replace

from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class TriggerCharacteristicConditionTests(unittest.TestCase):
    def test_rift_regeneration_criteria_with_proven_null_trigger_are_false(self):
        # Actual retained913 criteria317510/327470/327473 from Rift fight601.
        # External1037 carries no triggering Qe; native eJy.d returns -1.
        criteria = (
            'GetCharac("HP", "triggeringCaster") >= 5 and '
            'GetCharacMax("HP", "target") < 30000',
            'GetCharac("HP", "triggeringCaster") >= 5 and '
            'GetCharacMax("HP", "target") >= 30000 and '
            'GetCharacMax("HP", "target") < 300000',
            'GetCharac("HP", "triggeringCaster") >= 5 and '
            'GetCharacMax("HP", "target") >= 300000',
        )
        for hp in (100, 50000, 500000):
            context = ConditionContext(
                {
                    "target": ConditionActor(
                        characteristics={"HP": hp}, characteristic_maxima={"HP": hp}
                    )
                },
                triggering_effect_present=False,
                null_actor_aliases=frozenset(("triggeringcaster", "triggeringtarget")),
            )
            with self.subTest(hp=hp):
                self.assertEqual(
                    [evaluate_condition(criterion, context) for criterion in criteria],
                    [False, False, False],
                )
                for name in ("GetCharac", "GetCharacteristic"):
                    for selector in ("triggeringCaster", "triggeringTarget"):
                        self.assertTrue(
                            evaluate_condition(
                                f'{name}("HP", "{selector}") == -1', context
                            )
                        )
                # A real source remains selected and retains each HP tier gate.
                context = replace(
                    context,
                    actors={
                        **context.actors,
                        "triggeringcaster": ConditionActor(characteristics={"HP": 5}),
                    },
                    null_actor_aliases=frozenset(("triggeringtarget",)),
                    triggering_effect_present=True,
                )
                self.assertEqual(
                    [evaluate_condition(criterion, context) for criterion in criteria],
                    [hp < 30000, 30000 <= hp < 300000, hp >= 300000],
                )

    def test_reads_exact_trigger_actor_instead_of_running_caster(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(characteristics={"HP": 99}),
                "triggeringtarget": ConditionActor(
                    characteristics={"HP": 25}, characteristic_maxima={"HP": 100}
                ),
                "triggeringcaster": ConditionActor(
                    characteristics={"HP": 60}, characteristic_maxima={"HP": 120}
                ),
                "castercontroller": ConditionActor(
                    characteristics={"HP": 80}, characteristic_maxima={"HP": 100}
                ),
            }
        )
        self.assertTrue(
            evaluate_condition(
                'GetCharac("HP", "triggeringTarget") == 25 and '
                'GetCharacMax("HP", "triggeringCaster") == 120 and '
                'GetCharacInPct("HP", "casterController") == 80',
                context,
            )
        )
        self.assertFalse(
            evaluate_condition(
                'GetCharac("HP", "triggeringTarget") == GetCharac("HP", "caster")',
                context,
            )
        )

    def test_missing_relationship_and_unknown_selector_remain_rejected(self):
        context = ConditionContext(
            {"caster": ConditionActor(characteristics={"HP": 99})}
        )
        for selector in ("triggeringTarget", "invented"):
            with self.subTest(selector=selector):
                with self.assertRaises(UnknownCondition):
                    evaluate_condition(f'GetCharac("HP", "{selector}") > 0', context)
