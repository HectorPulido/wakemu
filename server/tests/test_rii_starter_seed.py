"""The Rii starter is an idempotent supply, not quest completion."""
import unittest
from unittest.mock import Mock, patch

from wakfu_server.achievements import rii_starter_seed


class RiiStarterSeedTests(unittest.TestCase):
    def setUp(self):
        self.db = Mock()
        self.db.execute.return_value.fetchall.return_value = []
        self.character = {"id": 17, "account_id": 19}
        self.store = Mock()

    def test_missing_seed_is_granted_once_through_inventory_authority(self):
        with patch.object(
            rii_starter_seed.storage, "record_event", side_effect=[True, False]
        ) as record, patch.object(
            rii_starter_seed.rewards, "_item", return_value=[(7, b"seed")]
        ) as grant:
            result = rii_starter_seed.grant_if_missing(
                self.db, self.store, self.character
            )
            replay = rii_starter_seed.grant_if_missing(
                self.db, self.store, self.character
            )
        self.assertEqual(result, [(7, b"seed")])
        self.assertEqual(replay, [])
        self.assertEqual(record.call_count, 2)
        grant.assert_called_once_with(self.db, self.store, self.character, 31007, 3)

    def test_owned_seed_does_not_create_event_or_grant(self):
        self.db.execute.return_value.fetchall.return_value = [
            {"quantity": 2},
            {"quantity": 2},
        ]
        with patch.object(
            rii_starter_seed.storage, "record_event"
        ) as record, patch.object(rii_starter_seed.rewards, "_item") as grant:
            self.assertEqual(
                rii_starter_seed.grant_if_missing(self.db, self.store, self.character),
                [],
            )
        record.assert_not_called()
        grant.assert_not_called()

    def test_owned_partial_supply_only_receives_the_difference(self):
        self.db.execute.return_value.fetchall.return_value = [{"quantity": 1}]
        with patch.object(
            rii_starter_seed.storage, "record_event", return_value=True
        ) as record, patch.object(
            rii_starter_seed.rewards, "_item", return_value=[]
        ) as grant:
            rii_starter_seed.grant_if_missing(self.db, self.store, self.character)
        grant.assert_called_once_with(self.db, self.store, self.character, 31007, 2)
        self.assertEqual(record.call_args.args[3]["quantity"], 2)

    def test_rejects_changed_native_seed(self):
        with patch("wakfu_server.planting.SEEDS", {31007: {"resource_reference": 999}}):
            with self.assertRaises(ValueError):
                rii_starter_seed.grant_if_missing(self.db, self.store, self.character)
        self.db.execute.assert_not_called()

    def test_refresh_targets_only_delivered_character_and_only_inventory_changes(self):
        with patch(
            "wakfu_server.inventory_move.reload_inventory", return_value={"id": 17}
        ) as reload:
            unchanged = rii_starter_seed.refresh_after_delivery(
                self.store, 19, self.character, [(13832, b"")]
            )
            changed = rii_starter_seed.refresh_after_delivery(
                self.store, 19, self.character, [(12471, b"")]
            )
        self.assertIs(unchanged, self.character)
        self.assertEqual(changed, {"id": 17})
        reload.assert_called_once_with(self.store, 19, self.character)


if __name__ == "__main__":
    unittest.main()
