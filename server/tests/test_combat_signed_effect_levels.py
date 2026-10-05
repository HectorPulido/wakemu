import unittest
from wakfu_server.combat_definitions import effect_profile, state_profile
from wakfu_server.combat_parameters import _float32


class NativeSignedEffectLevelTests(unittest.TestCase):
    def test_original_signed_short_parameter_and_probability(self):
        definition = dict(
            parameter_count=2,
            parameters=[7999.0, 0.0, 10.0, 0.5],
            probability_base=100.0,
            probability_per_level=0.5,
        )
        for level in (-32768, -97, -1, 0, 32767):
            with self.subTest(level=level):
                result = effect_profile(definition, level)
                self.assertEqual(result["parameters"][0], 7999)
                self.assertEqual(result["parameters"][1], int((10 + level * 0.5) // 1))
                self.assertEqual(result["probability"], _float32(100 + level * 0.5))

    def test_non_short_and_state_level_guards_remain(self):
        for level in (-32769, 32768, True, 1.5):
            with self.assertRaises(ValueError):
                effect_profile({}, level)
        with self.assertRaises(ValueError):
            state_profile({}, 1, -97)
