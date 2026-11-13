import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from wakfu_server.achievements import conversation_turnin as turnin


class ConversationTurnInTest(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.db.execute.return_value.fetchone.return_value = {"actor_id": -1}
        self.store = SimpleNamespace(
            now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        self.character = {"id": 7, "account_id": 9}
        self.session = SimpleNamespace(speaker_id=-1)
        self.binding = SimpleNamespace(quest_id=10, objective_id=11)
        self.definition = {"cjU": 0, "cjL": 0, "getDuration": 0}
        self.req = turnin.TurnInRequirement(123, 5)

    def invoke(self):
        return turnin.settle(
            self.db,
            self.store,
            self.character,
            self.session,
            self.binding,
            self.definition,
            self.req,
            node_id=4,
            choice_id=5,
        )

    @patch(
        "wakfu_server.achievements.service.drain_rewards", return_value=[(3, b"reward")]
    )
    @patch("wakfu_server.achievements.wire.changes", return_value=[(2, b"progress")])
    @patch("wakfu_server.achievements.storage.store")
    @patch("wakfu_server.achievements.storage.claim_reward")
    @patch("wakfu_server.achievements.storage.record_event", return_value=True)
    @patch(
        "wakfu_server.native_generic_rewards._payment",
        return_value=({}, [(1, b"payment")], []),
    )
    @patch("wakfu_server.achievements.conversation.advance")
    @patch(
        "wakfu_server.achievements.storage.load_locked", return_value={"existing": True}
    )
    @patch(
        "wakfu_server.achievements.conversation.authorize_fact",
        return_value={"kind": "qualified"},
    )
    @patch("wakfu_server.achievements.service._owner")
    def test_qualified_delivery_debits_once_then_persists_and_replay_does_not_debit(
        self,
        owner,
        authorize,
        load,
        advance,
        payment,
        record,
        claim,
        store,
        changes,
        drain,
    ):
        advance.return_value = ({"new": True}, [(10, {"d": 44})], [11], [10])
        result = self.invoke()
        self.assertTrue(result["applied"])
        self.assertEqual(
            result["packets"], [(1, b"payment"), (2, b"progress"), (3, b"reward")]
        )
        payment.assert_called_once_with(
            self.db, self.store, self.character, {"group_cod": 123, "group_coe": 5}
        )
        record.assert_called_once()
        self.assertEqual(record.call_args.args[3]["item_quantity"], 5)
        claim.assert_called_once()
        store.assert_called_once()
        payment.reset_mock()
        record.reset_mock()
        store.reset_mock()
        advance.return_value = ({"existing": True}, [], [], [])
        self.assertFalse(self.invoke()["applied"])
        payment.assert_not_called()
        record.assert_not_called()
        store.assert_not_called()

    @patch("wakfu_server.achievements.storage.store")
    @patch("wakfu_server.achievements.storage.record_event")
    @patch(
        "wakfu_server.native_generic_rewards._payment",
        side_effect=ValueError("insufficient items"),
    )
    @patch(
        "wakfu_server.achievements.conversation.advance",
        return_value=({"new": True}, [], [11], []),
    )
    @patch(
        "wakfu_server.achievements.storage.load_locked", return_value={"existing": True}
    )
    @patch(
        "wakfu_server.achievements.conversation.authorize_fact",
        return_value={"kind": "qualified"},
    )
    @patch("wakfu_server.achievements.service._owner")
    def test_insufficient_payment_never_records_progress(
        self,
        owner,
        authorize,
        load,
        advance,
        payment,
        record,
        store,
    ):
        with self.assertRaisesRegex(ValueError, "insufficient items"):
            self.invoke()
        record.assert_not_called()
        store.assert_not_called()

    @patch("wakfu_server.native_generic_rewards._payment")
    @patch(
        "wakfu_server.achievements.conversation.authorize_fact",
        side_effect=ValueError("unauthorized choice"),
    )
    @patch("wakfu_server.achievements.service._owner")
    def test_unqualified_choice_is_rejected_before_progress_or_payment(
        self,
        owner,
        authorize,
        payment,
    ):
        with self.assertRaisesRegex(ValueError, "unauthorized choice"):
            self.invoke()
        owner.assert_called_once_with(self.db, self.character)
        authorize.assert_called_once()
        payment.assert_not_called()
        # Only the published NPC lookup may run before conversation authorization.
        self.db.execute.assert_called_once()

    @patch("wakfu_server.native_generic_rewards._payment")
    @patch(
        "wakfu_server.achievements.service._owner",
        side_effect=ValueError("character ownership mismatch"),
    )
    def test_foreign_character_is_rejected_before_npc_or_item_access(
        self, owner, payment
    ):
        with self.assertRaisesRegex(ValueError, "ownership mismatch"):
            self.invoke()
        owner.assert_called_once_with(self.db, self.character)
        self.db.execute.assert_not_called()
        payment.assert_not_called()

    @patch("wakfu_server.achievements.storage.store")
    @patch("wakfu_server.achievements.storage.claim_reward")
    @patch("wakfu_server.achievements.storage.record_event", return_value=False)
    @patch(
        "wakfu_server.native_generic_rewards._payment",
        return_value=({}, [(1, b"payment")], []),
    )
    @patch(
        "wakfu_server.achievements.conversation.advance",
        return_value=({"new": True}, [(10, {"d": 44})], [11], [10]),
    )
    @patch(
        "wakfu_server.achievements.storage.load_locked", return_value={"existing": True}
    )
    @patch(
        "wakfu_server.achievements.conversation.authorize_fact",
        return_value={"kind": "qualified"},
    )
    @patch("wakfu_server.achievements.service._owner")
    def test_missing_durable_receipt_prevents_progress_and_reward_claim(
        self,
        owner,
        authorize,
        load,
        advance,
        payment,
        record,
        claim,
        store,
    ):
        with self.assertRaisesRegex(ValueError, "receipt is missing"):
            self.invoke()
        payment.assert_called_once_with(
            self.db,
            self.store,
            self.character,
            {"group_cod": 123, "group_coe": 5},
        )
        record.assert_called_once()
        claim.assert_not_called()
        store.assert_not_called()

    @patch("wakfu_server.achievements.service._owner")
    def test_invalid_and_recurring_bindings_fail_before_debit(self, owner):
        for ref, qty in [(0, 1), (1, 0), (True, 1), (1, 32768)]:
            with self.subTest(ref=ref, qty=qty), self.assertRaises(ValueError):
                turnin.TurnInRequirement(ref, qty)
        self.definition["cjU"] = 86400
        with self.assertRaises(ValueError):
            self.invoke()
        owner.assert_not_called()
