import unittest
from wakfu_server.combat_native_events import (
    activation_order_key,
    subscription_selection,
    subscription_actor_ids,
    validate_group_registration_flags,
)


class NativeEventSelectionTests(unittest.TestCase):
    def select(self, **kw):
        args = dict(
            masks=[[1001], [], [], [], [], [], []],
            event_ids=[1001],
            channel=1,
            global_subscription=False,
            reversed_subscription=False,
            flags=[],
            source_present=True,
        )
        args.update(kw)
        return subscription_selection(**args)

    def test_native_flag_one_matrix(self):
        for flag in (False, True):
            for silent in (False, True):
                self.assertEqual(
                    self.select(
                        flags=[1] if flag else [], source_suppresses_level_one=silent
                    ),
                    None if silent and not flag else "activate",
                )

    def test_flag_one_does_not_bypass_other_suppression(self):
        for key in (
            "source_suppresses_all",
            "source_is_self",
            "source_parent_is_self",
            "source_suppressed",
        ):
            self.assertIsNone(self.select(flags=[1], **{key: True}))

    def test_native_mask_channel_tables(self):
        for channel, index in ((1, 0), (2, 1), (3, 3), (4, 2), (5, 4), (6, 5)):
            masks = [[] for _ in range(7)]
            masks[index] = [1001]
            self.assertEqual(
                self.select(channel=channel, masks=masks),
                "remove" if index == 2 else "activate",
            )
        self.assertEqual(
            self.select(channel=10, reversed_subscription=True), "activate"
        )
        self.assertEqual(self.select(channel=11, global_subscription=True), "activate")
        self.assertIsNone(self.select(channel=1, reversed_subscription=True))

    def test_unknown_flags_still_reject(self):
        validate_group_registration_flags([1, 17], active=True)
        validate_group_registration_flags([5], active=True)
        validate_group_registration_flags([9], active=True)
        validate_group_registration_flags([15, 16, 17], active=True)
        with self.assertRaises(ValueError):
            validate_group_registration_flags([6], active=True)
        with self.assertRaises(ValueError):
            validate_group_registration_flags([1], active=False)

    def test_authenticated_eYy865_children_preserve_parent_flags(self):
        for flags in ([4, 22], [4, 22, 29]):
            definition = {
                "effect_class": 865,
                "native_effect_flags": list(flags),
                "children": [392622, 392984],
            }
            with self.subTest(flags=flags):
                validate_group_registration_flags(
                    flags, active=True, effect=definition, reference=5722
                )

    def test_eYy865_flag_gate_rejects_incomplete_or_forged_metadata(self):
        valid_flags = [4, 22, 29]
        base = {
            "effect_class": 865,
            "native_effect_flags": valid_flags,
            "children": [392622, 392984],
        }
        invalid = (
            {**base, "native_effect_flags": [4, 22]},
            {**base, "effect_class": 864},
            {**base, "children": [392622]},
            {**base, "children": [392622, 0]},
            {**base, "native_effect_flags": [4, 22, 29, 777]},
        )
        for definition in invalid:
            with self.subTest(definition=definition):
                with self.assertRaises(ValueError):
                    validate_group_registration_flags(
                        valid_flags,
                        active=True,
                        effect=definition,
                        reference=5722,
                    )

        with self.assertRaises(ValueError):
            validate_group_registration_flags(
                valid_flags, active=True, effect=base, reference=0
            )

    def test_actual_ezr_enum_rebinding_matches_native_probe(self):
        args = dict(
            original_caster=81,
            original_target=82,
            manager_actor=83,
            source_caster=71,
            source_target=72,
            source_present=True,
        )
        for code, expected in enumerate((82, 82, 83, 81, 71, 72)):
            self.assertEqual(
                subscription_actor_ids(target_code=code, caster_code=None, **args),
                (81, expected),
            )
        for code, expected in enumerate((81, 81, 83, 82, 71, 72)):
            self.assertEqual(
                subscription_actor_ids(target_code=1, caster_code=code, **args),
                (expected, 82),
            )

    def test_activation_priority_precedes_generic_and_uid(self):
        rows = [(0, 9, 901), (5, 12, 904), (5, 10, 903), (5, 10, 902)]
        self.assertEqual(
            sorted(
                rows,
                key=lambda x: activation_order_key(
                    priority=x[0], generic_effect=x[1], uid=x[2]
                ),
            ),
            [(5, 10, 902), (5, 10, 903), (5, 12, 904), (0, 9, 901)],
        )


if __name__ == "__main__":
    unittest.main()
