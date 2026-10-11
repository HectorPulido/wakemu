"""Real held-barrel armor is cleared only by a qualifying direct back hit."""
import os
import random
import struct
import unittest
import test_combat_pandawa_carry_death_runtime as shared


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class PandawaFermentationRuntimeTests(unittest.TestCase):
    fixture = shared.PandawaCarryDeathRuntimeTests.fixture
    reach = shared.PandawaCarryDeathRuntimeTests.reach

    def test_actual_back_hit_clears_held_barrel_armor_but_side_hit_does_not(self):
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_ordinary_authority import native_facing
        from tools.class_spell_eligible_targets import eligible_cast_targets

        for back in (False, True):
            with self.subTest(back=back):
                fight, characters, decks = self.fixture(
                    carrier_level=200,
                    carried_level=200,
                    pandawa_passives=(8597,),
                    attacker_spell=4780,
                    attacker_level=1,
                )
                fight = self.reach(fight, characters, decks, 7)

                def cast(current, spell, target, action):
                    uid = granted_spells(current, 7)[spell]["uid"]
                    return prepare_server_spell(
                        struct.pack(">qqiih", 7, uid, *target),
                        characters[7],
                        {},
                        current,
                        3,
                        decks[7],
                        action_id=action,
                        line_of_sight=lambda *args: True,
                        critical=False,
                        rng=random.Random(0),
                        player_characters=characters,
                        deck_blobs=decks,
                    ).fight

                _, adapter = server_runtime(
                    characters[7],
                    {},
                    decks[7],
                    action_id=10,
                    critical=False,
                    rng=random.Random(0),
                    player_characters=characters,
                    deck_blobs=decks,
                )
                selected = eligible_cast_targets(
                    fight,
                    characters[7],
                    decks[7],
                    granted_spells(fight, 7)[4718]["uid"],
                    adapter=adapter,
                    line_of_sight=lambda *args: True,
                    actor_id=7,
                    limit=128,
                    maximum_eligible=16,
                )
                carried = None
                for row in selected["eligible"]:
                    born = cast(fight, 4718, row["target"], 10)
                    barrel = next(
                        a
                        for a in born.actors.values()
                        if getattr(a, "native_summon_source", None)
                    )
                    try:
                        candidate = cast(born, 6847, barrel.position, 11)
                    except ValueError:
                        continue
                    if (
                        native_facing(candidate.actors[9], candidate.actors[7])
                        == "BACK"
                    ) == back:
                        carried = candidate
                        break
                self.assertIsNotNone(carried, selected)
                fight = self.reach(carried, characters, decks, 9)
                self.assertEqual(
                    native_facing(fight.actors[9], fight.actors[7]) == "BACK", back
                )
                self.assertIn(
                    6776, {e.reference for e in fight.actors[7].state_ledger.entries}
                )
                before = fight.actors[7].effect_stats.get(97, 0)
                self.assertGreater(before, 0)
                hit = prepare_server_spell(
                    struct.pack(
                        ">qqiih", 9, (9 << 32) | 4780, *fight.actors[7].position
                    ),
                    characters[9],
                    {},
                    fight,
                    5,
                    decks[9],
                    action_id=12,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    rng=random.Random(0),
                    player_characters=characters,
                    deck_blobs=decks,
                )
                armor = hit.fight.actors[7].effect_stats.get(97, 0)
                if back:
                    self.assertEqual(armor, 0)
                else:
                    self.assertGreater(armor, 0)
                    self.assertLess(armor, before)
