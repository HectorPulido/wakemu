import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_state_variants import state_child_variant_mode
from wakfu_server.combat_state_carrier import state_carrier_payload


class NativeStateVariantTests(unittest.TestCase):
    def test_native_unfiltered_state_ignores_outer_critical_branch(self):
        with patch(
            "wakfu_server.combat_state_variants.resolve_state_container",
            return_value=SimpleNamespace(reference=3425),
        ):
            self.assertEqual(state_child_variant_mode(SimpleNamespace(), 18), "ALL")

    def test_selective_state_uses_actual_carrier_critical_and_rejects_missing(self):
        for critical, expected in ((False, "EFFECTS_ONLY"), (True, "CRITICALS_ONLY")):
            payload = state_carrier_payload(
                uid=18,
                base_uid=None,
                caster_id=7,
                target_id=7,
                state_id=3425,
                level=10,
                native_turn_clock=-1,
                native_realtime_remaining=0,
                critical=critical,
            )
            with patch(
                "wakfu_server.combat_state_variants.resolve_state_container",
                return_value=SimpleNamespace(reference=3425),
            ), patch.dict(
                "wakfu_server.combat_state_variants.RULES",
                selective_child_states=[3425],
            ):
                self.assertEqual(
                    state_child_variant_mode(
                        SimpleNamespace(state_wire_payloads={18: payload.hex()}), 18
                    ),
                    expected,
                )
                with self.assertRaisesRegex(ValueError, "authority"):
                    state_child_variant_mode(
                        SimpleNamespace(state_wire_payloads={}), 18
                    )
