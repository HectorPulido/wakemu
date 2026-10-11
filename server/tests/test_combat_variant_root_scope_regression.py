"""Generic root partition and descendant traversal regression for staged overlay."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from test_combat_state_variants import NativeStateVariantTests
from wakfu_server.combat_state_variants import state_child_variant_mode


class VariantRootScopeTests(unittest.TestCase):
    def test_selected_group_descendants_ignore_unrelated_current_critical(self):
        definitions = NativeStateVariantTests().paired_roots()
        state = SimpleNamespace(reference=7931, effect_ids=[350694, 351908])
        with patch(
            "wakfu_server.combat_state_variants.resolve_state_container",
            return_value=state,
        ):
            for critical in (False, True):
                self.assertEqual(
                    state_child_variant_mode(
                        None,
                        18,
                        effect_definitions=definitions,
                        causing_critical=critical,
                        effect_reference=123,
                    ),
                    "ALL",
                )
                self.assertEqual(
                    state_child_variant_mode(
                        None,
                        18,
                        effect_definitions=definitions,
                        causing_critical=critical,
                        effect_reference=350694,
                    ),
                    "CRITICALS_ONLY" if critical else "EFFECTS_ONLY",
                )

    def test_selective_state_roots_still_use_original_carrier_critical(self):
        from wakfu_server.combat_state_carrier import state_carrier_payload

        state = SimpleNamespace(reference=3425, effect_ids=[101, 102])
        for carrier_critical in (False, True):
            payload = state_carrier_payload(
                uid=18,
                base_uid=None,
                caster_id=7,
                target_id=7,
                state_id=3425,
                level=10,
                native_turn_clock=-1,
                native_realtime_remaining=0,
                critical=carrier_critical,
            )
            with patch(
                "wakfu_server.combat_state_variants.resolve_state_container",
                return_value=state,
            ), patch.dict(
                "wakfu_server.combat_state_variants.RULES",
                selective_child_states=[3425],
            ):
                self.assertEqual(
                    state_child_variant_mode(
                        SimpleNamespace(state_wire_payloads={18: payload.hex()}),
                        18,
                        effect_reference=101,
                        causing_critical=not carrier_critical,
                    ),
                    "CRITICALS_ONLY" if carrier_critical else "EFFECTS_ONLY",
                )
                self.assertEqual(
                    state_child_variant_mode(
                        SimpleNamespace(state_wire_payloads={18: payload.hex()}),
                        18,
                        effect_reference=103,
                        causing_critical=not carrier_critical,
                    ),
                    "ALL",
                )
                with self.assertRaisesRegex(ValueError, "authority"):
                    state_child_variant_mode(
                        SimpleNamespace(state_wire_payloads={}),
                        18,
                        effect_reference=101,
                    )

    def test_missing_state_authority_is_never_bypassed_for_descendants(self):
        with patch(
            "wakfu_server.combat_state_variants.resolve_state_container",
            side_effect=ValueError("Missing native state authority"),
        ):
            with self.assertRaisesRegex(ValueError, "authority"):
                state_child_variant_mode(
                    None, 18, effect_reference=123, causing_critical=False
                )
