"""Resurrection inserts a fighter without collapsing a current extra turn."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_resurrection import complete_resurrection


class ResurrectionOccurrenceTests(unittest.TestCase):
    def fixture(self, position):
        target = SimpleNamespace(id=52, hp=10)
        current = SimpleNamespace(id=7)
        fight = SimpleNamespace(
            id=123,
            current=current,
            order=[7, -200, 7, 65],
            turn_index=2,
            native_base_turn_order=[7, -200, 65],
            native_timeline_round=4,
            native_timeline_snapshot_source="owned-tc-sy-v1",
            native_timeline_member_counters={"7": 4, "-200": 3, "65": 3},
            native_timeline_removed=[
                dict(actor_id=52, position=position),
                dict(actor_id=99, position=1),
            ],
        )
        fight._refill_turn_resources = lambda actor: None
        fight._event = lambda *args, **kwargs: None
        return fight, target, dict(removed=dict(position=position)), []

    def complete(self, fight, target, prepared, packets):
        # This unit isolates cursor insertion; global life transitions have
        # their separate real-runtime suite. Use actual native SY insertion.
        with patch(
            "wakfu_server.combat_global_pv_collections.set_global_fighter_status"
        ):
            with patch(
                "wakfu_server.combat_native_death_status.apply_native_fighter_state_transition"
            ):
                return complete_resurrection(
                    fight, target, prepared, action_id=8, packets=packets
                )

    def test_insertion_before_current_preserves_actual_duplicate_and_sy_counter(self):
        fight, target, prepared, packets = self.fixture(0)
        self.assertTrue(self.complete(fight, target, prepared, packets))
        self.assertEqual(fight.order, [52, 7, -200, 7, 65])
        self.assertEqual(fight.turn_index, 3)
        self.assertEqual(fight.order[fight.turn_index], 7)
        self.assertEqual(
            fight.native_timeline_member_counters, {"7": 4, "-200": 3, "65": 3, "52": 5}
        )
        self.assertEqual(fight.native_base_turn_order, (52, 7, -200, 65))
        self.assertEqual(fight.native_timeline_removed, [dict(actor_id=99, position=1)])
        self.assertEqual([opcode for opcode, _ in packets], [12727])

    def test_insertion_after_current_keeps_occurrence_and_saved_slot_clamping(self):
        for position in (3, 99):
            with self.subTest(position=position):
                fight, target, prepared, packets = self.fixture(position)
                self.assertTrue(self.complete(fight, target, prepared, packets))
                expected = [7, -200, 7, 65]
                expected.insert(min(position, len(expected)), 52)
                self.assertEqual(fight.order, expected)
                self.assertEqual(fight.turn_index, 2)
                self.assertEqual(fight.native_timeline_member_counters["52"], 4)
                self.assertEqual(fight.native_timeline_member_counters["7"], 4)
                self.assertEqual(fight.native_base_turn_order, (7, -200, 65, 52))
