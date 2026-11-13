"""Exercise state-lesson turn boundaries and real native spell dispatch."""
import random
import struct
import unittest
from unittest.mock import patch

import test_combat_spell_transaction as fixture_module
from wakfu_server.achievements import rii_states_contract
from wakfu_server.combat_casting_eligibility import native_casting_distance
from wakfu_server.combat_qi_fight import move_registered_actor
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.spells import encode_deck


class StateLessonNativeCastTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        # This focused native-dispatch test loads large live catalogs. Close
        # its cached pool so the standalone test process exits on completion.
        from wakfu_server import native_catalog

        if native_catalog._database.cache_info().currsize:
            native_catalog._database().close()
            native_catalog._database.cache_clear()

    def test_captured_casts_then_turn_reactions(self):
        fixture = fixture_module.SpellTransactionTests()
        character, monster, fight = fixture.native_server_fixture(
            3, 15, native_qi=True, target_ref=5466, target_level=1, target_distance=2
        )
        fight.rii_states_lesson_contract = {"owner": 7, "target": -7, "hits": 0}
        # This spell fixture uses map 1134, not the map 1388 LOS authority.
        with patch.object(rii_states_contract, "_marker_los", return_value=True):
            rii_states_contract.initialize(fight, [], action_id=1)
        target = fight.actors[-7]
        free = [
            tuple(cell)
            for cell in fight.walkable
            if cell[2] == target.position[2] and tuple(cell) != target.position
        ]
        far = next(
            cell
            for cell in free
            if native_casting_distance(cell[:2], target.position[:2]) >= 6
        )
        near = next(
            cell
            for cell in free
            if native_casting_distance(cell[:2], target.position[:2]) == 1
        )
        for expected, color in ((1, "green"), (2, "red")):
            move_registered_actor(
                fight, fight.actors[7], tuple(fight.rii_states_lesson_contract[color])
            )
            result = prepare_server_spell(
                struct.pack(">qqiih", 7, 7967, *fight.actors[-7].position),
                character,
                {-7: monster},
                fight,
                3,
                encode_deck([]),
                action_id=expected + 1,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=random.Random(1),
            )
            fight = result.fight
            self.assertEqual(fight.rii_states_lesson_contract["hits"], expected)
            self.assertEqual(fight.actors[-7].hp, 100 - expected * 25)
            if expected == 1:
                self.assertEqual(
                    fight.rii_states_lesson_contract["visible_state"], 8016
                )
                self.assertIn(12613, [opcode for opcode, _ in result.packets])
        move_registered_actor(fight, fight.actors[7], near)
        fight.end_turn(3, 7, fight.actors[7].turn_count)
        self.assertEqual(
            (fight.actors[-7].hp, fight.rii_states_lesson_contract["hits"]), (25, 3)
        )
        fight._advance()
        move_registered_actor(fight, fight.actors[7], far)
        fight.end_turn(3, 7, fight.actors[7].turn_count)
        self.assertEqual(
            (fight.actors[-7].hp, fight.rii_states_lesson_contract["hits"]), (0, 4)
        )
        self.assertEqual(fight.phase, "finished")


if __name__ == "__main__":
    unittest.main()
