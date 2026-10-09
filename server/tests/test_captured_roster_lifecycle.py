"""Owned PC departure reset preserves descriptors and stays checkpoint-plain."""
import json
from types import SimpleNamespace
import unittest
from wakfu_server.characters.captured_roster import (
    CapturedCreature,
    OwnedCapturedRoster,
    selected_availability_status,
    roster_from_character,
)
from wakfu_server.combat_captured_roster_lifecycle import (
    reset_availability,
    restore_departing_roster,
)


class CapturedRosterLifecycleTests(unittest.TestCase):
    def roster(self):
        slots = [None] * 10
        slots[3] = CapturedCreature(3, 5347, "Owned name")
        return OwnedCapturedRoster(7, tuple(slots), (False,) * 10, 3)

    def test_native_all_ten_flags_reset_without_descriptor_or_selection_changes(self):
        before = self.roster()
        after = reset_availability(before)
        self.assertEqual(after.available, (True,) * 10)
        self.assertEqual(after.slots, before.slots)
        self.assertEqual(after.selected_slot, 3)
        self.assertEqual(after.to_native().encode(), before.to_native().encode())
        self.assertEqual(selected_availability_status(before), -2)
        self.assertEqual(selected_availability_status(after), 0)
        self.assertEqual(before.available, (False,) * 10)

    def test_departure_uses_latest_owned_overlay_and_queues_plain_record(self):
        roster = self.roster()
        character = dict(
            id=7,
            account_id=3,
            breed=2,
            captured_roster=OwnedCapturedRoster(7).to_record(),
        )
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(controlled=True, owner_id=3)},
            native_captured_rosters={"7": roster.to_record()},
            native_captured_roster_updates={},
        )
        self.assertTrue(restore_departing_roster(fight, character))
        self.assertEqual(
            fight.native_captured_roster_updates["7"]["slots"][3]["name"], "Owned name"
        )
        self.assertEqual(
            fight.native_captured_roster_updates["7"]["available"], [True] * 10
        )
        json.dumps(fight.native_captured_rosters, allow_nan=False)
        self.assertEqual(character["captured_roster"]["slots"], [None] * 10)

    def test_new_fight_hydration_restores_selected_available_slot(self):
        character = dict(
            id=7, account_id=3, breed=2, captured_roster=self.roster().to_record()
        )
        departing = SimpleNamespace(
            actors={7: SimpleNamespace(controlled=True, owner_id=3)}
        )
        self.assertEqual(
            selected_availability_status(roster_from_character(character)), -2
        )
        restore_departing_roster(departing, character)
        # The existing checkpoint transaction persists this plain record; a new
        # fight hydrates it without retaining the previous battle overlay.
        hydrated = {
            **character,
            "captured_roster": departing.native_captured_roster_updates["7"],
        }
        self.assertEqual(
            selected_availability_status(roster_from_character(hydrated)), 0
        )
        self.assertEqual(
            roster_from_character(hydrated).selected_creature,
            self.roster().selected_creature,
        )

    def test_foreign_component_rejects_before_mutating_fight(self):
        character = dict(
            id=7, account_id=3, breed=2, captured_roster=self.roster().to_record()
        )
        invalid = {"7": OwnedCapturedRoster(9).to_record()}
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(controlled=True, owner_id=3)},
            native_captured_rosters=invalid,
        )
        with self.assertRaises(ValueError):
            restore_departing_roster(fight, character)
        self.assertIs(fight.native_captured_rosters, invalid)
        self.assertFalse(hasattr(fight, "native_captured_roster_updates"))


if __name__ == "__main__":
    unittest.main()
