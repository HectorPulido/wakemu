"""Isolated optional-route review: real dispatch, no native catalog or live DB."""
import copy
import json
import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import dungeon_optional_ground_items as ground
from wakfu_server import dungeon_optional_encounters as optional
from wakfu_server import dungeon_progression as progression
from wakfu_server import dungeon_fight_binding as binding
from wakfu_server import dungeon_auto_exit


class Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return copy.deepcopy(self.rows[0]) if self.rows else None

    def __iter__(self):
        return iter(copy.deepcopy(self.rows))


class StateDB:
    def __init__(self):
        self.run = dict(
            instance_id=10,
            party_id=20,
            status="completed",
            current_room=3,
            revision=4,
            rooms=[{"order": n} for n in (1, 2, 3)],
            catalog_hash="a" * 64,
        )
        self.access = dict(
            instance_id=10,
            room_order=4,
            source_order=4,
            asset_map_id=910,
            group_id=30,
            status="active",
            revision=1,
            catalog_hash="a" * 64,
        )
        self.encounter = dict(
            fight_id=99,
            instance_id=10,
            room_order=4,
            player_team=0,
            status="active",
            encounter_scope="optional",
            result=None,
        )
        self.commands = []
        self.member = True
        self.participant_team = 0

    def execute(self, sql, args=()):
        self.commands.append((sql, args))
        if "JOIN combat_fights f ON f.id=e.fight_id" in sql:
            return Rows([])
        if sql.startswith("SELECT"):
            if "FROM dungeon_optional_access" in sql:
                return Rows([self.access])
            if "FROM dungeon_room_runs" in sql:
                return Rows([self.run])
            if "FROM dungeon_room_encounters" in sql:
                return Rows(
                    [self.encounter] if self.encounter["fight_id"] == args[0] else []
                )
            if "FROM combat_fights" in sql:
                return Rows([dict(status="aborted")])
            if "FROM dungeon_instance_members" in sql:
                return Rows([{"?column?": 1}] if self.member else [])
            if "FROM combat_fight_participants" in sql:
                return Rows([dict(team=self.participant_team)])
        if sql.startswith("INSERT INTO dungeon_room_encounters"):
            self.encounter = dict(
                fight_id=args[0],
                instance_id=args[1],
                room_order=args[2],
                player_team=args[3],
                encounter_scope="optional",
                status="active",
                result=None,
            )
            return Rows([])
        if sql.startswith("UPDATE dungeon_optional_access SET status=%s"):
            self.access.update(status=args[0], revision=args[1])
            return Rows([])
        if sql.startswith("UPDATE dungeon_optional_access SET status='active'"):
            self.access["status"] = "active"
            return Rows([])
        if sql.startswith("UPDATE dungeon_optional_access SET status='available'"):
            self.access["status"] = "available"
            return Rows([])
        if sql.startswith("UPDATE dungeon_room_encounters SET status=%s"):
            self.encounter.update(
                status=args[0], result_revision=args[1], result=json.loads(args[2])
            )
            return Rows([])
        if sql.startswith("UPDATE dungeon_room_encounters SET status='aborted'"):
            self.encounter.update(
                status="aborted", result_revision=args[0], result=json.loads(args[1])
            )
            return Rows([])
        raise AssertionError("Unexpected SQL: " + sql)


