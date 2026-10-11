"""Flag8 group admission requires exact source-qualified native faI identity."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from wakfu_server.combat_native_events import validate_group_registration_flags

# Installed native eVn export, health-ordering/native-flag8-identities.json.
NATIVE = {
    "187193": {
        "native_effect_flags": [8],
        "effect_class": 330,
        "maximum_targets": -1,
        "ordering_contract": "faI.PV.a.sgC.PA.aYS.aYU.float32.asc.v1",
    }
}


class GroupHealthOrderingFlagTests(unittest.TestCase):
    def effect(self):
        return dict(effect_class=330, native_effect_flags=[8])

    def test_actual_native_group_identity_accepted_with_original_phase_guards(self):
        with patch(
            "wakfu_server.combat_target_ordering.native_health_target_ordering",
            return_value=NATIVE,
        ):
            validate_group_registration_flags(
                [8], active=True, effect=self.effect(), reference=187193
            )
            validate_group_registration_flags(
                [8],
                active=False,
                constructor=True,
                effect=self.effect(),
                reference=187193,
            )
            with self.assertRaisesRegex(ValueError, "requires active combat"):
                validate_group_registration_flags(
                    [8], active=False, effect=self.effect(), reference=187193
                )

    def test_flags_only_callers_cannot_assert_native_ordering_authority(self):
        for flags in ([8], [8, 26]):
            with self.subTest(flags=flags), self.assertRaisesRegex(
                ValueError, "Unaudited"
            ):
                validate_group_registration_flags(flags, active=True)

    def test_mismatched_reference_class_flags_and_marker_reject(self):
        with patch(
            "wakfu_server.combat_target_ordering.native_health_target_ordering",
            return_value=NATIVE,
        ):
            for effect, reference in (
                (self.effect(), 999999),
                (dict(effect_class=349, native_effect_flags=[8]), 187193),
                (dict(effect_class=330, native_effect_flags=[8, 26]), 187193),
            ):
                with self.subTest(
                    effect=effect, reference=reference
                ), self.assertRaisesRegex(ValueError, "identity"):
                    validate_group_registration_flags(
                        effect["native_effect_flags"],
                        active=True,
                        effect=effect,
                        reference=reference,
                    )
            with self.assertRaisesRegex(ValueError, "differ"):
                validate_group_registration_flags(
                    [8, 26], active=True, effect=self.effect(), reference=187193
                )
        unqualified = deepcopy(NATIVE)
        del unqualified["187193"]["ordering_contract"]
        with patch(
            "wakfu_server.combat_target_ordering.native_health_target_ordering",
            return_value=unqualified,
        ), self.assertRaisesRegex(ValueError, "identity"):
            validate_group_registration_flags(
                [8], active=True, effect=self.effect(), reference=187193
            )

    def test_native_ordering_metadata_does_not_allow_unrelated_unknown_flags(self):
        altered = deepcopy(NATIVE)
        altered["187193"]["native_effect_flags"] = [8, 999]
        effect = dict(effect_class=330, native_effect_flags=[8, 999])
        with patch(
            "wakfu_server.combat_target_ordering.native_health_target_ordering",
            return_value=altered,
        ), self.assertRaisesRegex(ValueError, "999"):
            validate_group_registration_flags(
                [8, 999], active=True, effect=effect, reference=187193
            )

    def test_invalid_native_signed_target_cap_rejects(self):
        altered = deepcopy(NATIVE)
        altered["187193"]["maximum_targets"] = 128
        with patch(
            "wakfu_server.combat_target_ordering.native_health_target_ordering",
            return_value=altered,
        ), self.assertRaisesRegex(ValueError, "signed byte"):
            validate_group_registration_flags(
                [8], active=True, effect=self.effect(), reference=187193
            )
