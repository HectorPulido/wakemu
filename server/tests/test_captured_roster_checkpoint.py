"""Owned roster persistence shares transaction and skips identical mutations."""
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from wakfu_server.characters.captured_roster import OwnedCapturedRoster
from wakfu_server.combat_captured_roster_checkpoint import (
    persist_captured_roster_updates,
)


class CapturedCheckpointTests(unittest.TestCase):
    def test_owned_plain_update_saved_with_existing_transaction(self):
        roster = OwnedCapturedRoster(42)
        record = roster.to_record()
        fight = SimpleNamespace(
            actors={42: SimpleNamespace(controlled=True, owner_id=3)},
            native_captured_roster_updates={"42": record},
        )

        class DB:
            def __init__(self):
                self.rows = iter(({"id": 42, "account_id": 3, "breed": 2}, None))

            def execute(self, sql, params):
                return SimpleNamespace(fetchone=lambda: next(self.rows))

        db = DB()
        with patch("wakfu_server.combat_captured_roster_checkpoint.save") as save:
            persist_captured_roster_updates(db, fight)
        save.assert_called_once_with(
            db, {"id": 42, "account_id": 3, "breed": 2}, roster
        )

    def test_identical_checkpoint_does_not_advance_roster_revision(self):
        record = OwnedCapturedRoster(42).to_record()
        fight = SimpleNamespace(
            actors={42: SimpleNamespace(controlled=True, owner_id=3)},
            native_captured_roster_updates={"42": record},
        )
        rows = iter(({"id": 42, "account_id": 3, "breed": 2}, {"record": record}))
        db = SimpleNamespace(
            execute=lambda *args: SimpleNamespace(fetchone=lambda: next(rows))
        )
        with patch("wakfu_server.combat_captured_roster_checkpoint.save") as save:
            persist_captured_roster_updates(db, fight)
        save.assert_not_called()

    def test_foreign_record_rejected_before_database_access(self):
        db = SimpleNamespace(execute=lambda *args: self.fail("Must not touch database"))
        fight = SimpleNamespace(
            actors={},
            native_captured_roster_updates={"42": OwnedCapturedRoster(43).to_record()},
        )
        with self.assertRaises(ValueError):
            persist_captured_roster_updates(db, fight)
