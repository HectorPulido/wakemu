"""Daily hunter choice stays separate from victory-based auto-acceptance."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from wakfu_server.maps import daily_hunter_npc as daily


class DailyHunterNpcTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.db.execute.return_value.fetchone.return_value = None
        self.store = MagicMock()
        self.character = {"id": 9, "account_id": 2, "level": 36}
        self.offer = {"category_id": 703, "node_id": 3789, "choice_id": 9494}
        self.choice = {
            "category_id": 703,
            "definition_id": 4142,
            "version": 1,
            "utc_day": 22000,
            "eligible": True,
        }
        self.source = {
            "interpretation_policy": daily.recurring.DAILY_POLICY,
            "daily_target_authority": {"category_id": 703},
        }
        self.contract = SimpleNamespace(period=lambda now: 27)
        patches = [
            patch.object(daily, "enabled", return_value=True),
            patch.object(
                daily.selection, "select_for_character", return_value=(self.choice,)
            ),
            patch.object(
                daily.recurring,
                "_load",
                return_value=(self.source, self.contract, None),
            ),
            patch.object(daily.recurring, "_now", return_value=1234),
            patch.object(
                daily.storage,
                "load_locked",
                return_value={"running": [], "completed": []},
            ),
            patch.object(daily.storage, "record_event", return_value=True),
            patch.object(
                daily.recurring,
                "accept_from_receipt",
                return_value={"packets": [(13312, b"active")]},
            ),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def call(self):
        return daily.accept_for_choice(
            self.db,
            self.store,
            self.character,
            self.offer,
            actor_id=-5,
            reference_id=3819,
            action_id=703,
        )

    def test_matching_offered_category_creates_authenticated_acceptance(self):
        self.assertEqual(self.call(), [(13312, b"active")])
        args = daily.storage.record_event.call_args.args
        self.assertEqual(args[1], 9)
        self.assertEqual(args[3]["kind"], "native_recurring_acceptance")
        self.assertEqual(args[3]["definition_id"], 4142)
        self.assertEqual(args[3]["node_id"], 3789)
        self.assertEqual(args[3]["choice_id"], 9494)
        self.assertEqual(args[3]["reconstruction"], daily.POLICY)
        daily.recurring.accept_from_receipt.assert_called_once()

    def test_no_daily_or_wrong_category_no_mutation(self):
        self.choice["category_id"] = 701
        self.assertEqual(self.call(), [])
        daily.storage.record_event.assert_not_called()
        daily.recurring.accept_from_receipt.assert_not_called()

    def test_existing_acceptance_does_not_regrant(self):
        self.db.execute.return_value.fetchone.return_value = {"exists": 1}
        self.assertEqual(self.call(), [])
        daily.storage.record_event.assert_not_called()

    def test_rejects_unqualified_source(self):
        self.source["daily_target_authority"]["category_id"] = 701
        with self.assertRaisesRegex(ValueError, "source differs"):
            self.call()
        daily.storage.record_event.assert_not_called()


if __name__ == "__main__":
    unittest.main()
