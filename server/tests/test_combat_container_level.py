import unittest
from types import SimpleNamespace
from wakfu_server.combat_container_level import running_container_level
from wakfu_server.combat_conditions import (
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)
from wakfu_server.wire import proto_field


class NativeContainerLevelTests(unittest.TestCase):
    def invocation(self, override=None):
        return SimpleNamespace(
            state_uid=None,
            native_context_hex=None
            if override is None
            else proto_field(32, override & ((1 << 64) - 1)).hex(),
            native_trigger_context={"value": 999, "level": 999},
        )

    def test_current_runner_short_override_then_actual_container(self):
        fight = SimpleNamespace()
        self.assertEqual(running_container_level(fight, {}, None), 0)
        plan = {"native_retained_container": {"present": True, "level": 200}}
        self.assertEqual(running_container_level(fight, plan, self.invocation()), 200)
        self.assertEqual(
            running_container_level(fight, plan, self.invocation(65538)), 2
        )
        self.assertEqual(running_container_level(fight, plan, self.invocation(-1)), 200)
        self.assertEqual(
            running_container_level(
                fight,
                {"native_retained_container": {"present": False}},
                self.invocation(),
            ),
            0,
        )
        self.assertEqual(
            running_container_level(
                fight, {"spell_id": 5345, "evaluation_level": 1}, self.invocation()
            ),
            1,
        )

    def test_unknown_current_container_not_inferred_from_actor_or_trigger(self):
        for plan in (
            {"level": 200},
            {"native_retained_container": {"present": True}},
            {"spell_id": 5345},
        ):
            with self.assertRaises(ValueError):
                running_container_level(SimpleNamespace(), plan, self.invocation())
        with self.assertRaises(ValueError):
            running_container_level(SimpleNamespace(), {}, self.invocation(-1))

    def test_criterion_shared_callback_and_unknown_authority(self):
        c = ConditionContext({}, current_container_level_query=lambda: 2)
        self.assertTrue(evaluate_condition("GetContainerLevel() == 2", c))
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetContainerLevel() == 2", ConditionContext({}))
        with self.assertRaises(UnknownCondition):
            evaluate_condition('GetContainerLevel("caster") == 2', c)
