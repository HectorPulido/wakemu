"""Retained elemental damage preserves audited single-target semantics."""

import unittest

from wakfu_server.combat.combat_native_events import validate_group_registration_flags


class NativeSingleTargetRetentionTests(unittest.TestCase):
    def test_elemental_damage_listener_accepts_its_native_single_target_flag(self):
        for family in (1, 2, 3, 4, 5):
            with self.subTest(family=family):
                validate_group_registration_flags(
                    [22],
                    active=True,
                    effect={"effect_class": family, "native_effect_flags": [22]},
                    reference=186995 if family == 4 else 9066,
                )

    def test_missing_authority_other_families_and_flag_mismatches_reject(self):
        alternatives = (
            {},
            {
                "effect": {"effect_class": 330, "native_effect_flags": [22]},
                "reference": 9066,
            },
            {
                "effect": {"effect_class": 1, "native_effect_flags": []},
                "reference": 9066,
            },
        )
        for arguments in alternatives:
            with self.subTest(arguments=arguments):
                with self.assertRaisesRegex(ValueError, "Unaudited native group"):
                    validate_group_registration_flags([22], active=True, **arguments)

    def test_unknown_flags_and_inactive_combat_remain_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unaudited native group"):
            validate_group_registration_flags(
                [22, 38],
                active=True,
                effect={"effect_class": 1, "native_effect_flags": [22, 38]},
                reference=9066,
            )
        with self.assertRaisesRegex(ValueError, "active combat"):
            validate_group_registration_flags(
                [22],
                active=False,
                effect={"effect_class": 1, "native_effect_flags": [22]},
                reference=9066,
            )
