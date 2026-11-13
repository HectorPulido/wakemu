"""Exercise the real native damage handler against the isolated lesson rule."""
import unittest
from dataclasses import replace

import test_combat_damage_handler as damage_fixture
from wakfu_server.achievements import rii_element_contract


class NativeElementalDamageTests(unittest.TestCase):
    def setUp(self):
        self.fixture = damage_fixture.DamageHandlerTests()
        self.fixture.setUp()
        self.fight = self.fixture.fight
        self.fight.rii_element_lesson_contract = {
            "owner": 7,
            "target": -7,
            "hits": 0,
            "last_turn": None,
        }
        target = self.fight.actors[-7]
        target.effect_stats.update({28: 0, 29: 0, 30: 0, 31: 0, 97: 0, 92: 0})
        target.effect_minima = {
            28: -2147483648,
            29: -2147483648,
            30: -2147483648,
            31: -2147483648,
        }
        target.effect_maxima.update(
            {28: 2147483647, 29: 2147483647, 30: 2147483647, 31: 2147483647, 92: 0}
        )
        self.fight.actors[7].effect_stats[100] = 0

    def test_four_turns_damage_native_hp_without_premature_victory(self):
        for turn, reference, element in (
            (1, 361189, 2),
            (3, 361190, 4),
            (5, 361191, 3),
            (7, 361192, 5),
        ):
            self.fight.turn_id = turn
            rii_element_contract.begin_turn(self.fight)
            effect = {**self.fixture.effect, "effect_class": element}
            invocation = replace(self.fixture.invocation, reference=reference)
            self.assertTrue(self.fixture.handler(effect, {}, invocation))
            self.assertEqual(self.fight.actors[-7].hp, 100 - 25 * ((turn + 1) // 2))
        self.assertEqual(self.fight.rii_element_lesson_contract["hits"], 4)
        self.assertEqual(self.fight.phase, "finished")

    def test_wrong_element_and_second_hit_in_one_turn_do_not_damage(self):
        rii_element_contract.begin_turn(self.fight)
        wrong = {**self.fixture.effect, "effect_class": 4}
        invocation = replace(self.fixture.invocation, reference=361190)
        self.fixture.handler(wrong, {}, invocation)
        self.assertEqual(self.fight.actors[-7].hp, 100)
        right = {**self.fixture.effect, "effect_class": 2}
        invocation = replace(self.fixture.invocation, reference=361189)
        self.fixture.handler(right, {}, invocation)
        self.fixture.handler(right, {}, invocation)
        self.assertEqual(self.fight.actors[-7].hp, 75)
        self.assertEqual(self.fight.rii_element_lesson_contract["hits"], 1)


if __name__ == "__main__":
    unittest.main()
