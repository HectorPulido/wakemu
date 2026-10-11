import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_state_variants import state_child_variant_mode
from wakfu_server.combat_state_carrier import state_carrier_payload
from wakfu_server.combat_state_variants import paired_state_variants
from pathlib import Path
import json
import copy


class NativeStateVariantTests(unittest.TestCase):
    def test_multiple_structured_pairs_select_one_branch_and_preserve_mixed_all(self):
        definitions = self.paired_roots()
        first, second = [
            copy.deepcopy(definitions[str(key)]) for key in (350694, 351908)
        ]
        first["effect_class"] = second["effect_class"] = 999
        definitions.update({"1": first, "2": second})
        state = SimpleNamespace(reference=7931, effect_ids=[1, 2, 350694, 351908])
        self.assertTrue(paired_state_variants(state, definitions))
        with patch(
            "wakfu_server.combat_state_variants.resolve_state_container",
            return_value=state,
        ):
            for critical in (False, True):
                self.assertEqual(
                    state_child_variant_mode(
                        SimpleNamespace(),
                        18,
                        effect_definitions=definitions,
                        causing_critical=critical,
                    ),
                    "CRITICALS_ONLY" if critical else "EFFECTS_ONLY",
                )
        definitions["2"]["criteria"] = "HasState(1)"
        self.assertFalse(paired_state_variants(state, definitions))
        definitions["2"]["criteria"] = definitions["1"]["criteria"]
        state.effect_ids = [1, 2, 1, 2]
        self.assertFalse(paired_state_variants(state, definitions))

    def paired_roots(self):
        evidence = (
            Path(__file__).resolve().parents[2]
            / "docs/reports/combat-inventory/native-cra-beacon-reaction-contract-20261008.json"
        )
        return json.loads(evidence.read_text())["compiled_paired_root_definitions"]

    def test_paired_policy_uses_causing_hit_not_old_creation_critical(self):
        definitions = self.paired_roots()
        state = SimpleNamespace(reference=7802, effect_ids=[350694, 351908])
        for created_critical, hit_critical in ((False, True), (True, False)):
            payload = state_carrier_payload(
                uid=18,
                base_uid=None,
                caster_id=7,
                target_id=7,
                state_id=7802,
                level=3,
                native_turn_clock=-1,
                native_realtime_remaining=0,
                critical=created_critical,
            )
            with patch(
                "wakfu_server.combat_state_variants.resolve_state_container",
                return_value=state,
            ):
                self.assertEqual(
                    state_child_variant_mode(
                        SimpleNamespace(state_wire_payloads={18: payload.hex()}),
                        18,
                        effect_definitions=definitions,
                        causing_critical=hit_critical,
                    ),
                    "CRITICALS_ONLY" if hit_critical else "EFFECTS_ONLY",
                )
                # Instant carriers do not need a fabricated serialized payload.
                self.assertEqual(
                    state_child_variant_mode(
                        SimpleNamespace(state_wire_payloads={}),
                        18,
                        effect_definitions=definitions,
                        causing_critical=hit_critical,
                    ),
                    "CRITICALS_ONLY" if hit_critical else "EFFECTS_ONLY",
                )
                with self.assertRaisesRegex(ValueError, "causing branch"):
                    state_child_variant_mode(
                        SimpleNamespace(), 18, effect_definitions=definitions
                    )

    def test_pair_policy_preserves_unpaired_and_mixed_states(self):
        definitions = self.paired_roots()
        self.assertTrue(
            paired_state_variants(
                SimpleNamespace(effect_ids=[350694, 351908]), definitions
            )
        )
        self.assertFalse(
            paired_state_variants(SimpleNamespace(effect_ids=[350694]), definitions)
        )
        mixed = copy.deepcopy(definitions)
        mixed["351908"]["criteria"] = "HasState(1)"
        self.assertFalse(
            paired_state_variants(SimpleNamespace(effect_ids=[350694, 351908]), mixed)
        )
        with patch(
            "wakfu_server.combat_state_variants.resolve_state_container",
            return_value=SimpleNamespace(reference=7802, effect_ids=[350694, 351908]),
        ):
            self.assertEqual(
                state_child_variant_mode(
                    SimpleNamespace(),
                    18,
                    effect_definitions=mixed,
                    causing_critical=True,
                ),
                "ALL",
            )

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
