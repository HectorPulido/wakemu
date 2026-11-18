"""Actual area-PC absence differs from an unknown fighter characteristic."""
import unittest

import test_registered_area_team_condition as area_fixture
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation


class RegisteredAreaCharacteristicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        area_fixture.RegisteredAreaTeamConditionTests.setUpClass()

    def setUp(self):
        fixture = area_fixture.RegisteredAreaTeamConditionTests()
        fixture.setUp()
        self.fight, self.adapter = fixture.fight, fixture.adapter
        self.fight.actors[7].effect_stats[35] = self.fight.actors[7].initiative

    def test_native159872_reads_absent_area_init_without_disabling_fighter_comparison(
        self,
    ):
        from wakfu_server.spell_audit import catalog

        effect = catalog()["effects"]["159872"]
        self.assertEqual(effect["effect_class"], 1093)
        invocation = EffectInvocation(159872, 46, 7, 901, (2, 3, 0))
        context = self.adapter.condition(self.fight, {}, effect, invocation)
        self.assertTrue(
            evaluate_condition('GetCharacteristic("INIT","target") == -1', context)
        )
        self.assertTrue(
            evaluate_condition('GetCharacMax("INIT","target") == -1', context)
        )
        self.assertTrue(
            evaluate_condition('GetCharacPct("INIT","target") == -1', context)
        )
        self.assertFalse(evaluate_condition(effect["criteria"], context))
        target = self.fight.actors[-7]
        target.initiative = self.fight.actors[7].initiative + 10
        target.effect_stats[35] = target.initiative
        fighter = EffectInvocation(159872, 46, 7, -7, target.position)
        self.assertTrue(
            evaluate_condition(
                effect["criteria"],
                self.adapter.condition(self.fight, {}, effect, fighter),
            )
        )
        del target.effect_stats[35]
        with self.assertRaisesRegex(
            UnknownCondition, "Missing native characteristic: INIT"
        ):
            evaluate_condition(
                effect["criteria"],
                self.adapter.condition(self.fight, {}, effect, fighter),
            )

    def test_present_native_area_hp_and_maxima_keep_their_actual_values(self):
        import test_combat_fake_fighter_area as constructor_fixture
        from wakfu_server.combat_area_characteristic_conditions import (
            area_characteristic_snapshot,
        )

        fixture = constructor_fixture.NativeFakeFighterAreaTests()
        fight, creator, _, _ = fixture.create()
        creator.fake_fighter_hp_enabled = True
        creator(
            {"effect_class": 339},
            {"parameters": [1688, 200]},
            EffectInvocation(323843, 200, 7, None, (2, 3, 0)),
        )
        current, maxima, absent = area_characteristic_snapshot(fight, 901)
        self.assertGreater(current["HP"], 0)
        self.assertGreater(maxima["HP"], 0)
        context = ConditionContext(
            {
                "target": ConditionActor(
                    characteristics=current,
                    characteristic_maxima=maxima,
                    total_hp_absent_characteristics=absent,
                )
            }
        )
        self.assertTrue(
            evaluate_condition(
                'GetCharac("HP","target") == ' + str(current["HP"]), context
            )
        )
        self.assertTrue(
            evaluate_condition(
                'GetCharacMax("HP","target") == ' + str(maxima["HP"]), context
            )
        )
        self.assertTrue(
            evaluate_condition('GetCharacteristic("INIT","target") == -1', context)
        )
        self.assertTrue(
            evaluate_condition('GetTotalHpInPercent("target") > 0', context)
        )
