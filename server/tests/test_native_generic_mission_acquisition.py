"""Native generic reward grants emit durable mission acquisition events."""

from contextlib import nullcontext
from datetime import datetime, timezone
import struct
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

from wakfu_server import native_generic_rewards
from wakfu_server.achievements import mission_toolkit_contract


class NativeGenericMissionAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.character = {
            "id": 7,
            "account_id": 2,
            "map_id": 453,
            "instance_id": 0,
            "x": 10,
            "y": 20,
            "z": 0,
            "inventory_items": [],
        }
        self.rule = {
            "object_id": 12345,
            "wire_action": 0,
            "map_id": 453,
            "policy_id": 99,
            "action_criterion": "true",
            "approaches": [[10, 20, 0]],
            "group_cod": 0,
            "group_coe": 0,
            "lifecycle_mode": "ONCE_PER_CHARACTER_RECONSTRUCTED",
            "effects": [
                {"effect_type": 12, "effect_reference": 888, "criterion": "true"}
            ],
        }

    def run_claim(self, grants, *, replay=False, settle_error=None):
        order = []
        db = Mock()

        def execute(sql, params=None):
            if "SELECT rule_digest" in sql:
                return Mock(
                    fetchone=lambda: (
                        {"rule_digest": native_generic_rewards._digest(self.rule)}
                        if replay
                        else None
                    )
                )
            if "INSERT INTO native_generic_reward_attempts" in sql:
                order.append(("attempt", params))
            return Mock(fetchone=lambda: None, fetchall=lambda: [])

        db.execute.side_effect = execute
        store = Mock()
        store.connection.return_value = nullcontext(db)
        store.character.return_value = dict(self.character)
        store.now.return_value = datetime(2026, 11, 17, tzinfo=timezone.utc)

        def settle(_db, _store, _character, token, kind, reference, *, quantity):
            order.append(("event", token, kind, reference, quantity))
            if settle_error:
                raise settle_error
            return [(13832, b"mission")]

        idle_module = ModuleType("wakfu_server.simple_item_actions")
        idle_module._idle = Mock()

        ctx = (
            patch.dict(sys.modules, {"wakfu_server.simple_item_actions": idle_module}),
            patch("wakfu_server.paid_containers._leased_owner"),
            patch.object(native_generic_rewards, "_rule", return_value=self.rule),
            patch("wakfu_server.simple_item_actions._idle"),
            patch.object(native_generic_rewards, "_source"),
            patch("wakfu_server.dungeon_criteria.evaluate", return_value=True),
            patch.object(
                native_generic_rewards, "external_quest_scripts", return_value=set()
            ),
            patch("wakfu_server.achievements.chest_scripts.packets", return_value=[]),
            patch.object(
                native_generic_rewards,
                "_payment",
                return_value=(dict(self.character), [], []),
            ),
            patch.object(native_generic_rewards, "_products", return_value=grants),
            patch(
                "wakfu_server.achievements.rewards._item", return_value=[(123, b"item")]
            ),
            patch(
                "wakfu_server.dungeon_optional_votes.reward_scope", return_value=None
            ),
            patch("wakfu_server.dungeon_optional_votes.claim_scope"),
            patch(
                "wakfu_server.achievements.mission_toolkit.settle", side_effect=settle
            ),
            patch("wakfu_server.achievements.storage.enqueue_notifications"),
        )
        from contextlib import ExitStack

        with ExitStack() as stack:
            mocks = [stack.enter_context(p) for p in ctx]
            result = (
                native_generic_rewards.claim(
                    store,
                    2,
                    "lease",
                    dict(self.character),
                    struct.pack(">qHH", self.rule["object_id"], 0, 0),
                    loaded=True,
                )
                if not settle_error
                else self._raising_claim(store, settle_error)
            )
        return result, order, mocks

    def _raising_claim(self, store, error):
        with self.assertRaisesRegex(type(error), str(error)):
            native_generic_rewards.claim(
                store,
                2,
                "lease",
                dict(self.character),
                struct.pack(">qHH", self.rule["object_id"], 0, 0),
                loaded=True,
            )
        return None

    def test_actual_grant_records_attempt_then_emits_object_scoped_event_quantity_sum(
        self,
    ):
        result, order, mocks = self.run_claim({17545: 2, 17546: 3})
        self.assertEqual([row[0] for row in order], ["attempt", "event"])
        self.assertEqual(order[1][2:], ("generic_item_acquired", 12345, 5))
        self.assertEqual(order[1][1], f"generic-item-acquired:{result['attempt']}")
        self.assertEqual(mocks[13].call_args.args[4:], ("generic_item_acquired", 12345))
        self.assertEqual(mocks[13].call_args.kwargs["quantity"], 5)

    def test_empty_and_replayed_claims_emit_no_acquisition_event(self):
        empty, empty_order, _ = self.run_claim({})
        replay, replay_order, _ = self.run_claim({17545: 1}, replay=True)
        self.assertTrue(empty["replay"])
        self.assertTrue(replay["replay"])
        self.assertNotIn("event", [row[0] for row in empty_order])
        self.assertNotIn("event", [row[0] for row in replay_order])

    def test_event_writer_failure_propagates_after_attempt_and_prevents_delivery(self):
        result, order, mocks = self.run_claim(
            {17545: 1}, settle_error=RuntimeError("overflow")
        )
        self.assertIsNone(result)
        self.assertEqual([row[0] for row in order], ["attempt", "event"])
        mocks[14].assert_not_called()

    def test_toolkit_event_requires_reference_and_accepts_physical_object_id(self):
        event = {"kind": "generic_item_acquired", "reference": 12345, "quantity": 5}
        self.assertIs(mission_toolkit_contract.validate_event(event), event)
        for malformed in (
            {"kind": "generic_item_acquired", "quantity": 1},
            {"kind": "generic_item_acquired", "reference": 0, "quantity": 1},
        ):
            with self.subTest(event=malformed), self.assertRaises(ValueError):
                mission_toolkit_contract.validate_event(malformed)

    @staticmethod
    def loot_fixture(leaf_guard):
        payload = {
            "d": 2294,
            "czg": 1,
            "gBN": [
                {
                    "aAi": 15839,
                    "cqA": False,
                    "cqy": 1,
                    "cqz": 1,
                    "bfh": 1,
                    "czl": 0,
                    "csE": 1,
                    "gBO": [],
                    "czk": leaf_guard,
                    "cmY": 1.0,
                }
            ],
        }
        db = Mock()
        db.execute.return_value.fetchone.return_value = {
            "payload": payload,
            "source_sha256": "a" * 64,
        }
        effect = {
            "loot_list_id": 2294,
            "loot_source_sha256": "a" * 64,
            "criterion": "IsAchievementRunning(123) or true",
        }
        return db, effect

    def test_original_2294_leaf_guard_authorizes_outer_or_effect_criterion(self):
        db, effect = self.loot_fixture("GetItemQuantity(15839) <= 0")
        self.assertTrue(native_generic_rewards._inventory_loot_guard(db, effect))

    def test_outer_or_cannot_bypass_missing_changed_nested_or_wrong_item_leaf_guard(
        self,
    ):
        bad_guards = (
            "",
            "GetItemQuantity(15840) <= 0",
            "(GetItemQuantity(15839) <= 0)",
        )
        for guard in bad_guards:
            with self.subTest(guard=guard):
                db, effect = self.loot_fixture(guard)
                if guard.startswith("(") or "15840" in guard:
                    with self.assertRaises(ValueError):
                        native_generic_rewards._inventory_loot_guard(db, effect)
                else:
                    self.assertFalse(
                        native_generic_rewards._inventory_loot_guard(db, effect)
                    )


if __name__ == "__main__":
    unittest.main()
