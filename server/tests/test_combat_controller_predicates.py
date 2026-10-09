import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_original_controller import controller_predicate
from wakfu_server.combat_casting_context import use_gate_triggering_effect


class NativeControllerPredicateTests(unittest.TestCase):
    def test_empty_native_boolean_signatures(self):
        context = ConditionContext(
            {},
            original_controller_predicate_query=lambda name: True,
            use_gate_triggering_effect_query=lambda: False,
        )
        for name in (
            "IsOriginalController",
            "CasterAndTargetHaveSameOriginalController",
        ):
            self.assertTrue(evaluate_condition(name + "()", context))
            with self.assertRaises(UnknownCondition):
                evaluate_condition(name + '("target")', context)
        self.assertFalse(evaluate_condition("UseGateTriggeringEffect()", context))
        with self.assertRaises(UnknownCondition):
            evaluate_condition("UseGateTriggeringEffect(1)", context)

    def test_actual_identity_and_controller_are_separate_including_zero(self):
        for original in (0, 1, 2, -(1 << 63)):
            for identity in (0, 1, 2, -(1 << 63)):
                for other in (0, 1, 2, -(1 << 63)):
                    source = SimpleNamespace(id=99, controller=original)
                    target = SimpleNamespace(id=identity, controller=other)
                    fight = SimpleNamespace(actors={99: source, identity: target})
                    authority = lambda f, a: SimpleNamespace(
                        targeting={"is_eGj": True}, native_controller_id=a.controller
                    )
                    kwargs = dict(target_is_cell=False)
                    self.assertEqual(
                        controller_predicate(
                            fight,
                            authority,
                            99,
                            identity,
                            None,
                            name="IsOriginalController",
                            **kwargs
                        ),
                        identity == original,
                    )
                    self.assertEqual(
                        controller_predicate(
                            fight,
                            authority,
                            99,
                            identity,
                            None,
                            name="CasterAndTargetHaveSameOriginalController",
                            **kwargs
                        ),
                        other == original,
                    )

    def test_trigger_null_and_null_active_pz_do_not_borrow_trigger_spell(self):
        invocation = SimpleNamespace(native_trigger_context=None)
        fight = SimpleNamespace(native_active_spell_id=None)
        self.assertFalse(
            use_gate_triggering_effect(None, fight, {"spell_id": 1}, {}, invocation)
        )
        invocation.native_trigger_context = dict(
            native_events_verified=True,
            native_container={
                "present": True,
                "is_spell": True,
                "spell_id": 777,
                "level": 200,
            },
            cell=[8, 9, 10],
        )
        self.assertFalse(
            use_gate_triggering_effect(None, fight, {"spell_id": 1}, {}, invocation)
        )
        fight.native_active_spell_id = 1
        with self.assertRaises(ValueError):
            use_gate_triggering_effect(None, fight, {"spell_id": 1}, {}, invocation)

    def test_trigger_forwards_actual_source_cell_and_current_pz_container(self):
        source = dict(
            native_events_verified=True,
            cell=[8, 9, 10],
            native_container={
                "present": True,
                "is_spell": True,
                "spell_id": 777,
                "level": 200,
            },
        )
        container = {"present": True, "is_spell": True, "spell_id": 17, "level": 4}
        fight = SimpleNamespace(
            native_active_spell_id=17, native_active_spell_container=container
        )
        invocation = SimpleNamespace(native_trigger_context=source)
        with patch(
            "wakfu_server.combat_casting_context.use_gate_effect", return_value=True
        ) as query:
            self.assertTrue(
                use_gate_triggering_effect(
                    "adapter", fight, {"spell_id": 999}, {}, invocation
                )
            )
        actual = query.call_args.kwargs["trigger_source"]
        self.assertEqual(actual["cell"], source["cell"])
        self.assertEqual(actual["casting_container"], container)
        self.assertNotEqual(
            actual["casting_container"]["spell_id"],
            source["native_container"]["spell_id"],
        )

    def test_active_spell_scope_restores_exact_current_pl_descriptor(self):
        from wakfu_server.combat_active_spell import (
            active_spell_scope,
            active_spell_container,
        )

        fight = SimpleNamespace(native_active_spell_id=None)
        with active_spell_scope(fight, 17, level=4):
            self.assertEqual(active_spell_container(fight)["level"], 4)
            with active_spell_scope(fight, 19, level=8):
                self.assertEqual(active_spell_container(fight)["spell_id"], 19)
            self.assertEqual(active_spell_container(fight)["spell_id"], 17)
        self.assertEqual(active_spell_container(fight), {"present": False})
