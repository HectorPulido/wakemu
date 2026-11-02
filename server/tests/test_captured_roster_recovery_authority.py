"""Historical snapshots cannot override the current owned capture component."""
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from wakfu_server.characters.captured_roster import (
    CapturedCreature,
    OwnedCapturedRoster,
)
from wakfu_server import captured_roster_recovery


class CapturedRecoveryAuthorityTests(unittest.TestCase):
    def setUp(self):
        slots = [None] * 10
        slots[3] = CapturedCreature(3, 4, "Current owned name")
        self.roster = OwnedCapturedRoster(12, tuple(slots), (False,) * 10, 3)
        self.character = dict(
            id=12, account_id=7, breed=2, captured_roster=self.roster.to_record()
        )

    def test_aborted_sql_owner_restores_current_component_despite_bad_history(self):
        for snapshot in (
            None,
            [],
            {},
            {"actors": []},
            {"actors": {"12": {"owner_id": 99}}},
            {"native_captured_rosters": {"12": "invalid"}},
        ):
            with self.subTest(snapshot=snapshot):
                db = Mock()
                db.execute.return_value.fetchone.return_value = dict(
                    id=31,
                    status="aborted",
                    snapshot=snapshot,
                )
                with patch.object(captured_roster_recovery, "save") as save:
                    self.assertTrue(
                        captured_roster_recovery.reconcile_aborted(db, self.character)
                    )
                save.assert_called_once_with(
                    db, self.character, replace(self.roster, available=(True,) * 10)
                )
                query, parameters = db.execute.call_args.args
                self.assertEqual(parameters, (12, 7))
                self.assertNotIn("fight_checkpoints", query)
                self.assertIn("NOT EXISTS", query)
                self.assertIn("running.status IN ('placement','active')", query)
                self.assertEqual(
                    self.character["captured_roster"], self.roster.to_record()
                )

    def test_missing_or_nonaborted_participant_never_changes_owned_roster(self):
        for witness in (
            None,
            {"status": "placement"},
            {"status": "active"},
            {"status": "finished"},
        ):
            with self.subTest(witness=witness):
                db = Mock()
                db.execute.return_value.fetchone.return_value = witness
                with patch.object(captured_roster_recovery, "save") as save:
                    self.assertFalse(
                        captured_roster_recovery.reconcile_aborted(db, self.character)
                    )
                save.assert_not_called()

    def test_repaired_current_roster_is_idempotent_and_foreign_current_owner_rejected(
        self,
    ):
        db = Mock()
        current = dict(
            self.character,
            captured_roster=replace(self.roster, available=(True,) * 10).to_record(),
        )
        with patch.object(captured_roster_recovery, "save") as save:
            self.assertFalse(captured_roster_recovery.reconcile_aborted(db, current))
            foreign = dict(
                self.character,
                captured_roster=replace(self.roster, owner_id=99).to_record(),
            )
            with self.assertRaises(ValueError):
                captured_roster_recovery.reconcile_aborted(db, foreign)
        save.assert_not_called()
        db.execute.assert_not_called()
