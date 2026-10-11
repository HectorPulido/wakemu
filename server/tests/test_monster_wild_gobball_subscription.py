"""Actual wild gobball state child must remain deferred at installation."""
import unittest

from wakfu_server.combat_effect_dispatch import EffectDispatcher, EffectInvocation
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime


class WildGobballSubscriptionTests(unittest.TestCase):
    def test_actual_104345_registers_without_applying_state_2315(self):
        # Native state2315 -> group104344 -> listener104345, level1.
        effect = dict(
            effect_class=304,
            parameters=[2315.0, 0.0, 1.0, 0.0, -1.0, 0.0],
            parameter_count=3,
            probability_base=100,
            probability_per_level=0,
            minimum_level=0,
            maximum_level=32767,
            children=[],
            criteria="",
            target_masks=[None, [2], None, None, None, None, None],
        )
        runtime = object.__new__(NativeRetainedRuntime)
        runtime.definition = lambda effect, invocation: {"subscription": True}
        pending = []
        runtime.begin_group = lambda effect, values, invocation: {
            "reference": invocation.reference,
            "level": invocation.level,
            "state_uid": invocation.state_uid,
            "values": values,
        }
        runtime.finish_group = pending.append

        def unexpected(*args):
            raise AssertionError("State listener calculation requires its native event")

        dispatcher = EffectDispatcher(
            {"104345": effect},
            {304: unexpected},
            resolve=lambda effect, invocation: (invocation,),
            condition_context=unexpected,
            probability_accepts=unexpected,
            group_cells=unexpected,
            actor_position=unexpected,
            group_retention=runtime,
        )
        self.assertTrue(
            dispatcher.execute(
                EffectInvocation(
                    104345,
                    1,
                    7,
                    7,
                    (4, 5, 0),
                    state_uid=900,
                )
            )
        )
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["reference"], 104345)
        self.assertEqual(pending[0]["state_uid"], 900)
        # Static operands are decoded before registration; runner C/state
        # application and probability acceptance still wait for the event.
        self.assertEqual(
            pending[0]["values"],
            {
                "parameters": [2315, 1, -1],
                "probability": 100.0,
            },
        )


if __name__ == "__main__":
    unittest.main()
