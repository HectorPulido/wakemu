"""The area encounter must bind exactly four sacks owned by one player."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server.achievements import rii_area_encounter as encounter
from wakfu_server.achievements import mission_progress, storage, wire


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Database:
    def __init__(self, owners):
        self.owners = owners

    def execute(self, query, args):
        if "character_id=%s AND event_key=%s" in query:
            owner, key = args
            actor = -int(key.removeprefix(encounter.KEY))
            return Result(
                [{"payload": encounter.payload(owner, actor)}]
                if self.owners.get(actor) == owner
                else []
            )
        actor = -int(args[0].removeprefix(encounter.KEY))
        owner = self.owners.get(actor)
        return Result(
            []
            if owner is None
            else [{"character_id": owner, "payload": encounter.payload(owner, actor)}]
        )


class AreaEncounterTests(unittest.TestCase):
    def setUp(self):
        self.monsters = [
            {"id": actor, "ref": encounter.REF} for actor in (-1, -2, -3, -4)
        ]
        self.db = Database({actor["id"]: 8 for actor in self.monsters})

    def test_exact_owned_group_binds(self):
        contract = encounter.bind(self.db, 8, self.monsters)
        self.assertEqual(
            contract,
            {"owner": 8, "targets": [-4, -3, -2, -1], "hits": 0, "actions": []},
        )
        self.assertTrue(encounter.admit(self.db, 8, self.monsters))

    def test_other_player_cannot_take_group_and_mixed_ownership_cannot_bind(self):
        with self.assertRaises(ValueError):
            encounter.admit(self.db, 9, self.monsters)
        self.db.owners[-4] = 9
        self.assertIsNone(encounter.bind(self.db, 8, self.monsters))

    def test_incomplete_duplicate_and_unrelated_sacks_do_not_bind(self):
        self.assertIsNone(encounter.bind(self.db, 8, self.monsters[:3]))
        self.assertIsNone(
            encounter.bind(self.db, 8, self.monsters[:3] + self.monsters[:1])
        )
        self.assertIsNone(encounter.bind(Database({}), 8, self.monsters))

    def test_only_owned_complete_winning_fight_settles_exact_objective(self):
        fight = SimpleNamespace(
            id=12,
            phase="finished",
            winner=0,
            actors={
                8: SimpleNamespace(team=0),
                **{actor: SimpleNamespace(team=1) for actor in (-1, -2, -3, -4)},
            },
            rii_area_lesson_contract={
                "owner": 8,
                "targets": [-1, -2, -3, -4],
                "hits": 4,
                "actions": [1, 2, 3, 4],
            },
        )
        members = [{"character_id": 8, "account_id": 3, "session_generation": "gen"}]
        db = Mock()
        db.execute.return_value.fetchone.side_effect = [
            {"payload": encounter.payload(8, actor)} for actor in (-1, -2, -3, -4)
        ] + [
            {"status": "finished", "fight_kind": "pve", "team": 0},
            {"data": {"native": {"d": 5143}}},
        ]
        store = Mock()
        store.character.return_value = {"id": 8, "account_id": 3}
        store.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
        before = {"running": [5143], "objectives": [10608]}
        after = {"running": [5143], "objectives": [10608, 10609]}
        with patch.object(storage, "load_locked", return_value=before), patch.object(
            storage, "record_event", return_value=True
        ) as receipt, patch.object(storage, "store") as save, patch.object(
            mission_progress, "advance_objective", return_value=(after, [], [10609], [])
        ) as advance, patch.object(
            wire, "changes", return_value=[(13832, b"ok")]
        ):
            result = encounter.settle_participants(
                db, store, fight, members, self.monsters
            )
        self.assertEqual(result, {3: [(13832, b"ok")]})
        self.assertEqual(advance.call_args.args[2], 10609)
        self.assertEqual(receipt.call_args.args[2], "rii-lesson-objective:10609")
        save.assert_called_once_with(db, 8, after)

    def test_incomplete_or_losing_fight_never_queries_or_settles(self):
        fight = SimpleNamespace(
            id=12,
            phase="finished",
            winner=1,
            rii_area_lesson_contract={
                "owner": 8,
                "targets": [-1, -2, -3, -4],
                "hits": 3,
            },
        )
        db = Mock()
        self.assertEqual(
            encounter.settle_participants(db, Mock(), fight, [], self.monsters), {}
        )
        db.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
