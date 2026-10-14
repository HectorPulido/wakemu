"""Group ZONE_EFFECT metadata preserves native damage consumers and guards."""
import copy
import unittest

from wakfu_server.combat.combat_native_events import validate_group_registration_flags
from wakfu_server.combat.combat_damage_events import damage_event_ids
from wakfu_server.combat.combat_damage_parameters import damage_mastery_context


class NativeGroupAreaFlagMetadataTests(unittest.TestCase):
    def test_native_group_flag4_metadata_is_accepted_without_mutation(self):
        for family, reference in ((330, 181255), (844, 390596), (844, 390613)):
            effect = {"effect_class": family, "native_effect_flags": [4]}
            before = copy.deepcopy(effect)
            validate_group_registration_flags(
                [4], active=True, effect=effect, reference=reference
            )
            validate_group_registration_flags(
                [4], active=False, constructor=True, effect=effect, reference=reference
            )
            self.assertEqual(effect, before)

    def test_known_flags_can_coexist_but_unrelated_unknown_flag_still_rejects(self):
        effect = {"effect_class": 330, "native_effect_flags": [1, 4, 17]}
        validate_group_registration_flags(
            [1, 4, 17], active=True, effect=effect, reference=181255
        )
        effect["native_effect_flags"] = [4, 6]
        with self.assertRaisesRegex(ValueError, "Unaudited.*6"):
            validate_group_registration_flags(
                [4, 6], active=True, effect=effect, reference=181255
            )

    def test_flag_only_non_group_or_mismatched_authority_is_rejected(self):
        rows = [
            {},
            {
                "effect": {"effect_class": 330, "native_effect_flags": [4]},
                "reference": 0,
            },
            {
                "effect": {"effect_class": 330, "native_effect_flags": [4]},
                "reference": True,
            },
            {
                "effect": {"effect_class": 1, "native_effect_flags": [4]},
                "reference": 181255,
            },
            {
                "effect": {"effect_class": 330, "native_effect_flags": [17]},
                "reference": 181255,
            },
            {
                "effect": {"effect_class": 330, "native_effect_flags": [4.0]},
                "reference": 181255,
            },
            {
                "effect": {"effect_class": 330, "native_effect_flags": None},
                "reference": 181255,
            },
        ]
        for arguments in rows:
            with self.subTest(arguments=arguments), self.assertRaisesRegex(
                ValueError, "Unaudited"
            ):
                validate_group_registration_flags([4], active=True, **arguments)

    def test_malformed_flags_and_inactive_nonconstructor_still_reject(self):
        effect = {"effect_class": 330, "native_effect_flags": [4]}
        for flags in ([True], [4.0], ["4"]):
            with self.assertRaisesRegex(ValueError, "Explicit native"):
                validate_group_registration_flags(
                    flags, active=True, effect=effect, reference=181255
                )
        with self.assertRaisesRegex(ValueError, "requires active combat"):
            validate_group_registration_flags(
                [4], active=False, effect=effect, reference=181255
            )

    def test_existing_damage_flag4_still_emits_native_area_event(self):
        effect = {
            "effect_class": 1,
            "native_effect_flags": [4],
            "target_masks": [[], [], [], [], [], [], []],
        }
        before = copy.deepcopy(effect)
        events = damage_event_ids(
            effect,
            container_type=None,
            phase=1,
            blocked=False,
            localization="FRONT",
            context_is_native_fight=True,
        )
        self.assertIn(2215, events)
        mastery = damage_mastery_context(
            [4],
            source_xy=(0, 0),
            target_xy=(1, 0),
            source_radius=0,
            target_radius=0,
            source_total_hp=100,
            source_total_max_hp=100,
        )
        self.assertTrue(mastery["area"])
        self.assertFalse(mastery["single_target"])
        self.assertEqual(effect, before)


if __name__ == "__main__":
    unittest.main()
