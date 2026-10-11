from types import SimpleNamespace
import unittest
from wakfu_server.combat_state_critical_source import causing_state_critical


class CausingStateCriticalTests(unittest.TestCase):
    def test_current_hit_overrides_old_creation_branch_in_both_directions(self):
        for hit in (False, True):
            invocation = SimpleNamespace(
                native_trigger_context=dict(
                    native_definition_present=True, native_definition_variant=int(hit)
                )
            )
            self.assertIs(
                causing_state_critical(invocation, current_critical=not hit), hit
            )

    def test_source_absent_uses_current_owned_execution_not_carrier_creation(self):
        for branch in (False, True):
            self.assertIs(
                causing_state_critical(SimpleNamespace(), current_critical=branch),
                branch,
            )

    def test_source_critical_is_dd_bit_one_not_exact_variant_value(self):
        for variant, expected in ((2, False), (3, True), (4, False), (5, True)):
            invocation = SimpleNamespace(
                native_trigger_context=dict(
                    native_definition_present=True, native_definition_variant=variant
                )
            )
            self.assertIs(
                causing_state_critical(invocation, current_critical=not expected),
                expected,
            )

    def test_proved_null_pk_is_noncritical_but_unknown_stays_unknown(self):
        invocation = SimpleNamespace(
            native_trigger_context=dict(native_definition_present=False)
        )
        self.assertIs(causing_state_critical(invocation, current_critical=True), False)
        for source in ({}, dict(native_definition_present=True)):
            self.assertIsNone(
                causing_state_critical(
                    SimpleNamespace(native_trigger_context=source),
                    current_critical=True,
                )
            )

    def test_malformed_typed_source_rejected(self):
        for source in (
            [],
            dict(native_definition_present=1),
            dict(native_definition_present=True, native_definition_variant=True),
        ):
            with self.assertRaises(ValueError):
                causing_state_critical(
                    SimpleNamespace(native_trigger_context=source),
                    current_critical=False,
                )

    def test_ordinary_resolver_routes_current_hit_with_actual_paired_definitions(self):
        import json
        import random
        from pathlib import Path
        from unittest.mock import patch
        from wakfu_server.combat_ordinary_authority import ordinary_cast_authority

        path = Path(__file__).resolve().parents[2] / (
            "docs/reports/combat-inventory/native-cra-beacon-reaction-contract-20261008.json"
        )
        definitions = json.loads(path.read_text())["compiled_paired_root_definitions"]
        timing = SimpleNamespace(
            catalog={"effects": definitions}, state=lambda *args: None
        )
        for hit in (False, True):
            authority = ordinary_cast_authority(
                actors=lambda *args: None,
                timing=timing,
                rng=random.Random(1),
                critical=not hit,
            )
            invocation = SimpleNamespace(
                reference=350694,
                state_uid=18,
                native_trigger_context=dict(
                    native_definition_present=True, native_definition_variant=int(hit)
                ),
            )
            with patch(
                "wakfu_server.combat_state_variants.resolve_state_container",
                return_value=SimpleNamespace(
                    reference=7802, effect_ids=[350694, 351908]
                ),
            ):
                context = authority.resolution(
                    SimpleNamespace(), {}, definitions["350694"], invocation
                )
            self.assertEqual(
                context.variant_mode, "CRITICALS_ONLY" if hit else "EFFECTS_ONLY"
            )
