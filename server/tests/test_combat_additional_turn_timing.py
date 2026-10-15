import unittest
from types import SimpleNamespace as NS

from wakfu_server.combat_native_timing_context import native_state_timeline


def timing_fight(
    *,
    order=(7, 7, -7),
    base=(7, -7),
    turn_index=0,
    current_id=7,
    hp=None,
    turn_count=2,
    timeline_round=1,
    resolution_depth=0,
):
    hp = hp or {7: 20, -7: 20}
    actors = {
        identity: NS(id=identity, hp=value, turn_count=turn_count)
        for identity, value in hp.items()
    }
    return NS(
        phase="active",
        current=actors[current_id],
        actors=actors,
        order=list(order),
        native_base_turn_order=None if base is None else list(base),
        native_timeline_round=timeline_round,
        turn_index=turn_index,
        _resolution_depth=resolution_depth,
        native_summon_registrations={},
    )


class AdditionalTurnTimingTests(unittest.TestCase):
    def test_family666_duplicate_in_current_cycle_is_a_valid_clock(self):
        # NativeAdditionalTurnHandler snapshots [7, -7] before it inserts 7.
        fight = timing_fight()
        clock = native_state_timeline(fight, -7)
        self.assertEqual(
            (clock.round_number, clock.current_actor_id, clock.clock_actor_index),
            (1, 7, 2),
        )

    def test_duplicate_without_saved_base_cycle_is_rejected(self):
        fight = timing_fight(base=None)
        with self.assertRaisesRegex(
            ValueError, "Inconsistent eligible fixed actor timeline"
        ):
            native_state_timeline(fight, -7)

    def test_malformed_base_duplicate_foreign_and_missing_live_member_are_rejected(
        self,
    ):
        cases = (
            ("duplicate base", (7, 7, -7), (7, 7, -7), {7: 20, -7: 20}),
            ("foreign order member", (7, 7, 99), (7, -7), {7: 20, -7: 20}),
            ("missing live member", (7, 7), (7, -7), {7: 20, -7: 20}),
        )
        for label, order, base, hp in cases:
            with self.subTest(label=label):
                fight = timing_fight(order=order, base=base, hp=hp)
                with self.assertRaisesRegex(
                    ValueError, "Inconsistent eligible fixed actor timeline"
                ):
                    native_state_timeline(fight, 7)

    def test_rotated_order_keeps_native_first_occurrence_clock_index(self):
        fight = timing_fight(
            order=(-7, 7, -7), base=(7, -7), turn_index=1, current_id=7
        )
        clock = native_state_timeline(fight, -7)
        self.assertEqual(clock.clock_actor_index, 0)
        self.assertEqual(clock.current_actor_index, 1)

    def test_extra_activation_does_not_advance_round_and_invalid_rounds_reject(self):
        fight = timing_fight(turn_count=3, timeline_round=1)
        self.assertEqual(native_state_timeline(fight, 7).round_number, 1)

        # Restoring the saved cycle removes the duplicate but does not advance
        # the native cycle clock; activation count and cycle count are distinct.
        fight.order = list(fight.native_base_turn_order)
        fight.turn_index = 0
        self.assertEqual(native_state_timeline(fight, 7).round_number, 1)

        for invalid_round in (0, 32768, None):
            with self.subTest(round=invalid_round):
                fight.native_timeline_round = invalid_round
                with self.assertRaisesRegex(ValueError, "native timeline round"):
                    native_state_timeline(fight, 7)

    def test_deferred_inactive_member_rules_and_missing_clock_guard_remain(self):
        fight = timing_fight(
            order=(7, 7),
            base=(7, -7),
            hp={7: 20, -7: 0},
            resolution_depth=1,
        )
        clock = native_state_timeline(fight, 7)
        self.assertEqual(clock.current_actor_id, 7)
        with self.assertRaisesRegex(ValueError, "Missing state clock actor"):
            native_state_timeline(fight, -7)


if __name__ == "__main__":
    unittest.main()
