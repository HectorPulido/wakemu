import unittest
from types import SimpleNamespace

from wakfu_server.combat_ai_control import (
    NativeAIControlHandler,
    native_ai_control_value,
    restore_native_ai_control,
    set_native_ai_control,
)


class NativeAIControlTests(unittest.TestCase):
    def test_native_parameter_positive_gate(self):
        for parameter, expected in (
            (-2147483648, 0),
            (-1, 0),
            (0, 0),
            (1, 1),
            (2147483647, 1),
        ):
            self.assertEqual(native_ai_control_value(parameter), expected)

    def test_removal_restores_class_baseline_instead_of_prior_effect(self):
        actor = SimpleNamespace(native_controlled_by_ai=True)
        set_native_ai_control(actor, False)
        restore_native_ai_control(
            actor, SimpleNamespace(native_ai_control_baseline=True)
        )
        self.assertTrue(actor.native_controlled_by_ai)

    def test_missing_native_fields_reject_before_mutation(self):
        actor = SimpleNamespace(native_controlled_by_ai=False)
        with self.assertRaises(ValueError):
            restore_native_ai_control(actor, SimpleNamespace())
        self.assertFalse(actor.native_controlled_by_ai)
        with self.assertRaises(ValueError):
            set_native_ai_control(SimpleNamespace(), True)
        with self.assertRaises(ValueError):
            native_ai_control_value(True)

    def test_actual_prepare_phase_order_and_delivery_before_control_mutation(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_stat_handler import StatExecutionContext

        actor = SimpleNamespace(id=7, native_controlled_by_ai=False)
        fight = SimpleNamespace(actors={7: actor})
        phases, packets = [], []
        effect = dict(effect_class=325, parameters=[1, 0], target_masks=[[]] * 7)
        invocation = EffectInvocation(
            22,
            1,
            7,
            7,
            (0, 0, 0),
            native_context_hex="0800100020ffffffffffffffffff0128013000380040004800",
        )

        def delivery(e, i, **kwargs):
            self.assertFalse(actor.native_controlled_by_ai)
            self.assertEqual(kwargs["value"], 1)
            return ((12613, b"verified-provider"), b"verified-payload")

        handler = NativeAIControlHandler(
            fight,
            packets,
            allocate_uid=lambda: 1,
            context=lambda e, i: StatExecutionContext(True, True, None, False, b""),
            authority=lambda f, a: SimpleNamespace(targeting={"is_eGj": True}),
            rng=lambda: 0.5,
            delivery=delivery,
        )
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda e, i, **k: phases.append(
                (k["channel"], k["value"], k["_execution_status"])
            )
        )
        self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual(phases, [(1, 0, -1), (2, 1, -1), (3, 1, -1), (4, 1, -1)])
        self.assertTrue(actor.native_controlled_by_ai)
        self.assertEqual(handler.runners, {})

    def test_missing_context_rejects_before_uid_or_mutation(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_stat_handler import StatExecutionContext

        actor = SimpleNamespace(id=7, native_controlled_by_ai=False)
        allocations = []
        handler = NativeAIControlHandler(
            SimpleNamespace(actors={7: actor}),
            [],
            allocate_uid=lambda: allocations.append(1),
            context=lambda e, i: StatExecutionContext(True, True, None, False, b""),
            authority=lambda f, a: None,
            rng=lambda: 0.5,
            delivery=lambda *a, **k: None,
        )
        with self.assertRaisesRegex(ValueError, "context origin"):
            handler(
                dict(effect_class=325), {}, EffectInvocation(22, 1, 7, 7, (0, 0, 0))
            )
        self.assertEqual(allocations, [])
        self.assertFalse(actor.native_controlled_by_ai)

    def test_retained_application_and_removal_restore_original_baseline(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_ai_control import (
            ai_control_delivery,
            remove_ai_control,
        )

        actor = SimpleNamespace(id=7, native_controlled_by_ai=False)
        fight = SimpleNamespace(id=1, actors={7: actor}, owned_stat_effects={})
        packets = []
        handler = NativeAIControlHandler(
            fight,
            packets,
            allocate_uid=lambda: 1,
            context=lambda e, i: StatExecutionContext(True, True, None, True, b""),
            authority=lambda f, a: SimpleNamespace(
                targeting={"is_eGj": True}, native_ai_control_baseline=False
            ),
            rng=lambda: 0.5,
            delivery=lambda e, i, **k: ai_control_delivery(1, 2, e, i, **k),
        )
        invocation = EffectInvocation(
            22,
            1,
            7,
            7,
            (0, 0, 0),
            native_context_hex="0800100020ffffffffffffffffff0128013000380040004800",
        )
        self.assertTrue(
            handler(dict(effect_class=325, parameters=[1, 0]), {}, invocation)
        )
        self.assertTrue(actor.native_controlled_by_ai)
        self.assertEqual(packets[0][0], 12613)
        remover = SimpleNamespace(fight=fight, packets=packets, action_id=2)
        remove_ai_control(remover, 1)
        self.assertFalse(actor.native_controlled_by_ai)
        self.assertEqual(fight.owned_stat_effects, {})
        self.assertEqual(packets[-1][0], 13560)

    def test_actual_detached_bje_authority_preserves_baseline_separately(self):
        from wakfu_server.combat_summon_creation import native_fresh_summon_authority

        actor = SimpleNamespace(id=9, effective_level=1, native_controlled_by_ai=False)
        authority = native_fresh_summon_authority(actor, 3798)
        self.assertTrue(authority.native_ai_control_baseline)
        self.assertFalse(authority.native_controlled_by_ai)
