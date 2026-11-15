"""The Rii guardian requires an owned, resolved fight, including a defeat."""

import unittest
import struct
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from wakfu_server.achievements import mission_dependencies, rii_guardian_battle
from wakfu_server.achievements import rii_guardian_contract


class GuardianBattleTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.store = MagicMock()
        self.store.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.store.character.return_value = {"id": 7, "account_id": 2}
        self.fight = SimpleNamespace(
            id=9,
            phase="finished",
            winner=1,
            native_fight_model=rii_guardian_contract.MODEL,
            actors={
                7: SimpleNamespace(
                    team=1, controlled=True, position=rii_guardian_contract.PLAYER
                ),
                -8: SimpleNamespace(
                    team=0,
                    effective_level=rii_guardian_contract.LEVEL,
                    position=rii_guardian_contract.TARGET,
                ),
            },
        )
        self.members = [{"character_id": 7, "account_id": 2, "session_generation": 3}]
        self.monsters = [{"id": -8, "ref": 5458, "level": rii_guardian_contract.LEVEL}]
        self.before = {
            "running": [5146, 5160],
            "completed": [],
            "objectives": [10582, 10583],
        }
        self.planned = ({}, [], [10584], [5146])
        self.receipt = {
            "kind": "reconstructed_rii_guardian_actor",
            "owner": 7,
            "actor_id": -8,
            "ref": 5458,
        }
        rii_guardian_contract.bind(
            self.fight,
            {"schema": rii_guardian_contract.SCHEMA, "owner": 7, "target": -8},
        )

    def query(self, sql, params):
        result = MagicMock()
        if "character_achievement_events" in sql:
            result.fetchone.return_value = {"payload": self.receipt}
        elif "combat_fight_participants" in sql:
            result.fetchone.return_value = {
                "team": 1,
                "status": "finished",
                "fight_kind": "pve",
            }
        else:
            result.fetchall.return_value = [
                {"definition_id": n, "data": {"native": {"d": n}}} for n in (5146, 5160)
            ]
        return result

    def test_defeat_and_victory_record_attempt_without_finishing_before_cinematic(self):
        self.db.execute.side_effect = self.query
        with patch(
            "wakfu_server.achievements.storage.load_locked", return_value=self.before
        ), patch(
            "wakfu_server.achievements.storage.record_event", return_value=True
        ) as receipt, patch(
            "wakfu_server.achievements.mission_dependencies.settle"
        ) as settle, patch.object(
            rii_guardian_battle, "_retire_lost_encounter"
        ) as retire:
            for winner in (0, 1):
                self.fight.winner = winner
                self.assertEqual(
                    rii_guardian_battle.settle(
                        self.db, self.store, self.fight, self.members, self.monsters
                    ),
                    {},
                )
                self.assertEqual(receipt.call_args.args[-1]["won"], winner == 1)
            settle.assert_not_called()
            retire.assert_called_once_with(self.db, -8)

    def test_unowned_wrong_monster_unfinished_and_withdrawn_never_progress(self):
        self.db.execute.side_effect = self.query
        for monsters, phase, withdrawn, receipt in (
            ([{"id": -8, "ref": 5466}], "finished", False, self.receipt),
            (self.monsters, "active", False, self.receipt),
            (self.monsters, "finished", True, self.receipt),
            (self.monsters, "finished", False, {**self.receipt, "owner": 8}),
        ):
            self.fight.phase = phase
            self.members[0]["withdrawn"] = withdrawn
            self.receipt = receipt
            self.assertEqual(
                rii_guardian_battle.settle(
                    self.db, self.store, self.fight, self.members, monsters
                ),
                {},
            )
        self.store.lock_character.assert_not_called()

    def test_owned_encounter_cannot_be_taken_by_other_player(self):
        self.db.execute.return_value.fetchall.return_value = [
            {"character_id": 7, "payload": self.receipt},
        ]
        self.assertTrue(rii_guardian_battle.admit(self.db, 7, self.monsters))
        with self.assertRaisesRegex(ValueError, "belongs to another player"):
            rii_guardian_battle.admit(self.db, 8, self.monsters)

    def test_arbitrary_guardian_breed_without_receipt_is_not_owned(self):
        self.db.execute.return_value.fetchall.return_value = []
        self.assertTrue(rii_guardian_battle.admit(self.db, 8, self.monsters))

    def test_missing_owner_receipt_does_not_settle_or_consume_guardian(self):
        query = MagicMock()
        query.fetchone.return_value = None
        self.db.execute.return_value = query
        with patch(
            "wakfu_server.achievements.storage.record_event"
        ) as record, patch.object(
            rii_guardian_battle, "_retire_lost_encounter"
        ) as retire:
            self.assertEqual(
                {},
                rii_guardian_battle.settle(
                    self.db, self.store, self.fight, self.members, self.monsters
                ),
            )
        record.assert_not_called()
        retire.assert_not_called()
        self.store.lock_character.assert_not_called()

    def test_ordinary_model_with_matching_actor_receipt_does_not_settle(self):
        self.db.execute.side_effect = self.query
        self.fight.native_fight_model = 2
        with patch("wakfu_server.achievements.storage.record_event") as record:
            self.assertEqual(
                {},
                rii_guardian_battle.settle(
                    self.db, self.store, self.fight, self.members, self.monsters
                ),
            )
        record.assert_not_called()
        self.store.lock_character.assert_not_called()

    def test_automatic_start_targets_the_owned_guardian_on_its_actual_cell(self):
        guardian = {
            "id": -8,
            "ref": 5458,
            "map_id": 1387,
            "instance_id": 0,
            "x": -12,
            "y": 0,
            "z": 2,
        }
        body = rii_guardian_battle.start_request(guardian)
        self.assertEqual(struct.unpack(">qiihB", body), (-8, -12, 0, 2, 0))
        for bad in (
            {**guardian, "ref": 1},
            {**guardian, "map_id": 1385},
            {**guardian, "id": 8},
        ):
            with self.assertRaises(ValueError):
                rii_guardian_battle.start_request(bad)

    def test_cinematic_callback_completes_mission_and_returns_to_rii(self):
        source = {
            "id": 7,
            "account_id": 2,
            "map_id": 1387,
            "instance_id": 0,
            "x": -12,
            "y": 0,
            "z": 2,
        }
        self.store.connection.return_value.__enter__.return_value = self.db
        self.store.character.return_value = source
        self.store.transition_map_in_transaction.return_value = {
            **source,
            "map_id": 1385,
        }
        self.db.execute.side_effect = self.query
        with patch.object(
            rii_guardian_battle, "pending_cinematic", return_value=True
        ), patch(
            "wakfu_server.achievements.storage.load_locked", return_value=self.before
        ), patch(
            "wakfu_server.achievements.mission_progress.advance_objective",
            return_value=self.planned,
        ), patch(
            "wakfu_server.achievements.rii_departure.activate",
            return_value=self.planned,
        ), patch(
            "wakfu_server.achievements.mission_dependencies.settle",
            return_value={"packets": [(1, b"x")]},
        ):
            saved, packets = rii_guardian_battle.finish_cinematic(
                self.store, 2, "session", source
            )
        self.assertEqual(saved["map_id"], 1385)
        self.assertEqual(packets, [(1, b"x")])
        self.assertEqual(
            self.store.transition_map_in_transaction.call_args.args[-1],
            {"map_id": 1385, "instance_id": 0, "x": -19, "y": 25, "z": 5},
        )

    def test_no_callback_without_a_qualified_pending_attempt(self):
        source = {
            "id": 7,
            "account_id": 2,
            "map_id": 1387,
            "instance_id": 0,
            "x": -12,
            "y": 0,
            "z": 2,
        }
        self.store.connection.return_value.__enter__.return_value = self.db
        self.store.character.return_value = source
        with patch.object(rii_guardian_battle, "pending_cinematic", return_value=False):
            with self.assertRaisesRegex(ValueError, "pending"):
                rii_guardian_battle.finish_cinematic(self.store, 2, "session", source)
        self.store.transition_map_in_transaction.assert_not_called()
