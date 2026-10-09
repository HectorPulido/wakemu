"""Pure transaction ownership and native breed-specific bootstrap checks."""
import unittest
from wakfu_server.characters.captured_roster import (
    OwnedCapturedRoster,
    CapturedCreature,
    breed_specific_section,
)
from wakfu_server.characters.captured_roster_store import load, save


class FakeResult:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeDatabase:
    def __init__(self, *rows):
        self.rows = list(rows)
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))
        return FakeResult(self.rows.pop(0))


class CapturedRosterStoreTests(unittest.TestCase):
    character = {"id": 42, "account_id": 3, "breed": 2}

    def test_only_osa_loads_roster_table(self):
        db = FakeDatabase()
        self.assertIsNone(load(db, {**self.character, "breed": 9}))
        self.assertEqual(db.calls, [])

    def test_absent_row_initializes_actual_empty_component(self):
        db = FakeDatabase({"relation": "character_captured_rosters"}, None)
        record = load(db, self.character)
        self.assertEqual(record, OwnedCapturedRoster(42).to_record())
        self.assertEqual(db.calls[1][1], (42,))
        self.assertEqual(
            breed_specific_section({**self.character, "captured_roster": record}),
            bytes.fromhex("010000"),
        )

    def test_hydration_rejects_foreign_owner(self):
        with self.assertRaises(ValueError):
            load(
                FakeDatabase(
                    {"relation": "character_captured_rosters"},
                    {"record": OwnedCapturedRoster(43).to_record(), "revision": 1},
                ),
                self.character,
            )

    def test_save_locks_actual_owner_then_persists_revision(self):
        db = FakeDatabase({"id": 42}, {"revision": 7})
        self.assertEqual(save(db, self.character, OwnedCapturedRoster(42)), 7)
        self.assertIn("FOR UPDATE", db.calls[0][0])
        self.assertEqual(db.calls[0][1], (42, 3))
        self.assertEqual(db.calls[1][1][1].obj["owner_id"], 42)

    def test_rejected_owner_never_writes(self):
        db = FakeDatabase(None)
        with self.assertRaises(ValueError):
            save(db, self.character, OwnedCapturedRoster(42))
        self.assertEqual(len(db.calls), 1)
        db = FakeDatabase()
        with self.assertRaises(ValueError):
            save(db, self.character, OwnedCapturedRoster(43))
        self.assertEqual(db.calls, [])

    def test_bootstrap_writes_resolved_roster_not_fixture(self):
        roster = OwnedCapturedRoster(
            42,
            (CapturedCreature(0, 7, "own"),) + (None,) * 9,
            (True,) + (False,) * 9,
            0,
        )
        character = {**self.character, "captured_roster": roster.to_record()}
        self.assertEqual(
            breed_specific_section(character), b"\x01" + roster.to_native().encode()
        )
        self.assertEqual(breed_specific_section({**character, "breed": 9}), b"\x00")

    def test_unapplied_schema_keeps_bootstrap_compatible_and_component_unknown(self):
        record = load(FakeDatabase({"relation": None}), self.character)
        self.assertIsNone(record)
        self.assertEqual(
            breed_specific_section({**self.character, "captured_roster": record}),
            b"\x00",
        )

    def test_osa_unhydrated_fails_instead_of_inventing_roster(self):
        with self.assertRaises(ValueError):
            breed_specific_section(self.character)


if __name__ == "__main__":
    unittest.main()
