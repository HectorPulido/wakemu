"""Doll actions assert native damage/heal/control/retirement, beyond receipts."""
import os
import unittest
import test_sadida_doll_actions_pipeline as births
import test_sadida_super_voodoll_actions_pipeline as actions


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaDollActionSemanticsTests(unittest.TestCase):
    def test_enabled_doll_actions_change_their_authored_targets(self):
        from wakfu_server.combat_hp_raw import set_hp_raw_current

        birth = births.SadidaDollActionsPipelineTests()
        helper = actions.SadidaSuperVoodollActionsPipelineTests()
        cases = (
            (925, 3747, 5024),
            (925, 3747, 8138),
            (921, 3748, 5023),
            (918, 3749, 5021),
            (932, 3750, 5026),
            (930, 3751, 5025),
            (934, 3751, 5356),
        )
        for spell, profile, action in cases:
            with self.subTest(spell=spell, profile=profile, action=action):
                data, actor_id = birth.born(
                    spell,
                    profile,
                    passives=(912,) if action == 8138 else (),
                    seed_cell=(-7, -7, -1)
                    if action in (5021, 5356)
                    else (-5, -7, -1)
                    if action == 5024
                    else (-6, -7, -1),
                )
                fight = data[2]
                if action == 5021:
                    set_hp_raw_current(fight.actors[7], fight.actors[7].hp // 2)
                target_id = (
                    actor_id
                    if action in (5024, 8138)
                    else 7
                    if action in (5021, 5356)
                    else -7
                )
                target = fight.actors[target_id]
                hp, position = target.hp, target.position
                enemy_hp = fight.actors[-7].hp
                tx = helper.summon_cast(data, actor_id, action, target.position)
                after = tx.fight.actors[target_id]
                if action == 5023:
                    self.assertLess(after.hp, hp)
                if action == 5024:
                    self.assertLess(tx.fight.actors[-7].hp, enemy_hp)
                if action in (5024, 8138):
                    self.assertEqual(tx.fight.actors[actor_id].hp, 0)
                    self.assertEqual(tx.fight.actors[actor_id].native_obstacle_id, -1)
                if action == 5021:
                    self.assertGreater(after.hp, hp)
                if action == 5026:
                    # Native8199 has zero duration; its children install poison
                    # and MP-loss carriers rather than retaining8199 itself.
                    self.assertNotIn(
                        8199, {s.reference for s in after.state_ledger.entries}
                    )
                    self.assertIn(
                        3617, {s.reference for s in after.state_ledger.entries}
                    )
                    self.assertIn(
                        3309, {s.reference for s in after.state_ledger.entries}
                    )
                    self.assertIn(
                        8259, {s.reference for s in after.state_ledger.entries}
                    )
                if action == 5025:
                    self.assertNotEqual(after.position, position)
                if action == 5356:
                    self.assertIn(
                        3681, {s.reference for s in after.state_ledger.entries}
                    )
                    self.assertIn(
                        3682,
                        {
                            s.reference
                            for s in tx.fight.actors[actor_id].state_ledger.entries
                        },
                    )
