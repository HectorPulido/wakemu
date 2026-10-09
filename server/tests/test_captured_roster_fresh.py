import unittest
from wakfu_server.characters.captured_roster import (
    roster_from_character,
    selected_availability_status,
)
from wakfu_server.characters.captured_roster_fresh import (
    initialize_fresh_character_roster,
)


class FreshCapturedRosterTests(unittest.TestCase):
    def test_original_fresh_component_has_ten_null_slots(self):
        character = initialize_fresh_character_roster(dict(id=7, breed=2))
        roster = roster_from_character(character)
        self.assertEqual(roster.slots, (None,) * 10)
        self.assertEqual(roster.available, (False,) * 10)
        self.assertEqual((roster.selected_slot, roster.free_slots), (0, 10))
        self.assertEqual(selected_availability_status(roster), -1)

    def test_non_osa_constructor_does_not_allocate_component(self):
        character = initialize_fresh_character_roster(dict(id=7, breed=15))
        self.assertNotIn("captured_roster", character)
        self.assertIsNone(roster_from_character(character))

    def test_hydrated_or_missing_persistence_cannot_be_reinitialized(self):
        for value in (None, {}):
            with self.assertRaises(ValueError):
                initialize_fresh_character_roster(
                    dict(id=7, breed=2, captured_roster=value)
                )
        with self.assertRaises(ValueError):
            roster_from_character(dict(id=7, breed=2))
