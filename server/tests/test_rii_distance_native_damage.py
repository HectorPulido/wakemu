"""The real damage handler applies the reconstructed distance constraint."""
import unittest
from dataclasses import replace

import test_combat_damage_handler as damage_fixture


class NativeDistanceDamageTests(unittest.TestCase):
    def setUp(self):
        self.fixture = damage_fixture.DamageHandlerTests()
        self.fixture.setUp()
        self.fight = self.fixture.fight
        self.fight.rii_distance_lesson_contract = {"owner": 7, "target": -7, "hits": 0}
        self.fight.actors[7].position = (0, 0, 0)
        target = self.fight.actors[-7]
        target.effect_stats.update({97: 0, 92: 0})
        target.effect_maxima.update({92: 0})
        self.fight.actors[7].effect_stats[100] = 0

    def test_correct_zones_advance_and_finish_in_same_turn(self):
        invocation = replace(self.fixture.invocation, reference=361204)
        for index, position in enumerate((1, 3, 2, 4), 1):
            self.fight.actors[-7].position = (position, 0, 0)
            self.assertTrue(self.fixture.handler(self.fixture.effect, {}, invocation))
            self.assertEqual(self.fight.actors[-7].hp, 100 - 25 * index)
        self.assertEqual(self.fight.rii_distance_lesson_contract["hits"], 4)
        self.assertEqual(self.fight.phase, "finished")

    def test_wrong_zone_does_not_damage(self):
        self.fight.actors[-7].position = (3, 0, 0)
        invocation = replace(self.fixture.invocation, reference=361204)
        self.fixture.handler(self.fixture.effect, {}, invocation)
        self.assertEqual(self.fight.actors[-7].hp, 100)
        self.assertEqual(self.fight.rii_distance_lesson_contract["hits"], 0)


if __name__ == "__main__":
    unittest.main()
