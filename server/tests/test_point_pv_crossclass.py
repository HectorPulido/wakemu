"""Native point-root targeting preserves cross-class Sacrifice semantics."""
import os
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
        # Exercise the shared boundary's policy, rather than the name or
        # location of the retired transaction-local helper.
        from contextlib import nullcontext
        from types import SimpleNamespace
        from wakfu_server.combat_entry_executor import execute_entry_roots
        from wakfu_server.combat_normal_execution_origin import normal_execution_origin

        for route in ("player", "summon.player"):
            for condition in (
                "eligible",
                "self",
                "missing_actor",
                "wrong_cell",
                "wrong_area",
                "wrong_selector",
                "direct_policy",
                "missing_policy",
                "numeric_policy",
            ):
                with self.subTest(route=route, condition=condition):
                    caster = SimpleNamespace(id=7, position=(0, 0, 0))
                    target = SimpleNamespace(position=(1, 0, 0))
                    preview = SimpleNamespace(
                        actors={7: caster, -7: target}, effect_resolution=nullcontext
                    )
                    plan = dict(
                        actor_id=7,
                        spell_id=6266,
                        evaluation_level=12,
                        target_id=-7,
                        target=(1, 0, 0),
                    )
                    effect = dict(
                        area_class="anD",
                        native_target_selector={"class": "fcE", "mask": 3},
                    )
                    policies = {"1": (None, False)}
                    if condition == "self":
                        plan.update(target_id=7, target=(0, 0, 0))
                    elif condition == "missing_actor":
                        del preview.actors[-7]
                    elif condition == "wrong_cell":
                        target.position = (2, 0, 0)
                    elif condition == "wrong_area":
                        effect["area_class"] = "anA"
                    elif condition == "wrong_selector":
                        effect["native_target_selector"] = {"class": "fcE", "mask": 65}
                    elif condition == "direct_policy":
                        policies["1"] = (None, True)
                    elif condition == "missing_policy":
                        policies.clear()
                    elif condition == "numeric_policy":
                        policies["1"] = (None, 0)
                    dispatcher = SimpleNamespace(
                        effects={"1": effect}, execute=lambda invocation: invocation
                    )
                    with patch(
                        "wakfu_server.combat_cost_payment_events.replay_paid_spell_costs"
                    ), patch(
                        "wakfu_server.combat_breeze_payment_events.replay_paid_breeze_costs"
                    ), patch(
                        "wakfu_server.combat_direct_target.native_direct_target_policies",
                        return_value=policies,
                    ):
                        outcomes = execute_entry_roots(
                            preview,
                            plan,
                            caster,
                            dispatcher,
                            (1,),
                            route=route,
                            execution_origin=normal_execution_origin(plan),
                            active_scope=lambda *args, **kwargs: nullcontext(),
                            event_scope=lambda *args: nullcontext(),
                        )
                    self.assertEqual(len(outcomes), 1)
                    self.assertIs(
                        outcomes[0].native_explicit_target, condition == "eligible"
                    )
