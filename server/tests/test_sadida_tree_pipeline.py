"""A native seed's second actual Semilla cast produces the tree profile."""
import os
import unittest

import test_sadida_grant_pipeline as grants
import test_aniripsa_grant_summon_pipeline as turns


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaTreePipelineTests(unittest.TestCase):
    fixture = grants.SadidaGrantPipelineTests.fixture
    cast = grants.SadidaGrantPipelineTests.cast

    def test_actual_seed_recast_creates_owned_empty_book_tree(self):
        from wakfu_server.combat_summon_spellbook import actor_action_book
        from wakfu_server.combat_summon import fresh_summon_slot_owned
        from wakfu_server.combat_qi_fight import current_registry

        data = self.fixture()
        seeded = self.cast(data, 8137)
        data = (*data[:2], seeded.fight, *data[3:])
        cell = next(
            a["cell"]
            for a in seeded.fight.native_effect_areas.values()
            if a["reference"] == 1835
        )
        tx = self.cast(data, 8137, target=cell, action_id=11)
        trees = [
            a
            for a in tx.fight.actors.values()
            if getattr(a, "native_summon_source", None) and a.hp > 0
        ]
        self.assertEqual(len(trees), 1)
        tree = trees[0]
        self.assertEqual(actor_action_book(tree)["profile"], 5577)
        self.assertEqual(actor_action_book(tree)["actions"], [])
        self.assertIn(8217, {s.reference for s in tree.state_ledger.entries})
        self.assertTrue(fresh_summon_slot_owned(tx.fight, tree))
        current_registry(tx.fight)
