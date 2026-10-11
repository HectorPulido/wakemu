"""Native Drunk stat and carried-actor range branches from legal actions."""
import os
import unittest
import test_combat_pandawa_runtime as fixture_module


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class PandawaModePassiveRuntimeTests(unittest.TestCase):
    fixture = fixture_module.PandawaRuntimeTests.fixture
    cast = fixture_module.PandawaRuntimeTests.cast

    def test_bambutella_drunk_gains_dodge_and_loses_tackle_only_with_passive(self):
        deltas = {}
        for passive in (None, 5148):
            with self.subTest(passive=passive):
                fixture = self.fixture(() if passive is None else (passive,))
                actor = fixture[2].actors[7]
                before = {stat: actor.effect_stats[stat] for stat in (7, 8)}
                applied = self.cast(fixture, 8592, target=actor.position)
                deltas[passive] = {
                    stat: applied.fight.actors[7].effect_stats[stat] - before[stat]
                    for stat in (7, 8)
                }
                self.assertIn(
                    3300,
                    {
                        entry.reference
                        for entry in applied.fight.actors[7].state_ledger.entries
                    },
                )
        self.assertEqual(deltas[None], {7: 0, 8: 0})
        # Group393743 scales the bearer level by200%; child175[0,1]
        # uses that calculated level as its flat gain (400 at level200).
        self.assertEqual(deltas[5148][8], 2 * fixture[0]["level"])
        # Native TACKLE has signed-int bounds; negative values are retained
        # independently of the full level-scaled dodge gain.
        self.assertLessEqual(deltas[5148][7], 0)

    def test_tipsy_passive_reduces_real_drunk_throw_range(self):
        ranges = {}
        for passive in (None, 6846):
            with self.subTest(passive=passive):
                fixture = self.fixture(() if passive is None else (passive,))
                drunk = self.cast(fixture, 8592, target=fixture[2].actors[7].position)
                fixture = (*fixture[:2], drunk.fight, *fixture[3:])
                carried = self.cast(
                    fixture, 6847, target=fixture[2].actors[-7].position, action_id=3
                )
                fixture = (*fixture[:2], carried.fight, *fixture[3:])
                self.assertIn(
                    3300,
                    {
                        entry.reference
                        for entry in fixture[2].actors[7].state_ledger.entries
                    },
                )
                thrown = self.cast(fixture, 6848, action_id=4)
                ranges[passive] = thrown.plan["native_casting_flags"]["maximum"]
                self.assertNotEqual(
                    thrown.fight.actors[7].position, thrown.fight.actors[-7].position
                )
        self.assertLess(ranges[6846], ranges[None])

    def test_bambutella_loses_real_aptitude_tackle_in_positive_build(self):
        import random
        import struct
        import test_combat_pandawa_carry_death_runtime as shared
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_grant import granted_spells

        results = {}
        for passive in (None, 5148):
            with self.subTest(passive=passive):
                helper = shared.PandawaCarryDeathRuntimeTests()
                fight, characters, decks = helper.fixture(
                    carrier_level=200,
                    carried_level=200,
                    pandawa_passives=() if passive is None else (passive,),
                    pandawa_aptitudes=[(18, 20)],
                )
                fight = helper.reach(fight, characters, decks, 7)
                before = fight.actors[7].effect_stats[7]
                self.assertEqual(before, 120)  # Native aptitude18:6 tackle per point.
                drunk = prepare_server_spell(
                    struct.pack(
                        ">qqiih",
                        7,
                        granted_spells(fight, 7)[8592]["uid"],
                        *fight.actors[7].position
                    ),
                    characters[7],
                    {},
                    fight,
                    3,
                    decks[7],
                    action_id=10,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    rng=random.Random(0),
                    player_characters=characters,
                    deck_blobs=decks,
                )
                results[passive] = drunk.fight.actors[7].effect_stats[7]
        self.assertEqual(results[None], 120)
        self.assertEqual(
            results[5148], -280
        )  # Native TACKLE has signed-int bounds:120−400.
