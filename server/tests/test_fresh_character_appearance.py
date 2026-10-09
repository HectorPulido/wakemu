import unittest
from protocol_codec import APPEARANCE_FIELDS, decode_appearance
from wakfu_server.characters.fresh_appearance import fresh_character_appearance
from wakfu_server.wire import appearance_section


class FreshCharacterAppearanceTests(unittest.TestCase):
    def test_owned_creation_defaults_preserve_actual_sex(self):
        for sex in (0, 1):
            appearance = fresh_character_appearance(sex)
            self.assertEqual(
                [appearance[key] for key in APPEARANCE_FIELDS[:3]], [-1] * 3
            )
            self.assertEqual(
                (appearance["sex"], appearance["faceIndex"], appearance["clothIndex"]),
                (sex, 0, 0),
            )
            self.assertEqual(
                appearance_section(appearance),
                appearance_section(
                    dict(
                        zip(APPEARANCE_FIELDS[:3], (-1,) * 3),
                        sex=sex,
                        faceIndex=0,
                        clothIndex=0,
                    )
                ),
            )

    def test_invalid_creation_values_reject(self):
        for value in (-1, 2, True, None):
            with self.assertRaises(ValueError):
                fresh_character_appearance(value)
        with self.assertRaises(ValueError):
            fresh_character_appearance(0, cloth=32)

    def test_real_ds_request_roundtrip_preserves_constructor_operands(self):
        for sex in (0, 1):
            appearance = fresh_character_appearance(sex)
            section = appearance_section(appearance)
            self.assertEqual(int.from_bytes(section[:2], "big"), len(section) - 2)
            decoded = decode_appearance(section[2:])
            self.assertTrue(
                all(decoded[key] == value for key, value in appearance.items())
            )
            self.assertEqual(appearance_section(decoded), section)
