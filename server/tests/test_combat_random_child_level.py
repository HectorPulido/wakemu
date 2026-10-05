import unittest
from types import SimpleNamespace as N
from wakfu_server.combat_random_child_level import (
    random_child_level,
    effective_child_level,
)


class RandomChildLevelTests(unittest.TestCase):
    def test_maximum_exclusive_equal_bounds_without_draw_and_signed_short(self):
        for draw, value in ((0.0, 2), (0.999999, 4)):
            self.assertEqual(random_child_level([2, 5], lambda: draw), value)
        self.assertEqual(
            random_child_level([42, 42], lambda: self.fail("unexpected draw")), 42
        )
        self.assertEqual(effective_child_level(65535), -1)

    def test_invalid_bounds_and_java_width_overflow_reject_before_rng(self):
        for params in ([4, 1], [-2147483648, 2147483647], [1], [True, 2]):
            with self.assertRaises(ValueError):
                random_child_level(params, lambda: self.fail("unexpected draw"))

    def test_evx_context_matches_original_java_and_keeps_calculated_override(self):
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime

        runtime = object.__new__(NativeRetainedRuntime)
        runtime.transmit_child_override = lambda effect, inv, override: override
        context = runtime.child_context(
            {"effect_class": 1076}, {}, N(), event_activation=True, native_override=42
        )
        self.assertEqual(context.hex(), "08001000202a28013000380040004800")

    def dispatcher(self, seen, draws):
        from test_combat_effect_dispatch import effect
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_conditions import ConditionContext

        retention = N(
            is_subscription=lambda *a: False,
            probability_bypassed=lambda *a: False,
            begin_group=lambda *a, **kw: None,
            finish_group=lambda *a: None,
            child_level_context=lambda *a, native_override, **kw: (
                effective_child_level(native_override),
                b"",
            ),
        )
        return EffectDispatcher(
            {
                "90": effect(1076, (2, 5), children=(91, 92)),
                "91": effect(400),
                "92": effect(400),
            },
            {400: lambda e, v, i: seen.append(i) is None},
            resolve=lambda e, i: (i,),
            condition_context=lambda i: ConditionContext({}),
            probability_accepts=lambda *a: True,
            group_cells=lambda *a: self.fail("eWd does not expand area"),
            actor_position=lambda i: (0, 0, 0),
            group_retention=retention,
            random_child_level=lambda parameters: random_child_level(
                parameters, lambda: draws.append(1) or 0.5
            ),
        )

    def test_all_children_share_one_draw_and_original_nullable_pv_anchor(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        seen = []
        draws = []
        d = self.dispatcher(seen, draws)
        self.assertTrue(d.execute(EffectInvocation(90, 20, 7, None, (3, 4, 5))))
        self.assertEqual(draws, [1])
        self.assertEqual(
            [(i.reference, i.level, i.target_id, i.cell) for i in seen],
            [(91, 3, None, (3, 4, 5)), (92, 3, None, (3, 4, 5))],
        )

    def test_later_unknown_child_rolls_back_first_child(self):
        from contextlib import nullcontext
        from wakfu_server.combat_effect_dispatch import (
            run_effect_transaction,
            EffectInvocation,
            UnsupportedEffectExecution,
        )

        source = N(hp=20, effect_resolution=lambda: nullcontext())

        def factory(preview):
            d = self.dispatcher([], [])
            d.effects["92"]["effect_class"] = 123456
            d.handlers[400] = lambda *a: setattr(preview, "hp", preview.hp - 2) or True
            return d

        with self.assertRaises(UnsupportedEffectExecution):
            run_effect_transaction(
                source, [EffectInvocation(90, 20, 7, None, (3, 4, 5))], factory
            )
        self.assertEqual(source.hp, 20)

    def test_explicit_minus_one_sp_is_not_replaced_by_eyg_flag16_policy(self):
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
        from wakfu_server.combat_effect_removal import _identity_fields

        runtime = object.__new__(NativeRetainedRuntime)
        runtime.transmit_child_override = lambda *a: self.fail(
            "eYx writes its chosen SP directly"
        )
        context = runtime.child_context(
            {"effect_class": 1076, "native_effect_flags": [16]},
            {},
            N(),
            native_override=-1,
        )
        value = _identity_fields(context, integer_fields=(4,))[4]
        self.assertEqual(value & 0xFFFFFFFF, 0xFFFFFFFF)