class OptionalGroundReviewTests(unittest.TestCase):
    def test_registered_native_request_is_exact_and_closed_before_any_io(self):
        body = struct.pack(">iqii", 7952, 123, -4, 55)
        self.assertEqual(ground.action_class(body), "bIg")
        self.assertEqual(
            ground.decode(body), dict(action_id=7952, source_uid=123, x=-4, y=55)
        )
        self.assertIsNone(ground.action_class(struct.pack(">i", 1)))
        for malformed in (body[:-1], body + b"\0", struct.pack(">iqii", 7952, 0, 1, 2)):
            with self.assertRaises(ValueError):
                ground.action_class(malformed)
        store = SimpleNamespace(
            connection=lambda: self.fail("Disabled access touched DB")
        )
        disabled = copy.deepcopy(ground.rules()[0])
        disabled["enabled"] = False
        with patch.object(ground, "rules", return_value=[disabled]):
            with self.assertRaisesRegex(ValueError, "not yet qualified"):
                ground.use(store, None, 1, "lease", 2, body)
        rule = disabled
        self.assertEqual(rule["native_parameters"], ["5", "5000"])
        self.assertFalse(rule["enabled"])
        self.assertEqual(
            rule["ground_authority"]["targets"][0]["position"], [21, 51, 0]
        )

    def test_exact_ground_and_approach_do_not_invent_distance_or_height(self):
        rule = dict(
            ground_authority=dict(
                map_id=910,
                targets=[
                    dict(
                        position=[1, 2, -2],
                        approach_cells=[[2, 2, -2]],
                        source_sha256="b" * 64,
                    )
                ],
            )
        )
        request = dict(x=1, y=2)
        actor = dict(map_id=910, x=2, y=2, z=-2)
        topology = dict(asset_map_id=910, rooms=[dict(cells=[[1, 2, -2], [2, 2, -2]])])
        self.assertEqual(ground.target_for(rule, request, actor, topology), [1, 2, -2])
        for bad in (dict(actor, z=0), dict(actor, map_id=911), dict(actor, x=100)):
            with self.assertRaises(ValueError):
                ground.target_for(rule, request, bad, topology)
        with self.assertRaises(ValueError):
            ground.target_for(rule, dict(x=3, y=2), actor, topology)

    def test_victory_and_defeat_dispatch_preserve_main_run_and_replay(self):
        for winner, expected in ((0, "victory"), (1, "available")):
            db = StateDB()
            before = copy.deepcopy(db.run)
            fight = SimpleNamespace(id=99, phase="finished", winner=winner)
            result = progression.settle_encounter(db, fight)
            self.assertEqual(db.run, before)
            self.assertEqual(db.access["status"], expected)
            self.assertEqual(result["encounter_scope"], "optional")
            self.assertEqual(
                (result["current_room"], result["revision"], result["completed"]),
                (3, 4, True),
            )
            writes = sum(sql.startswith("UPDATE") for sql, args in db.commands)
            replay = progression.settle_encounter(db, fight)
            self.assertTrue(replay["replay"])
            self.assertEqual(
                sum(sql.startswith("UPDATE") for sql, args in db.commands), writes
            )
            self.assertFalse(
                any("UPDATE dungeon_room_runs" in sql for sql, args in db.commands)
            )
            self.assertIsNone(
                dungeon_auto_exit.completion_destination(
                    result, dict(policy="local_accessible_anchor_policy")
                )
            )

    def test_abort_retry_uses_same_optional_receipt_without_main_stele(self):
        db = StateDB()
        before = copy.deepcopy(db.run)
        aborted = binding.abort_room_encounter(db, 99)
        self.assertTrue(aborted["aborted"])
        self.assertEqual(db.access["status"], "available")
        self.assertEqual(db.run, before)
        calls = []
        difficulty = SimpleNamespace(
            freeze_encounter=lambda *a, **k: calls.append((a, k))
        )
        with patch.dict(sys.modules, {"wakfu_server.dungeon_difficulty": difficulty}):
            bound = binding.bind_room_group(db, (910, 10, 30), 76, 100, player_team=0)
        self.assertEqual(bound["encounter_scope"], "optional")
        self.assertEqual(db.access["group_id"], 30)
        self.assertEqual(db.access["status"], "active")
        self.assertEqual(db.run, before)
        self.assertEqual(len(calls), 1)
        self.assertFalse(
            any(
                "dungeon_stele" in sql or "inventory_items" in sql
                for sql, args in db.commands
            )
        )

    def test_optional_actor_membership_and_native_area_stay_authoritative(self):
        db = StateDB()
        db.access["status"] = "available"
        db.member = False
        with self.assertRaisesRegex(ValueError, "authorized"):
            optional.bind(db, db.run, db.access, 76, 100, player_team=0)
        self.assertFalse(any(sql.startswith("INSERT") for sql, args in db.commands))
        cfg = dict(
            compiled_plan=dict(document_sha256="a" * 64),
            topology=dict(rooms=[dict(order=4, cells=[[1, 2, 0], [2, 2, 0]])]),
        )
        self.assertEqual(
            optional.combat_cells(db, (910, 10, 30), cfg, db.run, [[1, 2, 0]]),
            frozenset(((1, 2, 0), (2, 2, 0))),
        )
        with self.assertRaisesRegex(ValueError, "outside native terrain"):
            optional.combat_cells(db, (910, 10, 30), cfg, db.run, [[1, 2, 1]])
        with self.assertRaisesRegex(ValueError, "configuration changed"):
            optional.combat_cells(
                db,
                (910, 10, 30),
                dict(cfg, compiled_plan=dict(document_sha256="c" * 64)),
                db.run,
                [[1, 2, 0]],
            )


if __name__ == "__main__":
    unittest.main()
