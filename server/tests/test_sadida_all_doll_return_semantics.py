"""Real player-issued Return actions retire each native doll profile cleanly."""
import os
import unittest

import test_sadida_doll_actions_pipeline as births
import test_sadida_super_voodoll_actions_pipeline as actions
from wakfu_server.combat_qi_fight import current_registry


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaAllDollReturnSemanticsTests(unittest.TestCase):
    def test_each_actual_doll_return_retires_only_its_own_qi_identity(self):
        for spell, profile in (
            (925, 3747),
            (921, 3748),
            (918, 3749),
            (932, 3750),
            (930, 3751),
        ):
            with self.subTest(profile=profile):
                data, identity = births.SadidaDollActionsPipelineTests().born(
                    spell, profile, passives=(912,)
                )
                owner_hp = data[2].actors[7].hp
                tx = actions.SadidaSuperVoodollActionsPipelineTests().summon_cast(
                    data, identity, 8138, data[2].actors[identity].position
                )
                doll = tx.fight.actors[identity]
                self.assertEqual(doll.hp, 0)
                self.assertEqual(doll.native_obstacle_id, -1)
                self.assertEqual(tx.fight.actors[7].hp, owner_hp)
                self.assertGreater(tx.fight.actors[-7].hp, 0)
                self.assertFalse(
                    any(
                        row and row["identity"] == ["actor", identity]
                        for row in tx.fight.native_qi_slots
                    )
                )
                for bystander in (7, -7):
                    self.assertTrue(
                        any(
                            row and row["identity"] == ["actor", bystander]
                            for row in tx.fight.native_qi_slots
                        )
                    )
                current_registry(tx.fight)
