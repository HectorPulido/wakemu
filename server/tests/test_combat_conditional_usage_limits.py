import unittest
from unittest.mock import patch

from wakfu_server.combat.combat_conditions import UnknownCondition
from wakfu_server.combat.combat_spell_usage import limits


class ConditionalUsageLimitTests(unittest.TestCase):
    def resolve(self, selected, alternatives):
        row = {
            "maximum_level": 200,
            "limits": [1, 2, 0, 0],
            "conditional": [
                {"criteria": name, "limits": values} for name, values in alternatives
            ],
        }

        def evaluate(name, context):
            value = selected[name]
            if value is None:
                raise UnknownCondition("Missing source")
            return value

        with patch(
            "wakfu_server.combat.combat_spell_usage.native_limits",
            return_value={"10": row},
        ), patch(
            "wakfu_server.combat.combat_spell_usage.evaluate_condition",
            side_effect=evaluate,
        ):
            return limits(10, 20, object())

    def test_matching_baseline_and_distinct_table_require_native_order(self):
        with self.assertRaises(UnknownCondition):
            self.resolve(
                {"a": True, "b": True}, [("a", [1, 2, 0, 0]), ("b", [3, 4, 0, 0])]
            )

    def test_equal_matching_tables_are_unambiguous(self):
        self.assertEqual(
            self.resolve(
                {"a": True, "b": True}, [("a", [1, 2, 0, 0]), ("b", [1, 2, 0, 0])]
            ),
            dict(per_target=1, per_turn=2, interval=0),
        )

    def test_unknown_baseline_is_irrelevant_without_distinct_match(self):
        self.assertEqual(
            self.resolve(
                {"a": None, "b": False}, [("a", [1, 2, 0, 0]), ("b", [3, 4, 0, 0])]
            )["per_target"],
            1,
        )
        with self.assertRaises(UnknownCondition):
            self.resolve(
                {"a": None, "b": True}, [("a", [1, 2, 0, 0]), ("b", [3, 4, 0, 0])]
            )

    def test_unknown_distinct_table_always_rejects(self):
        with self.assertRaises(UnknownCondition):
            self.resolve({"a": None}, [("a", [3, 4, 0, 0])])
