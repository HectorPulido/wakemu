import unittest

from wakfu_server import guild_native_validators as native


class GuildNativeValidatorsTests(unittest.TestCase):
    def test_blazon_catalog_boundaries_round_trip_without_truncation(self):
        # Values copied from the native JVM oracle, including each picker maximum.
        fixtures = (
            ((0, 0, 0, 0), 0),
            ((1, 2, 3, 4), 281483566841860),
            ((376, 45, 103, 103), 105834784523485287),
        )
        for parts, encoded in fixtures:
            with self.subTest(parts=parts):
                self.assertEqual(
                    native.encode_blazon(
                        emblem_id=parts[0],
                        background_id=parts[1],
                        background_color=parts[2],
                        emblem_color=parts[3],
                    ),
                    encoded,
                )
                self.assertEqual(
                    native.decode_blazon(encoded),
                    dict(
                        emblem_id=parts[0],
                        background_id=parts[1],
                        background_color=parts[2],
                        emblem_color=parts[3],
                    ),
                )

    def test_blazon_rejects_unknown_components_and_non_signed64_values(self):
        for parts in (
            (377, 0, 0, 0),
            (0, 46, 0, 0),
            (0, 0, 104, 0),
            (0, 0, 0, 104),
            (True, 0, 0, 0),
        ):
            with self.subTest(parts=parts), self.assertRaises(ValueError):
                native.encode_blazon(
                    emblem_id=parts[0],
                    background_id=parts[1],
                    background_color=parts[2],
                    emblem_color=parts[3],
                )
        for value in (-1, 1 << 63, True, "0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                native.decode_blazon(value)

    def test_permission_bits_and_fixed_rank_hierarchy(self):
        bits = native.permission_bits()
        self.assertEqual(len(bits), 27)
        self.assertEqual(min(bits.values()), 1)
        self.assertEqual(max(bits.values()), 27)
        all_permissions = native.permission_mask(bits)
        self.assertEqual(all_permissions, 268435454)
        self.assertEqual(
            native.validate_rank_mask(all_permissions, highest=True), all_permissions
        )
        self.assertEqual(native.validate_rank_mask(0, lowest=True), 0)

        for names in (("NOT_A_NATIVE_GUILD_PERMISSION",), (True,)):
            with self.subTest(names=names), self.assertRaises(ValueError):
                native.permission_mask(names)
        for mask, kwargs in (
            (1 << 28, {}),
            (True, {}),
            (-1, {}),
            (0, {"highest": True}),
            (all_permissions, {"lowest": True}),
            (0, {"highest": True, "lowest": True}),
            (0, {"highest": 1}),
        ):
            with self.subTest(mask=mask, kwargs=kwargs), self.assertRaises(ValueError):
                native.validate_rank_mask(mask, **kwargs)

    def test_name_normalization_and_structural_result_match_native_fixture(self):
        # Oracle fixture: raw name fails case validation; native normalization
        # produces a structurally valid title-cased name.
        raw = "èïXùKCwig fNuVàjXymdéHùjTïjt"
        normalized = "Èïxùkcwig Fnuvàjxymdéhùjtïjt"
        self.assertEqual(native.normalize_name(raw), normalized)
        self.assertEqual(native.structural_name_error(raw), "ERROR_NAME_WITH_BAD_CASE")
        self.assertEqual(native.validate_name_structure(raw), normalized)
        self.assertEqual(
            native.validate_name_structure(normalized, normalize=False), normalized
        )

        # A separate native oracle fixture covers exact short-name rejection.
        self.assertEqual(native.structural_name_error("VBYR"), "ERROR_NAME_TOO_SHORT")
        with self.assertRaisesRegex(ValueError, "ERROR_NAME_TOO_SHORT"):
            native.validate_name_structure("VBYR", normalize=False)
        with self.assertRaisesRegex(ValueError, "A native guild name must be text"):
            native.normalize_name(None)


if __name__ == "__main__":
    unittest.main()
