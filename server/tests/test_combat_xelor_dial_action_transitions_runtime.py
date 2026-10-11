"""Context-dependent owned Xelor actions after actual dial creation."""
import unittest
import test_xelor_runtime_pipeline as helpers


class XelorDialActionTransitionRuntimeTests(unittest.TestCase):
    def test_owned_registered_dial_allows_actual_752_occupied_target(self):
        helper = helpers.XelorRuntimePipelineTests()
        data = helper.fixture(actives=(752,))
        first = helper.cast(data, 5345, (-11, -7, -1))
        data = helper.adopt(data, first.fight)
        self.assertIn(6759, helper.states(data[2].actors[7]))
        data = helper.next_owned_turn(data)
        before = data[2].actors[-7].hp
        tx = helper.cast(data, 752, data[2].actors[-7].position, action_id=20)
        self.assertTrue(any(tx.outcomes))
        self.assertLess(tx.fight.actors[-7].hp, before)

    def test_hour_action_requires_actual_owned_free_hour_then_commits(self):
        helper = helpers.XelorRuntimePipelineTests()
        data = helper.fixture(actives=(5344,))
        first = helper.cast(data, 5345, (-11, -7, -1))
        data = helper.adopt(data, first.fight)
        fight = data[2]
        owner = fight.actors[7].position
        occupied = {a.position for a in fight.actors.values() if a.hp > 0}
        candidates = sorted(
            {
                tuple(r["cell"])
                for r in fight.native_effect_areas.values()
                if r.get("owner_id") == 7
                and 1546 <= r["reference"] <= 1557
                and tuple(r["cell"]) not in occupied
                and 1
                <= abs(r["cell"][0] - owner[0]) + abs(r["cell"][1] - owner[1])
                <= 2
            }
        )
        self.assertTrue(candidates)
        rejected = []
        for cell in candidates:
            try:
                tx = helper.cast(data, 5344, cell, action_id=20)
            except ValueError as error:
                if "eligibility rejected" not in str(error):
                    raise
                rejected.append((cell, str(error)))
                continue
            self.assertTrue(any(tx.outcomes))
            from wakfu_server.combat_summon_spellbook import actor_action_book

            born = [
                actor
                for identity, actor in tx.fight.actors.items()
                if identity not in fight.actors
            ]
            self.assertEqual(len(born), 1)
            self.assertEqual(actor_action_book(born[0])["profile"], 5444)
            self.assertEqual(born[0].position, cell)
            self.assertEqual(actor_action_book(born[0])["actions"], [])
            self.assertEqual(helper.states(born[0])[7784], 200)
            entry = next(s for s in born[0].state_ledger.entries if s.reference == 7784)
            self.assertEqual((entry.target_id, entry.duration), (born[0].id, -1))
            from wakfu_server.combat_qi_fight import current_registry

            registry = current_registry(tx.fight)
            self.assertEqual(
                registry.slots[born[0].native_obstacle_id]["identity"],
                ["actor", born[0].id],
            )
            self.assertEqual(tx.fight.actors[7].position, owner)
            old_id = born[0].id
            continued = helper.next_owned_turn(helper.adopt(data, tx.fight))
            now = continued[2]
            occupied_now = {a.position for a in now.actors.values() if a.hp > 0}
            fresh_cells = sorted(
                {
                    tuple(r["cell"])
                    for r in now.native_effect_areas.values()
                    if r.get("owner_id") == 7
                    and 1546 <= r["reference"] <= 1557
                    and tuple(r["cell"]) not in occupied_now
                    and 1
                    <= abs(r["cell"][0] - now.actors[7].position[0])
                    + abs(r["cell"][1] - now.actors[7].position[1])
                    <= 2
                }
            )
            self.assertTrue(fresh_cells)
            replacement = helper.cast(continued, 5344, fresh_cells[0], action_id=40)
            self.assertEqual(replacement.fight.actors[old_id].hp, 0)
            fresh = [
                a
                for identity, a in replacement.fight.actors.items()
                if identity not in now.actors
            ]
            self.assertEqual(len(fresh), 1)
            self.assertEqual(actor_action_book(fresh[0])["profile"], 5444)
            self.assertIn(7784, helper.states(fresh[0]))
            current_registry(replacement.fight)
            return
        self.fail(("No lawful owned hour action", candidates, rejected))
