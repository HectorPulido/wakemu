"""Actual Wild Push births, two-tree cap and matched baseline seed controls."""
import os
import unittest
import test_sadida_semantic_qualification as semantic


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaWildPushSemanticsTests(unittest.TestCase):
    def test_8150_direct_tree_births_stop_at_two_then_leave_a_real_seed(self):
        from wakfu_server.combat_summon_spellbook import actor_action_book
        from wakfu_server.combat_summon import fresh_summon_slot_owned

        helper = semantic.SadidaSemanticQualificationTests()
        observations = {}
        cells = ((-7, -7, -1), (-9, -8, -1), (-9, -6, -1))
        for name, passives in (("baseline", (7053,)), ("8150", (8150, 7053))):
            data = helper.fixture_at_distance(2, passives=passives)
            initial_resources = data[2].actors[7].ap, data[2].actors[7].mp
            observations[name] = []
            for index, cell in enumerate(cells):
                tx, _ = helper.cast_with_trace(
                    data, 8137, target=cell, action_id=60 + index
                )
                data = (*data[:2], tx.fight, *data[3:])
                self.assertTrue(any(tx.outcomes))
                trees = [
                    actor
                    for actor in tx.fight.actors.values()
                    if getattr(actor, "native_summon_source", None)
                    and actor.hp > 0
                    and actor_action_book(actor)["profile"] == 5577
                ]
                areas = list(tx.fight.native_effect_areas.values())
                counts = {
                    reference: sum(row["reference"] == reference for row in areas)
                    for reference in (1835, 1850, 1855)
                }
                self.assertEqual(
                    (tx.fight.actors[7].ap, tx.fight.actors[7].mp), initial_resources
                )
                for tree in trees:
                    self.assertGreater(tree.hp, 0)
                    self.assertEqual(tree.hp, tree.max_hp)
                    self.assertIn(
                        (8217, 1),
                        [
                            (state.reference, state.level)
                            for state in tree.state_ledger.entries
                        ],
                    )
                    self.assertTrue(fresh_summon_slot_owned(tx.fight, tree))
                    self.assertEqual(actor_action_book(tree)["actions"], [])
                self.assertTrue(all(row.get("owner_id") == 7 for row in areas))
                observations[name].append((len(trees), counts))
        self.assertEqual([row[0] for row in observations["baseline"]], [0, 0, 0])
        self.assertEqual([row[1][1835] for row in observations["baseline"]], [1, 2, 3])
        self.assertEqual([row[1][1855] for row in observations["baseline"]], [1, 2, 3])
        self.assertEqual([row[1][1850] for row in observations["baseline"]], [0, 0, 0])
        self.assertEqual([row[0] for row in observations["8150"]], [1, 2, 2])
        self.assertEqual([row[1][1850] for row in observations["8150"]], [1, 2, 2])
        self.assertEqual([row[1][1835] for row in observations["8150"]], [0, 0, 1])
        self.assertEqual([row[1][1855] for row in observations["8150"]], [0, 0, 1])
