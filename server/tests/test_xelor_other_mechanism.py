"""Remanence changes actual owned mechanism replacement, without fake summons."""
import unittest
import test_xelor_runtime_pipeline as helpers


class XelorOtherMechanismRuntimeTests(unittest.TestCase):
    def test_remanence_keeps_two_owned_hydrands_instead_of_replacing_first(self):
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_los import authoritative_visible
        from tools.class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_summon_spellbook import actor_action_book

        helper = helpers.XelorRuntimePipelineTests()
        counts = {}
        for enabled in (False, True):
            data = helper.fixture(passives=(7190,) if enabled else (), actives=(766,))
            born = []
            for index in range(2):
                character, monster, fight, deck, rng = data
                _, adapter = server_runtime(
                    character,
                    {-7: monster},
                    deck,
                    action_id=10 + index,
                    critical=False,
                    rng=rng,
                )
                selection = eligible_cast_targets(
                    fight,
                    character,
                    deck,
                    (7 << 32) | 766,
                    adapter=adapter,
                    actor_id=7,
                    line_of_sight=lambda a, b, p: authoritative_visible(1134, a, b, p),
                    limit=256,
                    maximum_eligible=16,
                )
                self.assertTrue(selection["eligible"], selection)
                previous = set(fight.actors)
                tx = helper.cast(
                    data, 766, selection["eligible"][0]["target"], action_id=10 + index
                )
                added = [a for k, a in tx.fight.actors.items() if k not in previous]
                self.assertEqual(len(added), 1)
                self.assertEqual(actor_action_book(added[0])["profile"], 3790)
                born.append(added[0].id)
                data = helper.adopt(data, tx.fight)
                if index == 0:
                    data = helper.next_owned_turn(data)
                    self.assertGreater(data[2].actors[born[0]].hp, 0)
            living = {
                k for k in born if k in data[2].actors and data[2].actors[k].hp > 0
            }
            counts[enabled] = living
            self.assertIn(born[-1], living)
            self.assertEqual(len(living), 2 if enabled else 1, (enabled, born, living))
        self.assertEqual((len(counts[False]), len(counts[True])), (1, 2))
