"""Fresh Sadida fights isolate owned areas, grants, doll books and QI slots."""
import os
import unittest
import test_sadida_doll_actions_pipeline as dolls


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaSecondFightPipelineTests(unittest.TestCase):
    def test_actual_second_fight_does_not_mutate_first_doll_authority(self):
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.combat_summon_spellbook import actor_action_book
        from wakfu_server.combat_spell_grant import granted_spells

        helper = dolls.SadidaDollActionsPipelineTests()
        first, first_id = helper.born(921, 3748)
        before = snapshot(first[2])
        second, second_id = helper.born(930, 3751)
        self.assertEqual(snapshot(first[2]), before)
        self.assertIsNot(first[2], second[2])
        self.assertIsNot(first[2].actors[first_id], second[2].actors[second_id])
        self.assertEqual(actor_action_book(first[2].actors[first_id])["profile"], 3748)
        self.assertEqual(
            actor_action_book(second[2].actors[second_id])["profile"], 3751
        )
        self.assertNotEqual(
            {
                a["reference"]
                for a in actor_action_book(first[2].actors[first_id])["actions"]
            },
            {
                a["reference"]
                for a in actor_action_book(second[2].actors[second_id])["actions"]
            },
        )
        for data, identity in ((first, first_id), (second, second_id)):
            fight = data[2]
            self.assertEqual(
                len(
                    [
                        a
                        for a in fight.actors.values()
                        if getattr(a, "native_summon_source", None) and a.hp > 0
                    ]
                ),
                1,
            )
            self.assertGreaterEqual(fight.actors[identity].native_obstacle_id, 0)
            self.assertIn(8137, granted_spells(fight, 7))
            current_registry(fight)
