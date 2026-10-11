"""Installed native eWu wire and deferred dispatch regressions."""
import unittest

from test_combat_subscription_runners import fields
from wakfu_server.combat_subscription_runners import (
    DEFERRED_RUNNERS,
    SUBSCRIPTION_FAMILIES,
    deferred_payload,
)


class SubscribedState304Tests(unittest.TestCase):
    def test_fresh_state_listener_matches_installed_native_constructor(self):
        native = bytes.fromhex(
            "08850710a00618d8b21520002a06080410051800300738f9ffffffffffffffff01"
            "420d580070ffffffffffffffffff01"
            "5a2b080010ffffffffffffffffff011a0f080010ffffffffffffffffff011800"
            "20ffffffffffffffffff012800"
        )
        actual = deferred_payload(
            family=304,
            uid=901,
            base_uid=800,
            generic_effect=350552,
            caster_id=7,
            target_id=-7,
            cell=(4, 5, 0),
            timing_payload=bytes.fromhex(
                "08001a0f080010ffffffffffffffffff01180020ffffffffffffffffff01"
            ),
            container_type=None,
            container_id=None,
        )
        got, expected = fields(actual), fields(native)
        self.assertEqual(
            {k: v for k, v in got.items() if k != 11},
            {k: v for k, v in expected.items() if k != 11},
        )
        self.assertEqual(fields(got[11]), fields(expected[11]))
        self.assertEqual(fields(got[8]), {11: 0, 14: (1 << 64) - 1})
        self.assertEqual(DEFERRED_RUNNERS[304], "eWu")
        self.assertIn(304, SUBSCRIPTION_FAMILIES)

    def test_registration_waits_for_event_without_state_calculation(self):
        from wakfu_server.combat_effect_dispatch import (
            EffectDispatcher,
            EffectInvocation,
        )
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime

        effect = dict(
            effect_class=304,
            parameters=[],
            parameter_count=0,
            probability_base=100,
            probability_per_level=0,
            minimum_level=1,
            maximum_level=200,
            children=[],
            criteria="UnsupportedCriterion()",
            target_masks=[[1003], [], [], [], [], [], []],
        )
        runtime = object.__new__(NativeRetainedRuntime)
        runtime.definition = lambda effect, inv: {"subscription": True}
        runtime.begin_group = lambda effect, values, inv: {"reference": inv.reference}
        saved = []
        runtime.finish_group = saved.append

        def unexpected(*args):
            raise AssertionError("Fresh state listener must not execute before event")

        dispatcher = EffectDispatcher(
            {"52091": effect},
            {304: unexpected},
            resolve=lambda effect, inv: (inv,),
            condition_context=unexpected,
            probability_accepts=unexpected,
            group_cells=unexpected,
            actor_position=unexpected,
            group_retention=runtime,
        )
        self.assertTrue(dispatcher.execute(EffectInvocation(52091, 1, 1, 2, (0, 0, 0))))
        self.assertEqual(saved, [{"reference": 52091}])
