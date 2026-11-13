"""Elemental lesson settlement requires owned completed fight evidence."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server.achievements import rii_element_encounter as encounter
from wakfu_server.achievements import mission_progress, storage, wire


class ElementalSettlementTests(unittest.TestCase):
    def setUp(self):
        self.fight = SimpleNamespace(
            id=12,
            phase="finished",
            winner=0,
            actors={7: SimpleNamespace(team=0), -30: SimpleNamespace(team=1)},
            rii_element_lesson_contract={"owner": 7, "target": -30, "hits": 4},
        )
        self.monsters = [{"id": -30, "ref": 5466}]
        self.members = [
            {"character_id": 7, "account_id": 3, "session_generation": "gen"}
        ]
        self.character = {"id": 7, "account_id": 3}
        self.db = Mock()
        self.db.execute.return_value.fetchone.side_effect = [
            {"payload": encounter._payload(7, -30)},
            {"status": "finished", "fight_kind": "pve", "team": 0},
            {"data": {"native": {"d": 5143}}},
        ]
        self.store = Mock()
        self.store.character.return_value = self.character
        self.store.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.before = {"running": [5143], "completed": [], "objectives": [10574]}
        self.after = {"running": [5143], "completed": [], "objectives": [10574, 10575]}

    def test_owned_winner_persists_exact_objective(self):
        with patch.object(
            storage, "load_locked", return_value=self.before
        ), patch.object(
            storage, "record_event", return_value=True
        ) as receipt, patch.object(
            storage, "store"
        ) as save, patch.object(
            mission_progress,
            "advance_objective",
            return_value=(self.after, [], [10575], []),
        ) as advance, patch.object(
            wire, "changes", return_value=[(13832, b"ok")]
        ):
            result = encounter.settle_participants(
                self.db, self.store, self.fight, self.members, self.monsters
            )
        self.assertEqual(result, {3: [(13832, b"ok")]})
        self.assertEqual(advance.call_args.args[2], 10575)
        self.assertEqual(receipt.call_args.args[2], "rii-element-objective:10575")
        save.assert_called_once_with(self.db, 7, self.after)

    def test_duplicate_objective_is_idempotent(self):
        self.before["objectives"].append(10575)
        with patch.object(
            storage, "load_locked", return_value=self.before
        ), patch.object(storage, "record_event") as receipt:
            result = encounter.settle_participants(
                self.db, self.store, self.fight, self.members, self.monsters
            )
        self.assertEqual(result, {})
        receipt.assert_not_called()

    def test_missing_prior_objective_propagates_error_for_outer_rollback(self):
        self.before["objectives"] = []
        with patch.object(
            storage, "load_locked", return_value=self.before
        ), patch.object(
            mission_progress,
            "advance_objective",
            side_effect=ValueError("prerequisite"),
        ), patch.object(
            storage, "store"
        ) as save:
            with self.assertRaises(ValueError):
                encounter.settle_participants(
                    self.db, self.store, self.fight, self.members, self.monsters
                )
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
