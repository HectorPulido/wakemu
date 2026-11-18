"""Original neutral faW scene prototypes stay inert and non-fighters."""

from copy import deepcopy
import unittest

from wakfu_server.combat_effect_area import native_effect_areas
from wakfu_server.combat_encounter_glyph_bootstrap import (
    validate_fake_fighter_prototype,
)


class NativeInertSceneAreaTests(unittest.TestCase):
    def test_original_769_771_are_inert_point_prototypes_with_original_flags(self):
        areas = native_effect_areas()
        for reference in (769, 770, 771):
            with self.subTest(reference=reference):
                definition = areas[str(reference)]
                constructor = validate_fake_fighter_prototype(definition, level=0)
                self.assertEqual(definition["reference"], reference)
                self.assertEqual(definition["native_class"], "bcQ")
                self.assertEqual(definition["native_shape_description"], "point")
                self.assertEqual(definition["raw_bde"], -1)
                self.assertEqual(definition["effect_ids"], [])
                self.assertEqual(definition["native_area_properties"], [])
                self.assertEqual(definition["raw_bdh"][1], -1.0)
                self.assertEqual(constructor["kind"], 0)
                self.assertEqual(constructor["characteristic_ids"], ())
                self.assertFalse(constructor["running_effect_manager"])
                self.assertFalse(constructor["owner_activation"])
                self.assertFalse(constructor["other_activation"])

        # This raw flag is true for original prototype 770 and must be
        # preserved as source data rather than treated as active behavior.
        self.assertTrue(areas["770"]["raw_bdi"])

    def test_rejects_level_activation_hp_and_invented_effect_roots(self):
        source = native_effect_areas()["769"]
        invalid = []

        level = deepcopy(source)
        invalid.append((level, 1))

        owner_activation = deepcopy(source)
        owner_activation["raw_bdh"][5] = 1.0
        invalid.append((owner_activation, 0))

        other_activation = deepcopy(source)
        other_activation["raw_bdh"][6] = 1.0
        invalid.append((other_activation, 0))

        invented_hp = deepcopy(source)
        invented_hp["raw_bdh"][9] = 1.0
        invalid.append((invented_hp, 0))

        invented_root = deepcopy(source)
        invented_root["effect_ids"] = [118950]
        invalid.append((invented_root, 0))

        for definition, level in invalid:
            with self.subTest(level=level, definition=definition):
                with self.assertRaises(ValueError):
                    validate_fake_fighter_prototype(definition, level=level)


if __name__ == "__main__":
    unittest.main()
