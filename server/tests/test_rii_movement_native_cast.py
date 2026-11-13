"""Scoped Rii displacement effects run through actual spell dispatch."""
import random
import struct
import unittest

import test_combat_spell_transaction as fixture_module
from wakfu_server.achievements import rii_movement_contract
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.spells import encode_deck


class MovementNativeCastTests(unittest.TestCase):
    def test_qualified_cast_commits_marker_and_preserves_action_validation(self):
        from dataclasses import replace
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_tactical_markers import _marker_packet

        fixture = fixture_module.SpellTransactionTests()
        character, monster, fight = fixture.native_server_fixture(
            3, 15, native_qi=True, target_ref=5466, target_level=1, target_distance=2
        )
        fight.rii_movement_lesson_contract = {"owner": 7, "target": -7, "hits": 0}
        rii_movement_contract.initialize(fight, [], action_id=1)
        self.assertEqual(
            tuple(fight.rii_movement_lesson_contract["marker"]), (-7, -7, -1)
        )
        transaction = prepare_server_spell(
            struct.pack(">qqiih", 7, 7972, *fight.actors[-7].position),
            character,
            {-7: monster},
            fight,
            3,
            encode_deck([]),
            action_id=1,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(1),
        )
        self.assertEqual(transaction.fight.rii_movement_lesson_contract["hits"], 1)
        runtime = RuntimeMessages(fight)
        forged = _marker_packet(fight.id, fight.actors[7].position, 7, 0, True)
        with self.assertRaisesRegex(ValueError, "another combat action"):
            commit_spell_transaction(
                runtime,
                replace(transaction, packets=transaction.packets + (forged,)),
                stats_serializer=lambda *args: b"stats",
            )
        self.assertIs(runtime.fight, fight)
        packets = commit_spell_transaction(
            runtime, transaction, stats_serializer=lambda *args: b"stats"
        )
        self.assertEqual(runtime.fight.rii_movement_lesson_contract["hits"], 1)
        self.assertIn(12226, [opcode for opcode, _ in packets])

    def test_four_owned_native_moves_finish_only_after_swap(self):
        fixture = fixture_module.SpellTransactionTests()
        character, monster, fight = fixture.native_server_fixture(
            3, 15, native_qi=True, target_ref=5466, target_level=1, target_distance=2
        )
        fight.rii_movement_lesson_contract = {"owner": 7, "target": -7, "hits": 0}
        packets = []
        rii_movement_contract.initialize(fight, packets, action_id=1)
        self.assertEqual(fight.actors[7].mp, 0)
        action_id = 2
        for index in range(1, 5):
            marker = tuple(fight.rii_movement_lesson_contract["marker"])
            owner, sack = fight.actors[7], fight.actors[-7]
            if index < 4:
                dx, dy = marker[0] - sack.position[0], marker[1] - sack.position[1]
                x, y, z = sack.position
                plans = (
                    (7973, (x - dx, y - dy, z)),
                    (7972, (x + 2 * dx, y + 2 * dy, z)),
                )
                spell, stand = next(
                    (spell, stand)
                    for spell, stand in plans
                    if stand in fight.walkable
                    and abs(stand[0] - owner.position[0])
                    + abs(stand[1] - owner.position[1])
                    <= 4
                    and rii_movement_contract._native_plan_valid(
                        fight, owner, sack, marker, stand
                    )
                )
                if stand != owner.position:
                    result = prepare_server_spell(
                        struct.pack(">qqiih", 7, 7974, *stand),
                        character,
                        {-7: monster},
                        fight,
                        3,
                        encode_deck([]),
                        action_id=action_id,
                        line_of_sight=lambda *args: True,
                        critical=False,
                        rng=random.Random(1),
                    )
                    fight, action_id = result.fight, action_id + 1
                    self.assertEqual(fight.actors[7].position, stand)
                fight._refill_turn_resources(fight.actors[7])
            else:
                spell = 7975
                self.assertEqual(marker, fight.actors[7].position)
                fight._refill_turn_resources(fight.actors[7])
            result = prepare_server_spell(
                struct.pack(">qqiih", 7, spell, *fight.actors[-7].position),
                character,
                {-7: monster},
                fight,
                3,
                encode_deck([]),
                action_id=action_id,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=random.Random(1),
            )
            fight, action_id = result.fight, action_id + 1
            self.assertEqual(fight.actors[-7].position, marker)
            self.assertEqual(fight.rii_movement_lesson_contract["hits"], index)
            self.assertEqual(fight.phase, "finished" if index == 4 else "active")


if __name__ == "__main__":
    unittest.main()
