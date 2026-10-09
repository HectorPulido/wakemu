import unittest
from types import SimpleNamespace
from wakfu_server.combat_trigger_value_group import trigger_value_context
from wakfu_server.combat_value_transfer import apply_context_value
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_effects import _integer


def definition(ratio=100, addition=0):
    return {
        "effect_class": 1103,
        "parameters": [v for n in (0, 0, 1, 0, 1, 0, ratio, addition) for v in (n, 0)],
    }


class TriggerValueGroupTests(unittest.TestCase):
    def context(self, value, effect=None):
        original = b"".join(
            _integer(k, v)
            for k, v in (
                (1, 1),
                (2, 0),
                (4, -1),
                (5, 0),
                (6, 0),
                (7, 0),
                (8, 0),
                (9, 0),
            )
        )
        return trigger_value_context(
            effect or definition(),
            SimpleNamespace(level=1, native_trigger_context=value),
            original,
        )

    def test_native_set_overrides_value_without_changing_child_level(self):
        for value, expected in ((5, 3), (-5, -1)):
            payload = self.context({"value": value}, definition(50, 1))
            fields = _identity_fields(payload, integer_fields=(4, 6, 9))
            self.assertEqual(fields[4], (1 << 64) - 1)
            self.assertEqual(fields[9], 1)
            self.assertEqual(apply_context_value(999, payload), expected)

    def test_absent_source_preserves_parent_context_not_zero_override(self):
        self.assertEqual(apply_context_value(999, self.context(None)), 999)

    def test_unknown_or_non_native_value_rejected(self):
        for source in ({}, {"value": True}, {"value": 1 << 31}):
            with self.assertRaises(ValueError):
                self.context(source)

    def test_java_float_saturation_not_short_level_truncation(self):
        self.assertEqual(
            apply_context_value(0, self.context({"value": 5}, definition(1e20))),
            2147483647,
        )

    def test_defaults_and_signed_value_are_not_level_sentinels(self):
        d = definition()
        d["parameters"] = d["parameters"][:12]
        self.assertEqual(apply_context_value(100, self.context({"value": -1}, d)), -1)

    def test_native_codec_matches_original_eYb_context(self):
        from pathlib import Path

        path = (
            Path(__file__).resolve().parents[1]
            / "test-fixtures/combat/trigger-value1103-context.bin"
        )
        expected = _identity_fields(
            path.read_bytes(), integer_fields=(1, 2, 4, 5, 6, 7, 8, 9)
        )
        actual = _identity_fields(
            self.context({"value": 5}, definition(50, 1)),
            integer_fields=(1, 2, 4, 5, 6, 7, 8, 9),
        )
        # Probe d(source,false); test context models subscribed activation true.
        actual[1] = 0
        self.assertEqual(actual, expected)

    def dispatcher(self, source, value):
        from test_combat_effect_dispatch import effect
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
        from wakfu_server.combat_conditions import ConditionContext

        runtime = object.__new__(NativeRetainedRuntime)
        runtime.is_subscription = lambda *a: False
        runtime.probability_bypassed = lambda *a: False
        runtime.begin_group = lambda *a, **kw: None
        runtime.finish_group = lambda *a: None
        runtime.transmit_child_override = lambda e, i, v: v
        runtime.container_level = lambda i: (True, 20)

        def apply(e, v, i):
            source.hp -= apply_context_value(100, bytes.fromhex(i.native_context_hex))
            source.levels.append(i.level)
            return True

        return EffectDispatcher(
            {
                "90": effect(1103, (0, 0, 1, 0, 1, 0, 50, 1), children=(91, 92)),
                "91": effect(400),
                "92": effect(400),
            },
            {400: apply},
            resolve=lambda e, i: (i,),
            condition_context=lambda i: ConditionContext({}),
            probability_accepts=lambda *a: True,
            group_cells=lambda *a: (),
            actor_position=lambda identity: (0, 0, 0),
            group_retention=runtime,
        )

    def test_common_dispatch_applies_trigger_value_to_every_child_preserving_level(
        self,
    ):
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        source = SimpleNamespace(hp=20, levels=[])
        d = self.dispatcher(source, 5)
        self.assertTrue(
            d.execute(
                EffectInvocation(
                    90, 20, 7, 8, (0, 0, 0), native_trigger_context={"value": 5}
                )
            )
        )
        self.assertEqual((source.hp, source.levels), (14, [20, 20]))

    def test_failed_later_child_rolls_back_first_value_application(self):
        from contextlib import nullcontext
        from wakfu_server.combat_effect_dispatch import (
            EffectInvocation,
            run_effect_transaction,
            UnsupportedEffectExecution,
        )

        source = SimpleNamespace(
            hp=20, levels=[], effect_resolution=lambda: nullcontext()
        )

        def factory(preview):
            d = self.dispatcher(preview, 5)
            d.effects["92"]["effect_class"] = 123456
            return d

        with self.assertRaises(UnsupportedEffectExecution):
            run_effect_transaction(
                source,
                [
                    EffectInvocation(
                        90, 20, 7, 8, (0, 0, 0), native_trigger_context={"value": 5}
                    )
                ],
                factory,
            )
        self.assertEqual((source.hp, source.levels), (20, []))
