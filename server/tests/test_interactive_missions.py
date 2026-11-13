"""Configured native quest object interaction: qualification and settlement."""
import copy
import struct
import sys
import types
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

from wakfu_server.achievements import interactive_missions


class FakeDB:
    def __init__(self, row=None):
        self.row = row
        self.queries = []
        self.matched_row = row

    def execute(self, sql, params=()):
        self.queries.append((sql, params))
        if "quest_interactive_bindings" in sql and self.row is not None:
            self.matched_row = (
                self.row
                if tuple(params)
                == tuple(
                    self.row[k]
                    for k in ("map_id", "object_id", "action_id", "parameter")
                )
                else None
            )
        return self

    def fetchone(self):
        return self.matched_row


class FakeStore:
    def __init__(self, row=None, state=None):
        self.db = FakeDB(row)
        self.state = state
        self.position = {"map_id": 12, "instance_id": 0, "x": 5, "y": 8, "z": -1}

    @contextmanager
    def connection(self):
        yield self.db

    def character(self, account_id, character_id, db):
        return {"id": character_id, "account_id": account_id, **self.position}

    def now(self):
        return datetime.fromtimestamp(10, timezone.utc)


class InteractiveMissionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.definition = {
            "d": 91,
            "native_class": "aJM",
            "aqb": False,
            "cjI": {"always": True},
            "cjJ": [{"d": 901, "ckc": {"always": True}, "cke": {"always": True}}],
            "cjK": [{"d": 77, "aeV": 5, "ckl": [100, 1]}],
        }
        self.row = {
            "map_id": 12,
            "object_id": 345,
            "action_id": 9,
            "parameter": 2,
            "x": 4,
            "y": 8,
            "z": -1,
            "object_type": "bBH",
            "max_distance": 2,
            "quest_id": 91,
            "objective_id": 901,
            "revision": "native-r1",
            "required_item": 88,
            "required_quantity": 1,
            "data": {"native": self.definition},
        }
        self.location = {
            "id": 5,
            "map_id": 12,
            "instance_id": 0,
            "x": 5,
            "y": 8,
            "z": -1,
        }
        self.body = struct.pack(">qHH", 345, 9, 2)
        self.state = {
            "variables": {},
            "objectives": [],
            "running": [91],
            "completed": [],
            "tracking": [91],
            "recent": [],
            "completion_dates": {},
        }

    def invoke(
        self,
        *,
        row=None,
        state=None,
        location=None,
        body=None,
        loaded=True,
        blocked=False,
        real_wire=False
    ):
        store = FakeStore(
            self.row if row is None else row, self.state if state is None else state
        )
        store.position = {
            key: (location or self.location).get(key, 0)
            for key in ("map_id", "instance_id", "x", "y", "z")
        }
        interaction = {"type": "bBH", "x": 4, "y": 8, "z": -1}
        wire_changes = interactive_missions.wire.changes
        with patch("wakfu_server.paid_containers._leased_owner"), patch(
            "wakfu_server.environment_interactions._guard"
        ), patch.dict(
            sys.modules,
            {
                "wakfu_server.world_static": types.SimpleNamespace(
                    interaction=lambda *args: interaction
                )
            },
        ), patch(
            "wakfu_server.achievements.interactive_missions._owner"
        ), patch(
            "wakfu_server.native_generic_rewards._payment",
            return_value=(
                {
                    "id": 5,
                    "account_id": 6,
                    "map_id": 12,
                    "instance_id": 0,
                    "x": 5,
                    "y": 8,
                    "z": -1,
                },
                [b"paid"],
                [],
            ),
        ) as payment, patch(
            "wakfu_server.achievements.storage.load_locked", return_value=store.state
        ), patch(
            "wakfu_server.achievements.storage.record_event", return_value=True
        ) as record, patch(
            "wakfu_server.achievements.storage.store"
        ) as persist, patch(
            "wakfu_server.achievements.storage.claim_reward"
        ) as claim, patch(
            "wakfu_server.achievements.wire.changes",
            side_effect=wire_changes if real_wire else None,
            return_value=[b"progress"],
        ) as changes, patch(
            "wakfu_server.achievements.interactive_missions.drain_rewards",
            return_value=[b"reward"],
        ) as drain, patch(
            "wakfu_server.dungeon_criteria.evaluate", return_value=True
        ):
            result = interactive_missions.interact(
                store,
                6,
                "generation",
                location or self.location,
                self.body if body is None else body,
                loaded=loaded,
                blocked=blocked,
            )
        return result, store, record, persist, claim, changes, drain, payment

    def test_intermediate_fresco_refreshes_the_tracked_quest(self):
        self.definition["cjJ"].append({"d": 902, "ckc": "", "cke": ""})
        result, _, _, persist, _, _, _, _ = self.invoke(real_wire=True)
        opcodes = [
            packet[0] for packet in result["packets"] if isinstance(packet, tuple)
        ]
        self.assertEqual([13832, 13371, 13371], opcodes)
        self.assertEqual([91], persist.call_args.args[2]["tracking"])
        self.assertEqual([901], persist.call_args.args[2]["objectives"])

    def test_qualified_interaction_advances_once_and_claims_completion_reward(self):
        result, store, record, persist, claim, changes, drain, payment = self.invoke()
        self.assertTrue(result["applied"])
        self.assertEqual([b"paid", b"progress", b"reward"], result["packets"])
        payment.assert_called_once()
        self.assertEqual([91], result["completed"])
        self.assertEqual([901], persist.call_args.args[2]["objectives"])
        recorded = record.call_args.args[3]
        self.assertEqual(
            {
                "kind": "configured_quest_interactive_v1",
                "map_id": 12,
                "object_id": 345,
                "action_id": 9,
                "parameter": 2,
                "quest_id": 91,
                "objective_id": 901,
                "revision": "native-r1",
            },
            recorded,
        )
        self.assertEqual("quest-interactive:91:901", record.call_args.args[2])
        self.assertEqual(91, claim.call_args.args[2])
        self.assertEqual(("once", 77), claim.call_args.args[3:5])
        persist.assert_called_once()
        changes.assert_called_once()
        drain.assert_called_once()
        self.assertEqual((12, 345, 9, 2), store.db.queries[0][1])

    def test_action_range_instance_and_malformed_requests_reject_before_progress(self):
        cases = [
            (dict(body=b"short"), "unavailable"),
            (dict(loaded=False), "unavailable"),
            (dict(blocked=True), "unavailable"),
            (dict(body=struct.pack(">qHH", 345, 9, 3)), "Unknown quest"),
            (
                dict(location={**self.location, "instance_id": 7}),
                "configured map instance",
            ),
            (dict(location={**self.location, "x": 30}), "out of range"),
        ]
        for kwargs, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(
                ValueError, message
            ):
                self.invoke(**kwargs)

    def test_interaction_target_type_and_vertical_position_are_checked(self):
        for interaction in (
            {"type": "other", "x": 4, "y": 8, "z": -1},
            {"type": "bBH", "x": 4, "y": 8, "z": 0},
        ):
            with self.subTest(interaction=interaction), patch(
                "wakfu_server.paid_containers._leased_owner"
            ), patch("wakfu_server.achievements.interactive_missions._owner"), patch(
                "wakfu_server.environment_interactions._guard"
            ), patch.dict(
                sys.modules,
                {
                    "wakfu_server.world_static": types.SimpleNamespace(
                        interaction=lambda *args: interaction
                    )
                },
            ), self.assertRaisesRegex(
                ValueError, "unavailable or out of range"
            ):
                interactive_missions.interact(
                    FakeStore(self.row, self.state),
                    6,
                    "generation",
                    self.location,
                    self.body,
                    loaded=True,
                    blocked=False,
                )

    def test_inactive_and_replayed_objective_are_noop_without_receipt_or_reward(self):
        inactive = copy.deepcopy(self.state)
        inactive["running"] = []
        result, _, record, persist, claim, _, drain, payment = self.invoke(
            state=inactive
        )
        self.assertFalse(result["applied"])
        self.assertEqual([], result["packets"])
        record.assert_not_called()
        persist.assert_not_called()
        claim.assert_not_called()
        drain.assert_not_called()
        payment.assert_not_called()
        replay = copy.deepcopy(self.state)
        replay["objectives"] = [901]
        result, _, record, persist, claim, _, drain, payment = self.invoke(state=replay)
        self.assertFalse(result["applied"])
        record.assert_not_called()
        persist.assert_not_called()
        claim.assert_not_called()
        drain.assert_not_called()
        payment.assert_not_called()

    def test_reviewed_visual_remains_available_after_quest_completion(self):
        row = {**self.row, "script_id": 467}
        state = copy.deepcopy(self.state)
        state["running"] = []
        state["completed"] = [91]
        result, _, record, persist, claim, _, drain, payment = self.invoke(
            row=row, state=state
        )
        self.assertFalse(result["applied"])
        self.assertTrue(result["handled"])
        opcode, body = result["packets"][0]
        self.assertEqual(13270, opcode)
        self.assertEqual((5, 467, 1, 2), struct.unpack_from(">qiBi", body))
        for call in (record, persist, claim, drain, payment):
            call.assert_not_called()

    def test_locked_objective_still_opens_visual_without_progress(self):
        with patch(
            "wakfu_server.achievements.mission_progress.advance_objective",
            side_effect=ValueError("Native quest objective prerequisite is not met"),
        ):
            result, _, record, persist, claim, _, drain, payment = self.invoke(
                row={**self.row, "script_id": 470}
            )
        self.assertFalse(result["applied"])
        self.assertTrue(result["handled"])
        self.assertEqual(
            (5, 470, 1, 2), struct.unpack_from(">qiBi", result["packets"][0][1])
        )
        for call in (record, persist, claim, drain, payment):
            call.assert_not_called()

    def test_missing_payment_fails_before_receipt_or_progress(self):
        store = FakeStore(self.row, self.state)
        with patch("wakfu_server.paid_containers._leased_owner"), patch(
            "wakfu_server.environment_interactions._guard"
        ), patch.dict(
            sys.modules,
            {
                "wakfu_server.world_static": types.SimpleNamespace(
                    interaction=lambda *args: {"type": "bBH", "x": 4, "y": 8, "z": -1}
                )
            },
        ), patch(
            "wakfu_server.achievements.interactive_missions._owner"
        ), patch(
            "wakfu_server.achievements.storage.load_locked", return_value=self.state
        ), patch(
            "wakfu_server.dungeon_criteria.evaluate", return_value=True
        ), patch(
            "wakfu_server.native_generic_rewards._payment",
            side_effect=ValueError("Required item unavailable"),
        ) as payment, patch(
            "wakfu_server.achievements.storage.record_event"
        ) as record, patch(
            "wakfu_server.achievements.storage.store"
        ) as persist, self.assertRaisesRegex(
            ValueError, "Required item unavailable"
        ):
            interactive_missions.interact(
                store,
                6,
                "generation",
                self.location,
                self.body,
                loaded=True,
                blocked=False,
            )
        payment.assert_called_once()
        record.assert_not_called()
        persist.assert_not_called()

    def test_failed_native_criteria_does_not_write_receipt_or_progress(self):
        store = FakeStore(self.row, self.state)
        with patch("wakfu_server.paid_containers._leased_owner"), patch(
            "wakfu_server.environment_interactions._guard"
        ), patch.dict(
            sys.modules,
            {
                "wakfu_server.world_static": types.SimpleNamespace(
                    interaction=lambda *args: {"type": "bBH", "x": 4, "y": 8, "z": -1}
                )
            },
        ), patch(
            "wakfu_server.achievements.interactive_missions._owner"
        ), patch(
            "wakfu_server.native_generic_rewards._payment",
            return_value=(
                {
                    "id": 5,
                    "account_id": 6,
                    "map_id": 12,
                    "instance_id": 0,
                    "x": 5,
                    "y": 8,
                    "z": -1,
                },
                [b"paid"],
                [],
            ),
        ) as payment, patch(
            "wakfu_server.achievements.storage.load_locked", return_value=self.state
        ), patch(
            "wakfu_server.achievements.storage.record_event"
        ) as record, patch(
            "wakfu_server.achievements.storage.store"
        ) as persist, patch(
            "wakfu_server.dungeon_criteria.evaluate", return_value=False
        ), self.assertRaisesRegex(
            ValueError, "prerequisite"
        ):
            interactive_missions.interact(
                store,
                6,
                "generation",
                self.location,
                self.body,
                loaded=True,
                blocked=False,
            )
        record.assert_not_called()
        persist.assert_not_called()


if __name__ == "__main__":
    unittest.main()
