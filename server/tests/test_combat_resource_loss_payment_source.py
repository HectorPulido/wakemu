"""Actual synthetic eWf cost-source shape and native null-Qe behavior."""
import unittest
from wakfu_server.combat_resource_loss import triggering_resource_loss


class ResourceLossPaymentSourceTests(unittest.TestCase):
    def test_actual_payment_bytes_override_generic_packed_value(self):
        source = dict(
            effect_action_id=None,
            value=0x030205,
            cost_source=dict(
                runner_class="eWf",
                spell_context={"present": False},
                action_costs={"ap": 3, "mp": 2, "wp": 5},
            ),
        )
        self.assertEqual(
            [triggering_resource_loss(source, stat) for stat in (2, 3, 4)], [3, 2, 5]
        )
        source["cost_source"]["action_costs"]["ap"] = -128
        self.assertEqual(triggering_resource_loss(source, 2), -128)

    def test_native_null_and_ordinary_value_preserve_source_contract(self):
        self.assertEqual(triggering_resource_loss(None, 2), 0)
        self.assertEqual(
            triggering_resource_loss({"effect_action_id": 3, "value": 9}, 3), 9
        )
        for source in (
            {},
            {"runner_class": "eWf", "effect_action_id": 30, "value": 10},
            {"cost_source": {"runner_class": "eWf", "action_costs": {"ap": 2}}},
        ):
            with self.assertRaises(ValueError):
                triggering_resource_loss(source, 2)
