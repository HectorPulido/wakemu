import unittest
from contextlib import nullcontext
from datetime import datetime, timezone
from threading import RLock
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server.achievements import rii_owned_lesson as lesson


class OwnedLessonTests(unittest.TestCase):
    def setUp(self):
        self.db = Mock()
        self.monsters = [{"id": -42, "ref": 5466}]
        self.fact = lesson.payload(lesson.DISTANCE, 8, -42)

    def test_exact_receipt_binds_only_owner(self):
        self.db.execute.return_value.fetchone.return_value = {"payload": self.fact}
        self.assertEqual(
            lesson.bind(self.db, lesson.DISTANCE, 8, self.monsters),
            {"owner": 8, "target": -42, "hits": 0},
        )
        self.assertIsNone(lesson.bind(self.db, lesson.DISTANCE, 9, self.monsters))

    def test_admission_rejects_other_owner_but_preserves_unrelated_fights(self):
        self.db.execute.return_value.fetchall.return_value = [
            {"character_id": 8, "payload": self.fact}
        ]
        self.assertTrue(lesson.admit(self.db, lesson.DISTANCE, 8, self.monsters))
        with self.assertRaises(ValueError):
            lesson.admit(self.db, lesson.DISTANCE, 9, self.monsters)
        self.assertTrue(
            lesson.admit(self.db, lesson.DISTANCE, 9, [{"id": -1, "ref": 33}])
        )

    def test_malformed_and_other_receipts_do_not_claim_actors(self):
        self.db.execute.return_value.fetchone.return_value = {
            "payload": {"kind": "other"}
        }
        self.assertIsNone(lesson.bind(self.db, lesson.DISTANCE, 8, self.monsters))
        with self.assertRaises(ValueError):
            lesson.payload(lesson.DISTANCE, 8, 42)

    def test_spawn_checks_native_prerequisite_before_publication(self):
        from wakfu_server import (
            monsters,
            npc_actor_identity,
            combat_terrain,
            combat_monster_world,
        )
        from wakfu_server.achievements import storage

        player = {
            "id": 8,
            "account_id": 5,
            "map_id": 1388,
            "instance_id": 0,
            "x": 1,
            "y": 2,
            "z": 0,
        }
        store = Mock()
        store.connection.return_value = nullcontext(self.db)
        store.character.return_value = player
        groups = Mock(lock=RLock())
        groups.available.return_value = []
        groups.register_transaction = Mock()
        state = {"running": [5143], "objectives": [10575]}
        monster = {"id": -42, "ref": 5466, "x": 2, "y": 2, "z": 0}
        with patch.object(storage, "load_locked", return_value=state), patch.object(
            storage, "record_event", return_value=True
        ) as record, patch.object(
            monsters, "owned_instance", return_value=monster
        ), patch.object(
            npc_actor_identity, "allocate_block", return_value=42
        ), patch.object(
            combat_terrain,
            "published_geometry",
            return_value=SimpleNamespace(outgoing={(1, 2, 0): [(2, 2, 0)]}),
        ), patch.object(
            combat_monster_world, "spawn_group", return_value=b"scene"
        ):
            self.assertEqual(
                lesson.spawn(store, groups, 5, "generation", player, lesson.DISTANCE),
                (12608, b"scene"),
            )
            self.assertEqual(record.call_args.args[2], "rii-distance-sack:42")
            state["objectives"] = []
            self.assertIsNone(
                lesson.spawn(store, groups, 5, "generation", player, lesson.DISTANCE)
            )
            self.assertEqual(groups.register_transaction.call_count, 1)

    def test_settlement_requires_owned_finished_pve_victory(self):
        fight = SimpleNamespace(
            id=12,
            phase="finished",
            winner=0,
            actors={8: SimpleNamespace(team=0), -42: SimpleNamespace(team=1)},
            distance_contract={"owner": 8, "target": -42, "hits": 4},
        )
        member = {"character_id": 8, "account_id": 5, "session_generation": "g"}
        self.db.execute.return_value.fetchone.side_effect = [
            {"payload": self.fact},
            {"team": 1, "status": "finished", "fight_kind": "pve"},
        ]
        store = Mock()
        self.assertEqual(
            lesson.settle_participants(
                self.db,
                store,
                lesson.DISTANCE,
                fight,
                [member],
                self.monsters,
                contract_name="distance_contract",
            ),
            {},
        )
        store.lock_character.assert_not_called()
        fight.winner = 1
        self.assertEqual(
            lesson.settle_participants(
                self.db,
                store,
                lesson.DISTANCE,
                fight,
                [member],
                self.monsters,
                contract_name="distance_contract",
            ),
            {},
        )
        fight.winner = 0
        fight.distance_contract["hits"] = 3
        self.assertEqual(
            lesson.settle_participants(
                self.db,
                store,
                lesson.DISTANCE,
                fight,
                [member],
                self.monsters,
                contract_name="distance_contract",
            ),
            {},
        )

    def test_settlement_persists_only_the_native_distance_objective(self):
        from wakfu_server.achievements import mission_progress, storage, wire

        fight = SimpleNamespace(
            id=12,
            phase="finished",
            winner=0,
            actors={8: SimpleNamespace(team=0), -42: SimpleNamespace(team=1)},
            distance_contract={"owner": 8, "target": -42, "hits": 4},
        )
        member = {"character_id": 8, "account_id": 5, "session_generation": "g"}
        self.db.execute.return_value.fetchone.side_effect = [
            {"payload": self.fact},
            {"team": 0, "status": "finished", "fight_kind": "pve"},
            {"data": {"native": {"d": 5143}}},
        ]
        store = Mock()
        store.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
        before = {"running": [5143], "objectives": [10575]}
        after = {"running": [5143], "objectives": [10575, 10576]}
        with patch.object(storage, "load_locked", return_value=before), patch.object(
            storage, "record_event", return_value=True
        ) as receipt, patch.object(storage, "store") as save, patch.object(
            mission_progress, "advance_objective", return_value=(after, [], [10576], [])
        ) as advance, patch.object(
            wire, "changes", return_value=[(13832, b"ok")]
        ):
            result = lesson.settle_participants(
                self.db,
                store,
                lesson.DISTANCE,
                fight,
                [member],
                self.monsters,
                contract_name="distance_contract",
            )
        self.assertEqual(result, {5: [(13832, b"ok")]})
        self.assertEqual(advance.call_args.args[2], 10576)
        self.assertEqual(receipt.call_args.args[2], "rii-lesson-objective:10576")
        save.assert_called_once_with(self.db, 8, after)

    def test_final_lesson_settles_child_rewards_and_parent_in_same_transaction(self):
        from wakfu_server.achievements import (
            mission_dependencies,
            mission_progress,
            storage,
        )

        final = lesson.Lesson(
            "rii-states-sack:", "reconstructed_rii_states_sack", 5466, 10611, 10610
        )
        fight = SimpleNamespace(
            id=12,
            phase="finished",
            winner=0,
            actors={8: SimpleNamespace(team=0), -42: SimpleNamespace(team=1)},
            states_contract={"owner": 8, "target": -42, "hits": 4},
        )
        member = {"character_id": 8, "account_id": 5, "session_generation": "g"}
        child, parent = {"d": 5143}, {"d": 5160}
        self.db.execute.return_value.fetchone.side_effect = [
            {"payload": lesson.payload(final, 8, -42)},
            {"team": 0, "status": "finished", "fight_kind": "pve"},
            {"data": {"native": child}},
            {"data": {"native": parent}},
        ]
        store = Mock()
        store.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
        store.character.return_value = {"id": 8, "account_id": 5}
        before = {"running": [5143, 5160], "objectives": [10610]}
        after = {"running": [5160], "objectives": [10610, 10611]}
        reward = {"d": 1, "aeV": 6, "ckl": [1000]}
        planned = (after, [(5143, reward)], [10611], [5143])
        with patch.object(storage, "load_locked", return_value=before), patch.object(
            storage, "record_event", return_value=True
        ), patch.object(storage, "store") as save, patch.object(
            mission_progress, "advance_objective", return_value=planned
        ), patch.object(
            mission_dependencies, "settle", return_value={"packets": [(13832, b"done")]}
        ) as settle:
            result = lesson.settle_participants(
                self.db,
                store,
                final,
                fight,
                [member],
                self.monsters,
                contract_name="states_contract",
            )
        self.assertEqual(result, {5: [(13832, b"done")]})
        self.assertEqual(
            settle.call_args.args[4:7],
            (planned, {5143: child, 5160: parent}, ((5160, 10616, 5143),)),
        )
        save.assert_not_called()  # The shared settlement owns the only store operation.


if __name__ == "__main__":
    unittest.main()
