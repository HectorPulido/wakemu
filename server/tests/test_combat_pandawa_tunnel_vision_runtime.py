"""Real Drunk Pandawa receives an actual opposing melee attack."""
import os
import random
import struct
import unittest
from unittest.mock import patch
import test_combat_pandawa_carry_death_runtime as shared_fixture


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class PandawaTunnelVisionRuntimeTests(unittest.TestCase):
    fixture = shared_fixture.PandawaCarryDeathRuntimeTests.fixture
    reach = shared_fixture.PandawaCarryDeathRuntimeTests.reach

    def test_tunnel_vision_reduces_actual_melee_received_damage_while_drunk(self):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server import combat_final_modifier

        damage = {}
        for passive in (None, 8596):
            with self.subTest(passive=passive):
                fight, characters, decks = self.fixture(
                    carrier_level=200,
                    carried_level=200,
                    pandawa_passives=() if passive is None else (passive,),
                    attacker_spell=4780,
                )
                fight = self.reach(fight, characters, decks, 7)
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
                fight = self.reach(drunk.fight, characters, decks, 9)
                self.assertIn(
                    3300,
                    {entry.reference for entry in fight.actors[7].state_ledger.entries},
                )
                before = fight.actors[7].hp
                added = []
                original = combat_final_modifier.NativeFinalModifier.add

                def observe(modifier, amount):
                    added.append(amount)
                    return original(modifier, amount)

                with patch.object(
                    combat_final_modifier.NativeFinalModifier, "add", observe
                ):
                    hit = prepare_server_spell(
                        struct.pack(
                            ">qqiih", 9, (9 << 32) | 4780, *fight.actors[7].position
                        ),
                        characters[9],
                        {},
                        fight,
                        5,
                        decks[9],
                        action_id=11,
                        line_of_sight=lambda *args: True,
                        critical=False,
                        rng=random.Random(0),
                        player_characters=characters,
                        deck_blobs=decks,
                    )
                damage[passive] = before - hit.fight.actors[7].hp
                self.assertGreater(damage[passive], 0)
                if passive == 8596:
                    self.assertIn(-20, added)
                else:
                    self.assertNotIn(-20, added)
        self.assertLess(damage[8596], damage[None])

    def test_tunnel_vision_increases_actual_distance_received_damage_while_drunk(self):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server import combat_final_modifier

        damage = {}
        for passive in (None, 8596):
            with self.subTest(passive=passive):
                fight, characters, decks = self.fixture(
                    carrier_level=200,
                    carried_level=200,
                    pandawa_passives=() if passive is None else (passive,),
                    attacker_spell=4780,
                    attacker_distance=3,
                )
                fight = self.reach(fight, characters, decks, 7)
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
                fight = self.reach(drunk.fight, characters, decks, 9)
                self.assertIn(
                    3300,
                    {entry.reference for entry in fight.actors[7].state_ledger.entries},
                )
                before = fight.actors[7].hp
                added = []
                original = combat_final_modifier.NativeFinalModifier.add

                def observe(modifier, amount):
                    added.append(amount)
                    return original(modifier, amount)

                with patch.object(
                    combat_final_modifier.NativeFinalModifier, "add", observe
                ):
                    hit = prepare_server_spell(
                        struct.pack(
                            ">qqiih", 9, (9 << 32) | 4780, *fight.actors[7].position
                        ),
                        characters[9],
                        {},
                        fight,
                        5,
                        decks[9],
                        action_id=11,
                        line_of_sight=lambda *args: True,
                        critical=False,
                        rng=random.Random(0),
                        player_characters=characters,
                        deck_blobs=decks,
                    )
                damage[passive] = before - hit.fight.actors[7].hp
                self.assertGreater(damage[passive], 0)
                if passive == 8596:
                    self.assertIn(20, added)
                else:
                    self.assertNotIn(20, added)
        self.assertGreater(damage[8596], damage[None])
