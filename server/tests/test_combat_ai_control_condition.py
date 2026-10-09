import unittest
import json
from pathlib import Path
from wakfu_server.combat_summon_conditions import SummonBreedRow, surrounding_own_summon
from wakfu_server.combat_conditions import (
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)


class NativeAIControlConditionTests(unittest.TestCase):
    def test_original_neighborhood_geometry_and_owner_breed_filters(self):
        path = (
            Path(__file__).resolve().parents[2]
            / "server/test-fixtures/combat/ai-control-neighborhood.json"
        )
        for row in json.loads(path.read_text())["rows"]:
            summon = SummonBreedRow(8, 3794, 7, (row["x"], row["y"], 99))
            for mode in ("MOORE", "VON_NEUMANN"):
                self.assertEqual(
                    surrounding_own_summon(
                        [summon],
                        caller_id=7,
                        center=(row["center"], row["center"], 0),
                        breed=3794,
                        mode=mode,
                    ),
                    row[mode],
                )
        self.assertFalse(
            surrounding_own_summon(
                [SummonBreedRow(8, 3794, 9, (0, 0, 0))], caller_id=7, center=(0, 0, 0)
            )
        )
        self.assertFalse(
            surrounding_own_summon(
                [SummonBreedRow(7, 3794, 7, (0, 0, 0))], caller_id=7, center=(0, 0, 0)
            )
        )
        self.assertFalse(
            surrounding_own_summon(
                [SummonBreedRow(8, 3794, 7, (0, 0, 0))],
                caller_id=7,
                center=(0, 0, 0),
                breed=1,
            )
        )

    def test_surrounding_shared_signatures(self):
        calls = []
        context = ConditionContext(
            {}, surrounding_own_summon_query=lambda *args: calls.append(args) or True
        )
        self.assertTrue(
            evaluate_condition(
                'HasSurroundingCellWithOwnSummon("target",3794,"MOORE")', context
            )
        )
        self.assertEqual(calls[-1], ("target", 3794, "MOORE"))
        self.assertTrue(
            evaluate_condition(
                'HasSurroundingCellWithOwnSummon("caster","MOORE")', context
            )
        )
        self.assertEqual(calls[-1], ("caster", -1, "MOORE"))
        self.assertTrue(
            evaluate_condition(
                'HasSurroundingCellWithOwnSummon("target",3794)', context
            )
        )
        self.assertEqual(calls[-1], ("target", 3794, "VON_NEUMANN"))

    def test_explicit_native_boolean_and_one_string_signature(self):
        calls = []
        context = ConditionContext(
            {}, controlled_by_ai_query=lambda value: calls.append(value) or False
        )
        self.assertFalse(evaluate_condition('IsControlledByAI("caster")', context))
        self.assertEqual(calls, ["caster"])
        self.assertTrue(evaluate_condition('not IsControlledByAI("target")', context))
        self.assertTrue(
            evaluate_condition(
                'IsControlledByAI("caster")',
                ConditionContext({}, controlled_by_ai_query=lambda value: True),
            )
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsControlledByAI()", context)
        with self.assertRaises(UnknownCondition):
            evaluate_condition('IsControlledByAI("caster")', ConditionContext({}))
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                'IsControlledByAI("caster")',
                ConditionContext({}, controlled_by_ai_query=lambda value: 1),
            )


if __name__ == "__main__":
    unittest.main()
