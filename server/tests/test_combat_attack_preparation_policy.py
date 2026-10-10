"""Server policy contracts complement the real source-owned Iop acceptance."""
from contextlib import nullcontext
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from wakfu_server import combat_attack_preparation as policy
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_conditions import ConditionContext


def definition(family, children=(), *, mask=None, parameters=(), criteria=""):
    masks = [None] * 7
    if mask:
        masks[mask[0]] = [mask[1]]
    return dict(
        effect_class=family,
        children=list(children),
        target_masks=masks,
        parameters=list(parameters),
        criteria=criteria,
    )


class AttackPreparationPolicyTests(unittest.TestCase):
    def fixture(self):
        state = SimpleNamespace(uid=42, target_id=7, reference=99)
        owner = SimpleNamespace(
            position=(1, 2, 0), state_ledger=SimpleNamespace(entries=[state])
        )
        fight = SimpleNamespace(
            actors={7: owner},
            native_owned_group_effects={
                10: {"invocation": {"state_uid": 42, "reference": 1}}
            },
        )
        effects = {
            "1": definition(330, (2, 6), mask=(0, 500)),
            "2": definition(330, (3, 4), mask=(0, 2)),
            "3": definition(1093),
            "4": definition(330, (5,), mask=(3, 2)),
            "5": definition(400),
            "6": definition(330, (7,), mask=(5, 1025)),
            "7": definition(
                321, parameters=(99, 0), criteria='HasEffectWithSpecificId("caster", 5)'
            ),
        }
        executed = []
        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(
                fight=fight, container_scope=lambda i: nullcontext()
            ),
            effects=effects,
            execute=lambda invocation: executed.append(invocation),
            condition_context=lambda invocation: ConditionContext({}),
        )
        invocation = EffectInvocation(
            3, 20, 7, 8, (3, 2, 0), state_uid=42, native_trigger_context={"uid": 111}
        )
        return fight, state, dispatcher, executed, invocation

    def test_successful_multitarget_modifier_constructs_marker_once_on_owner(self):
        fight, state, dispatcher, executed, invocation = self.fixture()
        with policy.attack_preparation_scope(fight, 7):
            policy._scope.get().update(delivered=True, source_uids={111, 222})
            with patch(
                "wakfu_server.combat_native_container.resolve_state_container",
                return_value=state,
            ):
                policy.note_preparation_modifier(fight, invocation)
                policy.note_preparation_modifier(
                    fight, replace(invocation, native_trigger_context={"uid": 222})
                )
                policy.settle_attack_preparation(dispatcher)
                policy.settle_attack_preparation(dispatcher)
        self.assertEqual(len(executed), 1)
        self.assertEqual((executed[0].reference, executed[0].target_id), (5, 7))
        self.assertTrue(executed[0].native_explicit_target)

    def test_removed_noted_carrier_is_not_recreated(self):
        fight, state, dispatcher, executed, invocation = self.fixture()
        with policy.attack_preparation_scope(fight, 7):
            policy._scope.get().update(delivered=True, source_uid=111)
            with patch(
                "wakfu_server.combat_native_container.resolve_state_container",
                return_value=state,
            ):
                policy.note_preparation_modifier(fight, invocation)
            fight.actors[7].state_ledger.entries.clear()
            with patch(
                "wakfu_server.combat_native_container.resolve_state_container",
                side_effect=AssertionError("removed carrier resolved"),
            ):
                policy.settle_attack_preparation(dispatcher)
        self.assertEqual(executed, [])

    def test_nonattack_and_failed_scope_do_not_construct_marker(self):
        fight, state, dispatcher, executed, invocation = self.fixture()
        with policy.attack_preparation_scope(fight, 7):
            policy.note_preparation_modifier(fight, invocation)
            policy.settle_attack_preparation(dispatcher)
        with self.assertRaisesRegex(ValueError, "failed root"):
            with policy.attack_preparation_scope(fight, 7):
                policy._scope.get().update(delivered=True, source_uid=111)
                with patch(
                    "wakfu_server.combat_native_container.resolve_state_container",
                    return_value=state,
                ):
                    policy.note_preparation_modifier(fight, invocation)
                raise ValueError("failed root")
        self.assertEqual(executed, [])
        self.assertIsNone(policy._scope.get())

    def test_declared_marker_branch_condition_is_not_bypassed(self):
        fight, state, dispatcher, executed, invocation = self.fixture()
        dispatcher.effects["4"]["criteria"] = "False"
        with policy.attack_preparation_scope(fight, 7):
            policy._scope.get().update(delivered=True, source_uid=111)
            with patch(
                "wakfu_server.combat_native_container.resolve_state_container",
                return_value=state,
            ):
                policy.note_preparation_modifier(fight, invocation)
                policy.settle_attack_preparation(dispatcher)
        self.assertEqual(executed, [])

    def test_unknown_source_carrier_keeps_authority_failure(self):
        fight, _, _, _, invocation = self.fixture()
        with policy.attack_preparation_scope(fight, 7):
            policy._scope.get().update(delivered=True, source_uid=111)
            with patch(
                "wakfu_server.combat_native_container.resolve_state_container",
                side_effect=ValueError("unknown carrier"),
            ):
                with self.assertRaisesRegex(ValueError, "unknown carrier"):
                    policy.note_preparation_modifier(fight, invocation)
