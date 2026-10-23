"""Original eNo uses world membership, independently of fight PvP category."""
import json
from pathlib import Path
import unittest
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.native_world_context import battleground_worlds, is_battleground


class BattlegroundConditionTests(unittest.TestCase):
    def test_complete_original_world_export_and_twenty_ordinary_worlds(self):
        from wakfu_server import native_world_context

        path = Path(native_world_context.__file__).with_name(
            "native_world_battlegrounds.json"
        )
        definitions = json.loads(path.read_text())
        self.assertEqual(len(definitions["worlds"]), 720)
        self.assertEqual(len(battleground_worlds()), 7)
        for identity, expected in definitions["worlds"].items():
            self.assertIs(is_battleground(int(identity)), expected)
        ordinary = [
            int(key) for key, value in definitions["worlds"].items() if not value
        ][:20]
        self.assertEqual(len(ordinary), 20)
        self.assertTrue(all(not is_battleground(identity) for identity in ordinary))
        self.assertFalse(is_battleground(1134))
        self.assertFalse(is_battleground((1 << 63) - 1))  # Native mP returns null.

    def test_boolean_numeric_negation_and_constructor_ignored_arguments(self):
        for membership in (False, True):
            context = ConditionContext({}, battleground_query=lambda: membership)
            self.assertIs(evaluate_condition("IsBattleground()", context), membership)
            self.assertIs(
                evaluate_condition("not IsBattleground()", context), not membership
            )
            self.assertIs(
                evaluate_condition("IsBattleground() == 0", context), membership
            )
            self.assertIs(
                evaluate_condition("IsBattleground(123) == -1", context), not membership
            )

    def test_pvp_and_battleground_are_distinct_authorities(self):
        duel = ConditionContext(
            {}, pvp_query=lambda: True, battleground_query=lambda: is_battleground(1134)
        )
        self.assertTrue(evaluate_condition("IsPvp() and not IsBattleground()", duel))
        actual_battleground = next(iter(battleground_worlds()))
        world = ConditionContext(
            {},
            pvp_query=lambda: False,
            battleground_query=lambda: is_battleground(actual_battleground),
        )
        self.assertTrue(evaluate_condition("not IsPvp() and IsBattleground()", world))

    def test_missing_or_incorrect_authority_remains_unknown(self):
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsBattleground()", ConditionContext({}))
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "IsBattleground()", ConditionContext({}, battleground_query=lambda: 0)
            )
        for invalid in (None, True, "1134", 1 << 63):
            with self.subTest(identity=invalid), self.assertRaises(ValueError):
                is_battleground(invalid)


if __name__ == "__main__":
    unittest.main()
