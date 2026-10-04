import unittest

from wakfu_server.combat_parameters import parameter_value
from wakfu_server.combat_parameters import _float32
from wakfu_server.combat_definitions import effect_profile
from wakfu_server.spell_audit import catalog


class NativeEffectParameterTests(unittest.TestCase):
    def test_all_class_effect_parameters_match_client_at_every_exported_level(self):
        for reference, effect in catalog()["effects"].items():
            for level, expected in enumerate(effect["parameters_by_level"], 1):
                actual = [
                    parameter_value(effect["parameters"], i, level)
                    for i in range(effect["parameter_count"])
                ]
                if actual != expected:
                    self.fail(
                        f"Native effect {reference}, level {level}: {actual} != {expected}"
                    )

    def test_invalid_native_levels_and_indices_are_rejected(self):
        for index, level in ((-1, 1), (1, 1), (0, 32768), (0, True)):
            with self.assertRaises(ValueError):
                parameter_value([4, 0.44], index, level)

    def test_effect_probability_matches_native_client_across_levels(self):
        for reference, definition in catalog()["effects"].items():
            for level, expected in enumerate(definition["probabilities"], 1):
                actual = effect_profile(definition, level)["probability"]
                if actual != _float32(expected):
                    self.fail(
                        f"Effect {reference}, level {level}: {actual} != {expected}"
                    )


if __name__ == "__main__":
    unittest.main()
