"""Combat settlement dispatch for recurring hunter objectives."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from wakfu_server.achievements import combat_missions, service
from wakfu_server.objectives import environmental_recurring_storage
from wakfu_server.objectives import recurring_combat_auto
from wakfu_server import guild_daily_quests
from wakfu_server.custom_tasks import external


class RecurringSettlementHookTests(unittest.TestCase):
    def run_settlement(
        self,
        dungeon_id,
        *,
        fresh=False,
        error=None,
        acceptance_error=None,
        accepted_packets=()
    ):
        db = MagicMock()
        db.transaction.return_value.__enter__.return_value = None
        event = {"fight_id": 100, "completed_dungeon_id": dungeon_id}
        character = {"id": 3, "account_id": 4}
        fight = SimpleNamespace(id=100)
        state = {
            "running": [],
            "completed": [],
            "objectives": [],
            "variables": {},
            "tracking": [],
            "recent": [],
            "completion_dates": {},
        }
        with patch.object(service, "_owner"), patch.object(
            service, "_event", return_value=event
        ), patch.object(
            service.storage, "load_locked", return_value=state
        ), patch.object(
            service.storage, "record_event", return_value=fresh
        ), patch.object(
            service.storage, "enqueue_notifications"
        ), patch.object(
            combat_missions, "stage"
        ), patch.object(
            combat_missions, "settle", return_value=[]
        ), patch.object(
            service, "drain_rewards", return_value=[]
        ), patch.object(
            recurring_combat_auto,
            "accept_matching",
            side_effect=acceptance_error,
            return_value=list(accepted_packets),
        ) as acceptance, patch.object(
            environmental_recurring_storage,
            "settle_combat",
            side_effect=error,
            return_value={"packets": [(123, b"x")]},
        ) as hook:
            result = service.settle(db, MagicMock(), character, fight, [])
        return result, hook, acceptance, db

    def test_fresh_victory_uses_persisted_fight_receipt(self):
        db, store = MagicMock(), MagicMock()
        store.now.return_value.timestamp.return_value = 123
        character = {"id": 3, "account_id": 4, "map_id": 5}
        fight = SimpleNamespace(id=100)
        event = {"fight_id": 100, "completed_dungeon_id": 26}
        state = {
            "running": [],
            "completed": [],
            "objectives": [],
            "variables": {},
            "tracking": [],
            "recent": [],
            "completion_dates": {},
        }
        with patch.object(service, "_owner"), patch.object(
            service, "_event", return_value=event
        ), patch.object(
            service.storage, "load_locked", return_value=state
        ), patch.object(
            service.storage, "record_event", return_value=True
        ) as receipt, patch.object(
            service.storage, "store"
        ), patch.object(
            service.storage, "enqueue_notifications"
        ), patch.object(
            service.catalog, "load", return_value={}
        ), patch.object(
            service.engine, "advance", return_value=(state, [], [], [])
        ), patch.object(
            service.wire, "changes", return_value=[]
        ), patch.object(
            combat_missions, "stage"
        ), patch.object(
            combat_missions, "settle", return_value=[]
        ), patch.object(
            service, "drain_rewards", return_value=[]
        ), patch.object(
            recurring_combat_auto, "accept_matching", return_value=[(124, b"accepted")]
        ) as acceptance, patch.object(
            external, "enqueue_fact"
        ), patch.object(
            guild_daily_quests, "settle_combat", return_value=[]
        ), patch.object(
            environmental_recurring_storage,
            "settle_combat",
            return_value={"packets": [(123, b"x")]},
        ) as hook:
            result = service.settle(db, store, character, fight, [])
        receipt.assert_called_once_with(db, 3, "fight:100", event)
        hook.assert_called_once_with(db, store, character, fight, event)
        acceptance.assert_called_once_with(db, store, character, fight, event)
        self.assertEqual(result["packets"], [(124, b"accepted"), (123, b"x")])
        self.assertFalse(result["replay"])

    def test_dungeon_replay_can_retry_recurring_settlement(self):
        result, hook, acceptance, db = self.run_settlement(
            26, accepted_packets=[(124, b"accepted")]
        )
        hook.assert_called_once()
        acceptance.assert_called_once()
        self.assertEqual(result["packets"], [(124, b"accepted"), (123, b"x")])
        self.assertTrue(result["replay"])
        self.assertGreaterEqual(db.transaction.call_count, 2)

    def test_normal_fight_does_not_invoke_recurring_hook(self):
        result, hook, acceptance, _ = self.run_settlement(None)
        hook.assert_not_called()
        acceptance.assert_not_called()
        self.assertEqual(result["packets"], [])

    def test_recurring_failure_does_not_abort_combat_settlement(self):
        with self.assertLogs(service.__name__, level="ERROR"):
            result, hook, acceptance, db = self.run_settlement(
                26, error=ValueError("bad source")
            )
        hook.assert_called_once()
        acceptance.assert_called_once()
        self.assertEqual(result["packets"], [])
        self.assertTrue(result["replay"])
        self.assertGreaterEqual(db.transaction.call_count, 2)

    def test_automatic_acceptance_failure_isolated_from_existing_recurring_settlement(
        self,
    ):
        with self.assertLogs(service.__name__, level="ERROR"):
            result, hook, acceptance, db = self.run_settlement(
                26, acceptance_error=ValueError("invalid optional policy")
            )
        acceptance.assert_called_once()
        hook.assert_called_once()
        self.assertEqual(result["packets"], [(123, b"x")])
        self.assertTrue(result["replay"])
        self.assertGreaterEqual(db.transaction.call_count, 2)


if __name__ == "__main__":
    unittest.main()
