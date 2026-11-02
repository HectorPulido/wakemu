"""Paid native Wrath selects its child ring around the self-centered group."""
from collections import Counter
import unittest

from test_sram_castigo_recipient_pipeline import SramCastigoRecipientPipelineTests


class IopWrathRecipientPipelineTests(unittest.TestCase):
    def test_paid_wrath_hits_ring_allies_and_enemies_once_but_not_center(self):
        helper = SramCastigoRecipientPipelineTests()
        for critical in (False, True):
            with self.subTest(critical=critical):
                fixture = helper.fixture(ring=True, breed=8, spells=(4779,))
                runtime = fixture[2]
                before = {
                    identity: actor.hp
                    for identity, actor in runtime.fight.actors.items()
                }
                ap = runtime.fight.actors[7].ap
                wp = runtime.fight.actors[7].effect_stats[4]
                tx, packets = helper.cast(
                    fixture, 4779, critical=critical, aim_at_caster=True
                )
                self.assertEqual(tx.plan["costs"]["ap"], 6)
                self.assertEqual(runtime.fight.actors[7].ap, ap - 6)
                self.assertEqual(runtime.fight.actors[7].effect_stats[4], wp - 1)
                self.assertEqual(runtime.fight.actors[7].hp, before[7])
                for identity in (-7, -8, -9, 6, -10):
                    self.assertLess(runtime.fight.actors[identity].hp, before[identity])
                self.assertEqual(
                    helper.damaged_recipients(packets),
                    Counter({-7: 1, -8: 1, -9: 1, 6: 1, -10: 1}),
                )
                self.assertEqual(
                    helper.damage_references(packets),
                    [151815 if critical else 150190] * 5,
                )
