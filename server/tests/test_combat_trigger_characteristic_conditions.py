"""Native eJy/eJA/eJz actor selectors use the shared eII relationships."""
import unittest

from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class TriggerCharacteristicConditionTests(unittest.TestCase):
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
