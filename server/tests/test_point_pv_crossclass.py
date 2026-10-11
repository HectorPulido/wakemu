"""Native point-root targeting preserves cross-class Sacrifice semantics."""
import gc

gc.disable()
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import test_sacrier_sacrifice_pipeline as sacrifice
import wakfu_server.combat_spell_transaction as transaction
import wakfu_server.combat_server_spell as server


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class PointPVCrossClassCandidateTests(unittest.TestCase):
    def test_actual_sacrifice_and_enemy_owned_attack_keep_redirect_and_swap_contract(
        self,
    ):
        case = sacrifice.SacrificePipelineTests()
        with patch.object(
            server, "prepare_spell_transaction", transaction.prepare_spell_transaction
        ):
            result, original, before = case.run_attack()
        self.assertEqual(result.fight.actors[-7].hp, before[-7][0])
        self.assertLess(result.fight.actors[7].hp, before[7][0])
        self.assertEqual(result.fight.actors[7].position, before[-7][1])
        self.assertEqual(result.fight.actors[-7].position, before[7][1])
        self.assertIn(
            4800, {state.reference for state in original.actors[7].state_ledger.entries}
        )
        self.assertNotIn(
            4800,
            {state.reference for state in original.actors[-7].state_ledger.entries},
        )
        self.assertEqual(original.actors[7].position, before[7][1])
        self.assertEqual(original.actors[-7].position, before[-7][1])

    def test_point_root_source_retains_all_native_policy_guards(self):
        # Static source contract; runtime outcomes are covered by the native
        # acquisition, attack, and Sacrifice tests above.
        import ast

        source = ast.parse(
            Path("server/wakfu_server/combat/combat_spell_transaction.py").read_text()
        )
        function = next(
            node
            for node in ast.walk(source)
            if isinstance(node, ast.FunctionDef)
            and node.name == "_native_explicit_point_root_target"
        )
        return_value = next(
            (node.value for node in function.body if isinstance(node, ast.Return)),
            None,
        )
        self.assertIsNotNone(return_value, "point-root helper must return its guard")
        actual = ast.dump(return_value, include_attributes=False)
        expected = ast.dump(
            ast.parse(
                "plan['target_id'] != caster.id "
                "and plan['target_id'] in preview.actors "
                "and preview.actors[plan['target_id']].position == tuple(plan['target']) "
                "and dispatcher.effects[str(reference)].get('area_class') == 'anD' "
                "and dispatcher.effects[str(reference)].get('native_target_selector') == {'class': 'fcE', 'mask': 3} "
                "and root_direct_policies.get(str(reference), (None, None))[1] is False",
                mode="eval",
            ).body,
            include_attributes=False,
        )
        self.assertEqual(actual, expected)
