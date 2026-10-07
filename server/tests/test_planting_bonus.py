import unittest
from unittest.mock import patch

from wakfu_server import wire
from wakfu_server.planting_bonus import current


class CurrentPlantingBonusTests(unittest.TestCase):
    def test_native_effect_free_sections_authorize_only_zero_base_bonus(self):
        self.assertEqual(current({"character": {"id": 19}}), 0)

    def test_personal_effect_section_must_remain_proven_empty(self):
        sections = set(wire.EMPTY_SECTIONS)
        sections.remove("PERSONAL_EFFECTS")
        with patch.object(wire, "EMPTY_SECTIONS", sections):
            with self.assertRaisesRegex(ValueError, "requires a provider"):
                current({})

    def test_running_effect_default_must_remain_exact_native_zero_state(self):
        defaults = dict(wire.ENTITY_DEFAULTS)
        defaults["RUNNING_EFFECTS"] = b"\x00"
        with patch.object(wire, "ENTITY_DEFAULTS", defaults):
            with self.assertRaisesRegex(ValueError, "requires a provider"):
                current({})


if __name__ == "__main__":
    unittest.main()
