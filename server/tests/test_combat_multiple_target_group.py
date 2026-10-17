import unittest
from dataclasses import replace
from types import SimpleNamespace
from wakfu_server.combat_multiple_target_group import select_multiple_targets
from wakfu_server.combat_effect_dispatch import EffectInvocation, EffectDispatcher
from wakfu_server.combat_conditions import ConditionContext


class MultipleTargetGroupTests(unittest.TestCase):
    def setUp(self):
        self.positions = {1: (0, 0, 0), 2: (0, -1, -1), 3: (1, 0, 2), 4: (0, 1, 0)}
        self.inv = EffectInvocation(90, 1, 1, None, (9, 9, 5))
        self.rows = [replace(self.inv, target_id=i) for i in (2, 4, 3)]

    def select(self, parameters, **kwargs):
        return select_multiple_targets(
            {"parameters": parameters},
            self.rows,
            caster_position=self.positions[1],
            position=self.positions.__getitem__,
            condition=kwargs.get("condition", lambda row: True),
            rng=kwargs.get("rng", lambda: 0.5),
        )

    def test_spiral_native_order_center_and_count(self):
        self.assertEqual([r.target_id for r in self.select([2, 0, 0, 1])], [3, 4])
        self.assertEqual([r.target_id for r in self.select([3, 0, 0, 2])], [2, 4, 3])
        self.assertEqual([r.target_id for r in self.select([3, 0, 0, 99])], [2, 4, 3])
        self.assertEqual(self.select([-1]), ())

    def test_filter_precedes_shuffle_and_draws_are_transactional(self):
        calls = []

        def rng():
            calls.append(1)
            return 0

        result = self.select(
            [3, 1, 1, 0], condition=lambda row: row.target_id != 4, rng=rng
        )
        self.assertEqual([row.target_id for row in result], [3, 2])
        self.assertEqual(calls, [1])

    def test_same_xy_stable_ties_preserve_shuffle_order(self):
        self.positions[4] = (1, 0, 0)
        result = self.select([3, 0, 0, 1])
        self.assertEqual([r.target_id for r in result], [4, 3, 2])

    def test_dispatcher_runs_all_children_with_direct_pv_actual_height(self):
        from test_combat_effect_dispatch import effect

        seen = []
        effects = {
            "90": effect(345, (2, 0, 0, 1), children=(91, 92)),
            "91": effect(400),
            "92": effect(400),
        }
        retention = SimpleNamespace(
            is_subscription=lambda *a: False,
            begin_group=lambda *a: None,
            finish_group=lambda *a, **kw: None,
            child_level_context=lambda *a, **kw: (1, b""),
            probability_bypassed=lambda *a: False,
        )

        def handler(e, v, i):
            seen.append(i)
            return True

        dispatcher = EffectDispatcher(
            effects,
            {400: handler},
            resolve=lambda e, i: (i,),
            condition_context=lambda i: ConditionContext({}),
            probability_accepts=lambda *a: True,
            group_cells=lambda *a: (),
            actor_position=self.positions.__getitem__,
            group_retention=retention,
            multiple_group_candidates=lambda *a: self.rows,
            group_random=lambda: 0.5,
            pt_preflight=lambda *a: True,
        )
        self.assertTrue(dispatcher.execute(self.inv))
        self.assertEqual(
            [(i.reference, i.target_id, i.cell) for i in seen],
            [
                (91, 3, (1, 0, 2)),
                (92, 3, (1, 0, 2)),
                (91, 4, (0, 1, 0)),
                (92, 4, (0, 1, 0)),
            ],
        )
        self.assertTrue(
            all(i.native_explicit_target and i.native_running_uid is None for i in seen)
        )

    def test_pr_suppression_preserves_owned_qf_registration(self):
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime

        runtime = object.__new__(NativeRetainedRuntime)
        runtime.fight = SimpleNamespace(native_owned_group_effects={})
        runtime.packets = []
        runtime.metadata = {
            "effects": {
                "90": {
                    "effect_class": 345,
                    "variant": 0,
                    "minimum_level": 1,
                    "maximum_level": 1,
                    "parameters": [],
                    "definition_type": 2,
                    "subscription": False,
                }
            }
        }
        registered = []
        runtime.record = registered.append
        record = object()
        runtime.finish_group(
            {
                "uid": 901,
                "record": record,
                "invocation": {
                    "reference": self.inv.reference,
                    "level": self.inv.level,
                    "caster_id": self.inv.caster_id,
                    "target_id": self.inv.target_id,
                    "state_uid": self.inv.state_uid,
                },
                "_delivery_effect": {
                    "effect_class": 345,
                    "variant": 0,
                    "minimum_level": 1,
                    "maximum_level": 1,
                    "parameters": [],
                    "native_execution_mode": 2,
                    "native_timing_definition": {},
                },
                "_delivery_invocation": self.inv,
            },
            notify=False,
        )
        self.assertEqual(registered, [record])
        self.assertIn(901, runtime.fight.native_owned_group_effects)
        self.assertEqual(runtime.packets, [])


if __name__ == "__main__":
    unittest.main()
