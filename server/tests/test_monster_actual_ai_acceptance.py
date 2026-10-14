import ast
import json
from pathlib import Path
import sys
from unittest.mock import create_autospec

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import monster_actual_ai_acceptance as acceptance
from monster_actual_ai_acceptance import attach_scene_diagnostics
from wakfu_server.combat_tactical_ai import validate_response

import unittest
from monster_actual_ai_acceptance import execute_replanned


class ActualReplanningTests(unittest.TestCase):
    def test_replans_after_buff_and_never_executes_stale_second_action(self):
        actions = []

        def choose():
            if not actions:
                return dict(type="cast", spellId=1), dict(actions=[1, 999])
            return dict(type="cast", spellId=2), dict(actions=[2])

        result = execute_replanned(
            choose=choose,
            commit=lambda a: actions.append(a["spellId"]) or {"packets": 1},
            damaged=lambda: actions == [1, 2],
        )
        self.assertEqual(actions, [1, 2])
        self.assertEqual(result["status"], "validated_ordinary_ai")

    def test_end_turn_stops_without_forced_attack(self):
        result = execute_replanned(
            choose=lambda: (dict(type="end_turn"), {}),
            commit=lambda a: self.fail("Must not commit"),
            damaged=lambda: False,
        )
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["steps"], [])

    def test_three_real_actions_bound_is_preserved(self):
        actions = []
        result = execute_replanned(
            choose=lambda: (dict(type="move"), {}),
            commit=lambda a: actions.append(a) or {},
            damaged=lambda: False,
        )
        self.assertEqual(len(actions), 3)
        self.assertEqual(result["status"], "pending")


class ActualSequenceContractTests(unittest.TestCase):
    def test_actual_call_expression_matches_production_response_api(self):
        tree = ast.parse(Path(acceptance.__file__).read_text())
        calls = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "validate_response"
        ]
        self.assertEqual(len(calls), 1)
        spy = create_autospec(validate_response, return_value={"type": "move"})
        values = {
            name: object() for name in ("runtime", "request", "decision", "provider")
        }
        actual = eval(
            compile(ast.Expression(calls[0]), "<actual production API call>", "eval"),
            dict(values, validate_response=spy),
        )
        spy.assert_called_once_with(
            values["runtime"], values["request"], values["decision"], values["provider"]
        )
        self.assertEqual(actual, {"type": "move"})

    def test_final_pending_scene_can_appear_in_diagnostics_without_json_cycle(self):
        proof = dict(status="pending", steps=[dict(action={"type": "move"})])
        result = attach_scene_diagnostics(proof, [proof])
        self.assertEqual(json.loads(json.dumps(result))["status"], "pending")
        self.assertNotIn("prior_bounded_scene_diagnostics", proof)
