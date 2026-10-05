import unittest, struct
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
import test_combat_runtime_messages as runtime_tests


class TableTurnTests(unittest.TestCase):
    def test_native_numeric_context_not_personal_turn(self):
        self.assertTrue(
            evaluate_condition(
                "GetFightCurrentTableTurn() == 0",
                ConditionContext({}, fight_current_table_turn=0),
            )
        )
        self.assertTrue(
            evaluate_condition(
                "GetFightCurrentTableTurn() > 1",
                ConditionContext({}, fight_current_table_turn=2),
            )
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetFightCurrentTableTurn() == 0", ConditionContext({}))

    def test_runtime_cycle_only_updates_on_round_packet(self):
        fight, wire = runtime_tests.RuntimeMessageTests().state()
        self.assertEqual(fight.native_table_turn, 0)
        wire.turn_started()
        self.assertEqual(fight.native_table_turn, 1)
        wire.end_turn(1, 100, 1)
        self.assertEqual(fight.native_table_turn, 1)
        wire.acknowledge_turn(struct.pack(">i", 1))
        self.assertEqual(fight.native_table_turn, 1)
        wire.end_server_turn(-200, 2)
        # Authority prepares next round behind existing ACK barrier; casting is blocked.
        self.assertEqual(fight.native_table_turn, 2)
        wire.acknowledge_turn(struct.pack(">i", 2))
        self.assertEqual(fight.native_table_turn, 2)
