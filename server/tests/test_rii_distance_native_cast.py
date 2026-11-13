"""Exercise real server spell dispatch with the owned distance grant."""
import random
import struct
import unittest

import test_combat_spell_transaction as fixture_module
from wakfu_server.achievements import rii_distance_contract
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.spells import encode_deck


class DistanceNativeCastTests(unittest.TestCase):
    def test_first_granted_cast_qualifies_in_melee_zone(self):
        fixture = fixture_module.SpellTransactionTests()
        character, monster, fight = fixture.native_server_fixture(
            3, 15, native_qi=True, target_ref=5466, target_level=1, target_distance=2
        )
        fight.rii_distance_lesson_contract = {"owner": 7, "target": -7, "hits": 0}
        packets = []
        rii_distance_contract.initialize(fight, packets, action_id=1)
        self.assertEqual([op for op, _ in packets], [12613, 349])
        self.assertEqual(len(fight.native_retained_records), 1)
        result = prepare_server_spell(
            struct.pack(">qqiih", 7, 7967, *fight.actors[-7].position),
            character,
            {-7: monster},
            fight,
            3,
            encode_deck([]),
            action_id=2,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(1),
        )
        self.assertEqual(result.fight.actors[-7].hp, 75)
        self.assertEqual(result.fight.rii_distance_lesson_contract["hits"], 1)
        self.assertEqual(result.fight.phase, "active")
        from wakfu_server.combat_qi_fight import move_registered_actor

        for index, distance in enumerate((3, 1, 4), 2):
            fight = result.fight
            destination = (-8 + distance, -7, -1)
            self.assertIn(destination, fight.walkable)
            move_registered_actor(fight, fight.actors[-7], destination)
            # Keep the encounter in the same turn; the guide does not require
            # ending turns between distance changes.
            result = prepare_server_spell(
                struct.pack(">qqiih", 7, 7967, *destination),
                character,
                {-7: monster},
                fight,
                3,
                encode_deck([]),
                action_id=index + 1,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=random.Random(1),
            )
            self.assertEqual(result.fight.actors[-7].hp, 100 - index * 25)
            self.assertEqual(result.fight.rii_distance_lesson_contract["hits"], index)
        self.assertEqual(result.fight.phase, "finished")


if __name__ == "__main__":
    unittest.main()
