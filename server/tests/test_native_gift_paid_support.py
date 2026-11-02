"""Native gift support requires real ally recipients, costs and injury."""
import unittest

import test_native_monster_form_and_support_producers as support


class NativeGiftPaidSupportTests(unittest.TestCase):
    def test_both_native_gifts_pay_for_other_ally_healing_and_enemy_damage(self):
        fixture = support.NativeMonsterFormAndSupportProducerTests()
        for reference in (2201, 2224):
            with self.subTest(reference=reference):
                scene = fixture._scene(reference, 30)
                runtime = scene[0]
                initial = runtime.fight.actors[-8].hp
                fixture._cast(scene, 4780, -8)
                injured = runtime.fight.actors[-8].hp
                self.assertGreater(injured, 0)
                self.assertLess(injured, initial)
                fixture._turn(scene, -7)
                before_ap = runtime.fight.actors[-7].ap
                before_enemy = runtime.fight.actors[7].hp
                transaction, packets = fixture._cast(scene, 3140, None)
                self.assertEqual(transaction.plan["costs"]["ap"], 5)
                self.assertEqual(runtime.fight.actors[-7].ap, before_ap - 5)
                self.assertGreater(runtime.fight.actors[-8].hp, injured)
                self.assertLessEqual(runtime.fight.actors[-8].hp, initial)
                self.assertLess(runtime.fight.actors[7].hp, before_enemy)
                self.assertTrue(packets)
