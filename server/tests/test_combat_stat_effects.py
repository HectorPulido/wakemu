import unittest
from wakfu_server.combat_stat_effects import (
    null_execution_status,
    stat_parameters,
    apply_current_stat,
    remove_current_stat,
    owned_effect_payload,
    owned_effect_application,
    current_stat_initial_eligible,
)
from wakfu_server.combat_effect_removal import _identity_fields, running_effect_removal


class CommonStatEffectTests(unittest.TestCase):
    def test_initial_zero_guard_precedes_percent_conversion_and_actual_clamping(self):
        self.assertFalse(
            current_stat_initial_eligible(0, zero_initial_amount_rejected=True)
        )
        self.assertTrue(
            current_stat_initial_eligible(0, zero_initial_amount_rejected=False)
        )
        self.assertTrue(
            current_stat_initial_eligible(1, zero_initial_amount_rejected=True)
        )
        result = apply_current_stat(
            family="eWQ",
            current=1,
            minimum=0,
            maximum=100,
            requested=1,
            percent=True,
            executable=True,
            frozen=False,
            source_guards_verified=True,
            limit_policy="NORMAL",
        )
        self.assertEqual(
            result["actual"], 0
        )  # PT count still1 after entered execution.

    def test_null400_uses_levelzero_and_signed_execution_status(self):
        self.assertEqual(null_execution_status([]), -1)
        self.assertEqual(null_execution_status([], current_status=7), 7)
        self.assertEqual(null_execution_status([7, 1]), 7)
        self.assertEqual(null_execution_status([255, 0]), -1)

    def test_native_eWW_parameter_contract_and_explicit_trigger(self):
        ctx = dict(registered_stat_id=None, percent_default=False, trigger_value=None)
        self.assertEqual(
            stat_parameters([10, 0.5, 1, 0, 20, 0], 20, **ctx),
            dict(stat_id=20, requested=20, percent=True),
        )
        self.assertEqual(
            stat_parameters(
                [-1, 0], 0, **dict(ctx, registered_stat_id=20, trigger_value=30)
            )["requested"],
            30,
        )
        with self.assertRaises(ValueError):
            stat_parameters([-1, 0], 0, **dict(ctx, registered_stat_id=20))
        with self.assertRaises(ValueError):
            stat_parameters([10, 0] * 4, 0, **ctx)

    def test_owned_actual_clamped_delta_controls_removal(self):
        context = dict(
            current=80,
            minimum=0,
            maximum=100,
            requested=30,
            percent=False,
            executable=True,
            frozen=False,
            source_guards_verified=True,
            limit_policy="NORMAL",
        )
        result = apply_current_stat(family="eWQ", **context)
        self.assertEqual(
            result, dict(current=100, actual=20, requested=30, stat_changed=True)
        )
        self.assertEqual(
            remove_current_stat(
                family="eWQ",
                current=100,
                minimum=0,
                maximum=100,
                actual=20,
                frozen=False,
                limit_policy="NORMAL",
            ),
            80,
        )
        result = apply_current_stat(family="eWR", **dict(context, current=10))
        self.assertEqual((result["current"], result["actual"]), (0, 10))
        self.assertEqual(
            remove_current_stat(
                family="eWR",
                current=0,
                minimum=0,
                maximum=100,
                actual=10,
                frozen=False,
                limit_policy="NORMAL",
            ),
            10,
        )
        self.assertEqual(
            apply_current_stat(family="eWQ", **dict(context, frozen=True))["actual"], 0
        )
        self.assertEqual(
            apply_current_stat(family="eWR", **dict(context, percent=True))["current"],
            56,
        )
        with self.assertRaises(ValueError):
            apply_current_stat(family="eWN", **context)

    def test_native_stat_additional_fields_and_common_application_removal(self):
        context = dict(
            uid=2345,
            base_uid=1234,
            generic_effect=150327,
            caster_id=22,
            target_id=-33,
            value=30,
        )
        payload = owned_effect_payload(**context, stat_id=20, requested=30)
        messages = {}
        fields = _identity_fields(payload, messages=messages)
        self.assertEqual(messages[8], bytes.fromhex("6014c8011e"))
        self.assertEqual((fields[1], fields[4]), (2345, 30))
        applied = owned_effect_application(
            1,
            2,
            effect_class=120,
            target_id=-33,
            uid=2345,
            running_effect_payload=payload,
        )
        removed = running_effect_removal(
            1,
            2,
            effect_class=120,
            target_id=-33,
            uid=2345,
            running_effect_payload=payload,
        )
        self.assertEqual(applied, removed[:-16])
        nil = owned_effect_payload(**dict(context, value=0))
        messages = {}
        _identity_fields(nil, messages=messages)
        self.assertEqual(messages, {})
        with self.assertRaises(ValueError):
            owned_effect_payload(**context, stat_id=20)
