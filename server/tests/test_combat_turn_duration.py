import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_turn_duration import (
    duration_add_previous,
    turn_duration_policy,
    current_turn_duration,
    NativeTurnDurationHandler,
    remove_turn_duration,
)


class TurnDurationPolicyTests(unittest.TestCase):
    def test_exact_native_marker_parameters(self):
        for parameters, expected in (
            ([], False),
            ([0], False),
            ([1], True),
            ([2], False),
            ([1, 1], False),
        ):
            self.assertEqual(duration_add_previous(parameters), expected)
        with self.assertRaises(ValueError):
            duration_add_previous([True])

    def test_explicit_keep_add_and_first_fighter_policy(self):
        self.assertEqual(turn_duration_policy(30000, None, add_previous=True), 30000)
        self.assertEqual(turn_duration_policy(30000, 20000, add_previous=False), 20000)
        self.assertEqual(turn_duration_policy(30000, 20000, add_previous=True), 50000)
        with self.assertRaises(ValueError):
            turn_duration_policy(30000, 2**63 - 1, add_previous=True)

    def test_actual_qf_owner_selection_and_recovery_are_once_per_turn(self):
        first, second = SimpleNamespace(id=7), SimpleNamespace(id=8)
        row = dict(
            effect_class=668, family="eWL", native_turn_duration_add_previous=True
        )
        fight = SimpleNamespace(
            current=first, turn_id=1, turn_index=0, owned_stat_effects={}
        )
        self.assertEqual(current_turn_duration(fight, 20000), 20000)
        fight.current, fight.turn_id, fight.turn_index = second, 2, 1
        fight.owned_stat_effects = {12: row}
        with patch(
            "wakfu_server.combat_retained_runtime.native_retained_condition_effects",
            return_value=((44, 668, 12),),
        ) as actual_qf:
            self.assertEqual(current_turn_duration(fight, 30000), 50000)
            self.assertEqual(current_turn_duration(fight, 30000), 50000)
            actual_qf.assert_called_once_with(fight, 8)
        fight.turn_id, fight.turn_index = 3, 0
        with patch(
            "wakfu_server.combat_retained_runtime.native_retained_condition_effects",
            return_value=((44, 668, 12),),
        ):
            self.assertEqual(current_turn_duration(fight, 30000), 30000)

    def test_another_manager_marker_does_not_change_current_duration(self):
        fight = SimpleNamespace(
            current=SimpleNamespace(id=7),
            turn_id=1,
            turn_index=0,
            owned_stat_effects={12: dict(effect_class=668, family="eWL")},
        )
        with patch(
            "wakfu_server.combat_retained_runtime.native_retained_condition_effects",
            return_value=(),
        ):
            self.assertEqual(current_turn_duration(fight, 30000), 30000)

    def test_native_handler_retains_marker_and_removal_does_not_touch_clock(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        actor = SimpleNamespace(id=7)
        fight = SimpleNamespace(id=1, actors={7: actor}, owned_stat_effects={})
        initialize_global_pv_collections(fight, (7,))
        packets = []
        handler = NativeTurnDurationHandler(
            fight,
            packets,
            allocate_uid=lambda: 1,
            action_id=2,
            context=lambda e, i: StatExecutionContext(True, True, None, True, b""),
            authority=lambda f, a: SimpleNamespace(targeting={"is_eGj": True}),
            rng=lambda: 0.5,
        )
        invocation = EffectInvocation(
            22,
            1,
            7,
            7,
            (0, 0, 0),
            native_context_hex="0800100020ffffffffffffffffff0128013000380040004800",
        )
        self.assertTrue(
            handler(
                dict(effect_class=668, parameters=[1, 0], target_masks=[[]] * 7),
                {},
                invocation,
            )
        )
        self.assertTrue(
            fight.owned_stat_effects[1]["native_turn_duration_add_previous"]
        )
        self.assertFalse(hasattr(fight, "native_turn_duration_policy"))
        self.assertEqual(packets[0][0], 12613)
        remove_turn_duration(
            SimpleNamespace(fight=fight, packets=packets, action_id=2), 1
        )
        self.assertEqual(fight.owned_stat_effects, {})
        self.assertEqual(packets[-1][0], 13560)
