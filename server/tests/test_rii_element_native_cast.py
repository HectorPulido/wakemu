"""Full native spell dispatch for the four elemental training turns.

Requires the normal compiled catalogue or WAKFU_COMPILED_CATALOG_BUILD=1.
Turn numbers and resource refills are supplied by this test; no game client is
involved, and original server weakness selection remains reconstructed.
"""
import random
import struct
import unittest

import test_combat_spell_transaction as fixture_module
from wakfu_server.achievements import rii_element_contract
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.spells import encode_deck


class ElementalNativeCastTests(unittest.TestCase):
    def test_four_temporary_native_spells_complete_owned_lesson(self):
        fixture = fixture_module.SpellTransactionTests()
        character, monster, fight = fixture.native_server_fixture(
            3, 15, native_qi=True, target_ref=5466, target_level=1, target_distance=2
        )
        fight.rii_element_lesson_contract = {
            "owner": 7,
            "target": -7,
            "hits": 0,
            "last_turn": None,
        }
        packets = []
        rii_element_contract.initialize(fight, packets, action_id=1)
        self.assertEqual([op for op, _ in packets], [12613] * 4)
        self.assertEqual(len(fight.native_retained_records), 4)
        for index, (turn, spell) in enumerate(
            ((1, 7963), (3, 7964), (5, 7965), (7, 7966)), 1
        ):
            fight.turn_id = turn
            if turn > 1:
                fight._refill_turn_resources(fight.actors[7])
                fight.actors[7].turn_count += 1
                rii_element_contract.begin_turn(fight)
            result = prepare_server_spell(
                struct.pack(">qqiih", 7, spell, *fight.actors[-7].position),
                character,
                {-7: monster},
                fight,
                3,
                encode_deck([]),
                action_id=turn + 1,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=random.Random(1),
            )
            fight = result.fight
            self.assertEqual(fight.actors[-7].hp, 100 - index * 25)
            self.assertEqual(fight.rii_element_lesson_contract["hits"], index)
            self.assertEqual(fight.phase, "finished" if index == 4 else "active")
