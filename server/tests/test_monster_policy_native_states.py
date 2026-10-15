"""Regression tests for native initial-state policy serialization."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_policy_native_states import (
    native_initial_state_triples,
    validate_initial_state_triples,
)
from wakfu_server.combat.combat_summon_initial_states import initial_state_plan


class MonsterPolicyNativeStateTests(unittest.TestCase):
    def test_native_flat_order_level_and_flags_survive_serialization(self):
        raw = [5619, 1, 0, 7337, -1, 1, 7998, 1, 1]
        result = native_initial_state_triples(
            {"raw_native": {"cle": raw}, "initial_state_triples": raw}
        )
        self.assertEqual(result, raw)
        self.assertIsNot(result, raw)
        plan = initial_state_plan(result, 110)
        self.assertEqual(
            [(p.state_id, p.level, p.native_rBq) for p in plan],
            [(5619, 1, True), (7337, 110, False), (7998, 1, False)],
        )

    def test_nested_report_triples_cannot_be_published(self):
        for value in ([[5619, 1, 0]], [[5619, 1, 0], [7337, 1, 1], [7998, 1, 1]]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_initial_state_triples(value)

    def test_rejects_disagreement_and_invalid_short_values(self):
        with self.assertRaises(ValueError):
            native_initial_state_triples(
                {"raw_native": {"cle": [1, 1, 0]}, "initial_state_triples": [1, 2, 0]}
            )
        for value in ([1, 1], [True, 1, 0], [32768, 1, 0]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_initial_state_triples(value)
