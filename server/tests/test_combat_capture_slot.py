import unittest
from wakfu_server.characters.captured_roster import (
    OwnedCapturedRoster,
    CapturedCreature,
)
from wakfu_server.combat_capture_slot import add_fresh_capture


class CaptureSlotTests(unittest.TestCase):
    def test_first_capture_selects_lowest_empty_slot_and_preserves_source(self):
        source = OwnedCapturedRoster(7, selected_slot=9)
        slot, result = add_fresh_capture(
            source, dict(profile_id=1152, native_profile_name="")
        )
        self.assertEqual(slot, 0)
        self.assertEqual(result.selected_slot, 0)
        self.assertTrue(result.available[0])
        self.assertEqual(source.free_slots, 10)

    def test_new_descriptor_allows_equal_profiles_and_preserves_existing_selection(
        self,
    ):
        source = OwnedCapturedRoster(
            7,
            (CapturedCreature(0, 1152, "x"),) + (None,) * 9,
            (False,) * 10,
            selected_slot=0,
        )
        slot, result = add_fresh_capture(
            source, dict(profile_id=1152, native_profile_name="")
        )
        self.assertEqual(slot, 1)
        self.assertEqual(result.selected_slot, 0)
        self.assertFalse(result.available[0])
        self.assertTrue(result.available[1])

    def test_full_component_returns_minus_one_without_mutation(self):
        source = OwnedCapturedRoster(
            7, tuple(CapturedCreature(i, 1152, "") for i in range(10))
        )
        slot, result = add_fresh_capture(
            source, dict(profile_id=1152, native_profile_name="")
        )
        self.assertEqual(slot, -1)
        self.assertIs(result, source)


if __name__ == "__main__":
    unittest.main()
