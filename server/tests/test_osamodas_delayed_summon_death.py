"""Captured Osa summons publish final death before turn close and free their slot."""
import struct
import unittest
from unittest.mock import patch

import test_combat_summon_retirement as retirement_fixture
from wakfu_server.combat_qi_fight import current_registry
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_timeline_snapshot import current_wire_turn
from wakfu_server.combat_summon_creation import register_fresh_summon_obstacle


class OsamodasDelayedSummonDeathTests(unittest.TestCase):
    def test_captured_summon_death_is_delivered_before_turn_close_and_reusable(self):
        fight, owner, _, summon = retirement_fixture.SummonRetirementTests().fight(
            origin="captured"
        )
        self.assertIs(fight.current, owner)
        # The captured summon is an owned timeline actor. Advance the owner so
        # the delayed lethal callback runs while the summon itself ends its turn.
        fight.end_turn(owner.owner_id, owner.id, owner.turn_count)
        self.assertIs(fight.current, summon)
        summon.native_controlled_by_ai = False
        original_slot = summon.native_obstacle_id
        original_position = summon.position
        original_roster = fight.native_captured_rosters[str(owner.id)]
        before_turn = fight.turn_id

        def delayed_kill(candidate, *, actor_id, action_id):
            candidate.apply_effect_damage(
                owner.id, summon.id, candidate.actors[summon.id].hp
            )
            return candidate, []

        runtime = RuntimeMessages(fight, turn_end_provider=delayed_kill)
        packets = runtime.end_turn(
            owner.owner_id,
            summon.id,
            current_wire_turn(fight),
        )

        death_indices = [i for i, (opcode, _) in enumerate(packets) if opcode == 12727]
        close_index = next(
            i for i, (opcode, _) in enumerate(packets) if opcode == 12502
        )
        self.assertEqual(len(death_indices), 1)
        self.assertLess(death_indices[0], close_index)
        death_body = packets[death_indices[0]][1]
        self.assertEqual(
            struct.unpack_from(">qB", death_body, len(death_body) - 9), (summon.id, 2)
        )

        status = fight.native_global_pv_collections["fighter_status"][str(summon.id)]
        self.assertEqual(status, "OUT_OF_PLAY")
        self.assertEqual(summon.native_obstacle_id, -1)
        self.assertIsNone(fight.native_qi_slots[original_slot])
        self.assertEqual(current_registry(fight).ordered_U(*original_position[:2]), ())
        roster = fight.native_captured_rosters[str(owner.id)]
        self.assertEqual(roster["slots"], original_roster["slots"])
        self.assertEqual(roster["available"][0], True)
        self.assertEqual(roster["selected_slot"], original_roster["selected_slot"])

        from wakfu_server.combat_summon_stats import registered_summon_stats

        with patch(
            "wakfu_server.combat_summon_stats.snapshot_characteristics",
            return_value=b"\x00\x00",
        ):
            serialized = registered_summon_stats(summon, fight, 1134)
        self.assertEqual(struct.unpack_from(">b", serialized, 29)[0], -1)

        acknowledged = runtime.acknowledge_turn(struct.pack(">i", before_turn))
        self.assertFalse(any(opcode == 12727 for opcode, _ in acknowledged))

        replacement = type(summon)(902, 0, original_position, 20, 1, 1, 0, 10)
        replacement.physical_radius = 0
        register_fresh_summon_obstacle(fight, replacement)
        self.assertEqual(replacement.native_obstacle_id, original_slot)


if __name__ == "__main__":
    unittest.main()
