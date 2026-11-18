import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from wakfu_server.achievements import conversation, conversation_turnin as turnin


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

    def test_validated_provider_row_settles_both_paths_and_changed_placement_rejects(
        self,
    ):
        row = dict(
            actor_id=-101,
            reference_id=1234,
            map_id=987,
            instance_id=0,
            x=3,
            y=4,
            z=0,
            direction=2,
            dialogue_root=40,
            action_ids=[596],
            interaction_range=4,
            enabled=True,
            provenance="native-provider:test",
        )
        definition = dict(
            d=10,
            native_class="aJM",
            aqb=False,
            cjU=0,
            cjL=0,
            getDuration=0,
            cjJ=[dict(d=11)],
        )
        session = SimpleNamespace(
            speaker_id=row["actor_id"],
            node_id=4,
            graph={(4, 5): None},
            quest_nearby=lambda _character, _row: True,
            authorize_speaker=lambda speaker, node: (speaker, node) == (-101, 4),
            _node=lambda _node: dict(choices=[dict(id=5)]),
            authorize_choice=lambda choice: choice["id"] == 5,
        )
        binding = conversation.QualifiedConversation(
            quest_id=10,
            objective_id=11,
            reference_id=1234,
            action_id=596,
            node_id=4,
            choice_id=5,
            placement_sha256=conversation.placement_signature(row),
            native_definition_sha256=conversation._digest(definition),
        )
        before, after = {"existing": True}, {"existing": True, "objectives": [11]}
        advance_result = (after, [], [11], [])
        self.db.execute.reset_mock()

        with (
            patch("wakfu_server.achievements.service._owner"),
            patch("wakfu_server.achievements.storage.load_locked", return_value=before),
            patch(
                "wakfu_server.achievements.conversation.advance",
                return_value=advance_result,
            ),
            patch("wakfu_server.achievements.storage.record_event", return_value=True),
            patch(
                "wakfu_server.achievements.mission_dependencies.settle",
                return_value=dict(
                    packets=[(2, b"progress")], completed=[], new_objectives=[11]
                ),
            ),
        ):
            result = conversation.settle(
                self.db,
                self.store,
                self.character,
                session,
                binding,
                definition,
                speaker_row=row,
                node_id=4,
                choice_id=5,
            )
        self.assertTrue(result["applied"])
        self.assertEqual(result["packets"], [(2, b"progress")])
        self.db.execute.assert_not_called()

        self.db.execute.reset_mock()
        with (
            patch("wakfu_server.achievements.service._owner"),
            patch("wakfu_server.achievements.storage.load_locked", return_value=before),
            patch(
                "wakfu_server.achievements.conversation.advance",
                return_value=advance_result,
            ),
            patch("wakfu_server.achievements.storage.record_event", return_value=True),
            patch("wakfu_server.achievements.storage.store"),
            patch("wakfu_server.achievements.wire.changes", return_value=[]),
            patch("wakfu_server.achievements.service.drain_rewards", return_value=[]),
            patch("wakfu_server.achievements.mission_toolkit.settle", return_value=[]),
            patch(
                "wakfu_server.achievements.mission_toolkit.settle_completions",
                return_value=[],
            ),
            patch(
                "wakfu_server.native_generic_rewards._payment",
                return_value=({}, [(1, b"payment")], []),
            ),
        ):
            result = turnin.settle(
                self.db,
                self.store,
                self.character,
                session,
                binding,
                definition,
                self.req,
                speaker_row=row,
                node_id=4,
                choice_id=5,
            )
        self.assertTrue(result["applied"])
        self.db.execute.assert_not_called()

        changed = dict(row, x=row["x"] + 1)
        for settle in (conversation.settle, turnin.settle):
            with self.subTest(settler=settle.__module__), patch(
                "wakfu_server.achievements.service._owner"
            ), self.assertRaisesRegex(
                ValueError, "Unqualified or stale native quest conversation"
            ):
                if settle is conversation.settle:
                    settle(
                        self.db,
                        self.store,
                        self.character,
                        session,
                        binding,
                        definition,
                        speaker_row=changed,
                        node_id=4,
                        choice_id=5,
                    )
                else:
                    settle(
                        self.db,
                        self.store,
                        self.character,
                        session,
                        binding,
                        definition,
                        self.req,
                        speaker_row=changed,
                        node_id=4,
                        choice_id=5,
                    )
        self.db.execute.assert_not_called()

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
    @patch(
        "wakfu_server.achievements.mission_toolkit.settle_completions", return_value=[]
    )
    def test_qualified_delivery_debits_once_then_persists_and_replay_does_not_debit(
        self,
        settle_completions,
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
        settle_completions.assert_called_once_with(
            self.db, self.store, self.character, [10]
        )
        payment.reset_mock()
        record.reset_mock()
        store.reset_mock()
        advance.return_value = ({"existing": True}, [], [], [])
        self.assertFalse(self.invoke()["applied"])
        payment.assert_not_called()
        record.assert_not_called()
        store.assert_not_called()
        self.assertEqual(settle_completions.call_count, 1)

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

    def test_parser_accepts_exact_distinct_item_baskets_and_rejects_duplicates(self):
        entry = {
            "reference_id": 3275,
            "action_id": 596,
            "node_id": 3324,
            "choice_id": 8229,
            "items": [
                {"item_reference": 21054, "quantity": 5},
                {"item_reference": 13180, "quantity": 30},
            ],
        }
        self.assertEqual(
            turnin.requirement_from_entry(entry),
            (turnin.TurnInRequirement(21054, 5), turnin.TurnInRequirement(13180, 30)),
        )
        legacy = dict(entry)
        legacy.pop("items")
        legacy.update(item_reference=21054, quantity=5)
        self.assertEqual(
            turnin.requirement_from_entry(legacy), turnin.TurnInRequirement(21054, 5)
        )
        for invalid in (
            {**entry, "items": [entry["items"][0], entry["items"][0]]},
            {**entry, "items": [entry["items"][0]]},
            {
                **entry,
                "items": [dict(entry["items"][0], quantity=0), entry["items"][1]],
            },
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                turnin.requirement_from_entry(invalid)
