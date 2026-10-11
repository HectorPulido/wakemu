"""Actual ally Tipsy conversion and recipient-start healing with Cyanotic."""
import os
import random
import struct
import unittest
import test_combat_pandawa_carry_death_runtime as shared_fixture


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class PandawaAllyHealRuntimeTests(unittest.TestCase):
    fixture = shared_fixture.PandawaCarryDeathRuntimeTests.fixture
    reach = shared_fixture.PandawaCarryDeathRuntimeTests.reach

    def test_cyanotic_heals_actual_injured_ally_at_recipient_start(self):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_grant import granted_spells

        gains = {}
        for passive in (None, 8599):
            with self.subTest(passive=passive):
                fight, characters, decks = self.fixture(
                    carrier_level=200,
                    carried_level=200,
                    injured_ally=True,
                    pandawa_passives=() if passive is None else (passive,),
                )
                fight = self.reach(fight, characters, decks, 7)
                tipsy = prepare_server_spell(
                    struct.pack(
                        ">qqiih",
                        7,
                        granted_spells(fight, 7)[8592]["uid"],
                        *fight.actors[8].position
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
                self.assertIn(
                    6107,
                    {e.reference for e in tipsy.fight.actors[8].state_ledger.entries},
                )
                before = tipsy.fight.actors[8].hp
                advanced = self.reach(tipsy.fight, characters, decks, 8)
                gains[passive] = advanced.actors[8].hp - before
                if passive == 8599:
                    self.assertGreater(gains[passive], 0)
                    self.assertNotIn(
                        9366,
                        {e.reference for e in advanced.actors[8].state_ledger.entries},
                    )
                    self.assertNotIn(
                        6107,
                        {e.reference for e in advanced.actors[8].state_ledger.entries},
                    )
        self.assertEqual(gains[None], 0)
        self.assertGreater(gains[8599], gains[None])
