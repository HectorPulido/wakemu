import unittest
from wakfu_server.combat_trigger_level_group import trigger_group_override


def effect(ratio=1):
    return dict(
        effect_class=1020,
        parameters=[v for n in (0, 0, 1, 0, 1, 0, ratio) for v in (n, 0)],
    )


class TriggerGroupTests(unittest.TestCase):
    def test_actual_value_scaling_uses_java_truncation(self):
        self.assertEqual(
            trigger_group_override(
                effect(0.5), 1, source_present=True, trigger_value=5
            ),
            2,
        )
        self.assertEqual(
            trigger_group_override(
                effect(0.5), 1, source_present=True, trigger_value=-5
            ),
            -2,
        )

    def test_null_source_and_minus_one_override_keep_parent(self):
        self.assertEqual(
            trigger_group_override(
                effect(), 10, source_present=False, trigger_value=None
            ),
            10,
        )
        self.assertEqual(
            trigger_group_override(
                effect(),
                10,
                source_present=False,
                trigger_value=None,
                return_native_override=True,
            ),
            -1,
        )
        self.assertEqual(
            trigger_group_override(effect(), 10, source_present=True, trigger_value=-1),
            10,
        )

    def test_unknown_source_is_rejected_instead_of_assumed_absent(self):
        for present, value in ((None, None), (True, None), (False, 5), (True, True)):
            with self.assertRaises(ValueError):
                trigger_group_override(
                    effect(), 1, source_present=present, trigger_value=value
                )

    def test_native_f2i_saturation_then_signed_short_child_level(self):
        self.assertEqual(
            trigger_group_override(
                effect(1e20),
                1,
                source_present=True,
                trigger_value=5,
                return_native_override=True,
            ),
            2147483647,
        )
        self.assertEqual(
            trigger_group_override(
                effect(), 1, source_present=True, trigger_value=65536
            ),
            0,
        )

    def test_runtime_source_snapshot_requires_actual_effect_value(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_trigger_level_group import runtime_group_level
        from dataclasses import replace

        native = effect(0.5)
        native["native_execution_mode"] = 0
        invocation = EffectInvocation(
            308066, 1, 7, 7, (0, 0, 0), native_trigger_context=dict(value=-5)
        )
        self.assertEqual(runtime_group_level(native, {}, invocation, {}), -2)
        self.assertEqual(
            runtime_group_level(
                native, {}, replace(invocation, native_trigger_context=None), {}
            ),
            1,
        )
        with self.assertRaisesRegex(ValueError, "getValue"):
            runtime_group_level(
                native,
                {},
                replace(invocation, native_trigger_context=dict(uid=100)),
                {},
            )
