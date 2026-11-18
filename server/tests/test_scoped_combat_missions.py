"""Focused coverage for the reviewed regional monster mission adapter."""

from hashlib import sha256
import json
import sys
from types import ModuleType
import unittest
from unittest.mock import patch
from copy import deepcopy

from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from wakfu_server.achievements import scoped_combat_missions as scoped
from wakfu_server.achievements import storage


class Result:
    def __init__(self, rows=(), row=None):
        self.rows = list(rows)
        self.row = row

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.row


class FakeDB:
    """Small transactional ledger for testing pending-event retry semantics."""

    def __init__(self, state):
        self.info = type(
            "Info", (), {"transaction_status": TransactionStatus.INTRANS}
        )()
        self.state = state
        self.events = {}

    class _Transaction:
        def __init__(self, db):
            self.db = db

        def __enter__(self):
            self.snapshot = deepcopy(self.db.events)
            return self.db

        def __exit__(self, exc_type, exc, traceback):
            if exc_type is not None:
                self.db.events = self.snapshot
            return False

    def transaction(self):
        return self._Transaction(self)

    def execute(self, query, params=()):
        if "mission_toolkit_event_index" in query:
            return Result(rows=[{"reference": 2135}])
        if "SELECT id FROM characters" in query:
            return Result(row={"id": params[0]})
        if "character_achievement_progress" in query:
            return Result(row={"state": self.state})
        if query.startswith("INSERT INTO character_achievement_events"):
            character_id, key, signature, payload = params
            if isinstance(payload, Jsonb):
                payload = payload.obj
            identity = (character_id, key)
            if identity in self.events:
                return Result()
            self.events[identity] = {
                "signature": signature,
                "payload": deepcopy(payload),
            }
            return Result(row={"event_key": key})
        if "character_achievement_events" in query and "LIKE" in query:
            character_id, pattern = params
            prefix = pattern[:-1]
            rows = [
                {"event_key": key, **deepcopy(value)}
                for (owner, key), value in self.events.items()
                if owner == character_id and key.startswith(prefix)
            ]
            return Result(rows=rows)
        if "character_achievement_events" in query:
            character_id, key = params
            record = self.events.get((character_id, key))
            if record is None:
                return Result()
            if "SELECT 1" in query:
                return Result(row={"?column?": 1})
            if "SELECT signature" in query:
                return Result(row={"signature": record["signature"]})
            return Result(row={"payload": deepcopy(record["payload"])})
        raise AssertionError(f"Unexpected database query: {query}")


class ScopedCombatMissionTests(unittest.TestCase):
    def setUp(self):
        self.scope = next(
            row for row in scoped.declarations()["scopes"] if row["reference"] == 2135
        )

    def test_native_declaration_and_original_xy_qualification(self):
        self.assertEqual(
            (2135, 4228, 828),
            (
                self.scope["quest_id"],
                self.scope["objective_id"],
                self.scope["variable_id"],
            ),
        )
        self.assertEqual([527], self.scope["maps"])
        self.assertEqual([66701, 76201], self.scope["regions"])
        self.assertEqual([563], self.scope["families"])

        original = [
            {"id": 11, "ref": 10, "x": 1, "y": 1},
            {"id": 12, "ref": 10, "x": 2, "y": 2},
            {"id": 13, "ref": 20, "x": 3, "y": 3},
            {"id": 14, "ref": 10, "x": 4, "y": 4},
            {"id": 15, "ref": 10},  # Old encounter snapshots may lack XY.
        ]
        defeated = [(11, 10), (12, 10), (13, 20), (14, 10), (15, 10)]
        # The winning character's admission region is deliberately outside the
        # scope. The defeated original monsters' frozen world XY decides scope.
        scene = {"map_id": 527, "instance_id": 0, "admission_regions": {7: 90001}}

        selected = scoped.qualifying_kills(
            self.scope,
            original,
            defeated,
            scene,
            region_at=lambda _map, x, _y: {
                1: 66701,
                2: 76201,
                3: 66701,
                4: 90001,
            }[x],
            family_of=lambda breed: {10: 563, 20: 564}.get(breed),
        )
        self.assertEqual(((11, 10), (12, 10)), selected)

    def test_wrong_map_or_private_instance_never_qualifies(self):
        original = [{"id": 11, "ref": 10, "x": 1, "y": 1}]
        defeated = [(11, 10)]
        for scene in (
            {"map_id": 528, "instance_id": 0},
            {"map_id": 527, "instance_id": 44},
        ):
            with self.subTest(scene=scene):
                self.assertEqual(
                    (),
                    scoped.qualifying_kills(
                        self.scope,
                        original,
                        defeated,
                        scene,
                        region_at=lambda *_: 66701,
                        family_of=lambda _breed: 563,
                    ),
                )

    def test_frozen_admission_requires_the_durable_defeated_group_lease(self):
        original = [{"id": 11, "ref": 10, "x": 1, "y": 2, "z": 0}]
        scene = {
            "map_id": 527,
            "instance_id": 0,
            # Positive owner admission is required; it may be outside target regions.
            "admission_regions": {7: 90001},
            "group_lease": ((527, 0, 6), "generation-a", 99, 4),
        }
        db = type(
            "GroupDB",
            (),
            {
                "execute": lambda _self, *_args: Result(
                    row={
                        "members": [dict(original[0])],
                        "status": "defeated",
                        "revision": 5,
                    }
                )
            },
        )()
        character = {"account_id": 7}

        self.assertTrue(scoped._admission(db, character, 99, original, scene))
        wrong_map_lease = dict(scene, group_lease=((528, 0, 6), "generation-a", 99, 4))
        self.assertFalse(
            scoped._admission(db, character, 99, original, wrong_map_lease)
        )

        changed_origin = [dict(original[0], x=8)]
        with self.assertRaisesRegex(
            ValueError, "differs from its durable defeated world group"
        ):
            scoped._admission(db, character, 99, changed_origin, scene)

    def test_staged_job_survives_processor_rollback_and_replays_once(self):
        character = {"id": 3, "account_id": 7, "map_id": 527, "instance_id": 0}
        monster = {"id": 11, "ref": 10, "x": 1, "y": 1}
        event = {
            "fight_id": 99,
            "original_breeds": [10],
            "original_monsters": [[11, 10]],
            "completed_dungeon_id": None,
        }
        fight = type(
            "Fight",
            (),
            {"id": 99, "actors": {3: type("Actor", (), {"effective_level": 20})()}},
        )()
        scene = {
            "map_id": 527,
            "instance_id": 0,
            "admission_regions": {7: 90001},
            "group_lease": ((527, 0, 6), "frozen-owned-admission", 99, 4),
        }
        db = FakeDB(
            {
                "variables": {},
                "objectives": [],
                "running": [2135],
                "completed": [],
                "tracking": [],
                "recent": [],
                "completion_dates": {},
            }
        )
        with db.transaction():
            storage.record_event(db, character["id"], "fight:99", event)
        fake_monsters = ModuleType("wakfu_server.monsters")
        fake_monsters.REFERENCES = {10: {"family_id": 563}}
        fake_native_catalog = ModuleType("wakfu_server.native_catalog")
        fake_native_catalog.release = lambda: scoped.declarations()[
            "native_catalog_revision"
        ]
        fake_territory_cells = ModuleType("wakfu_server.territory_cells")
        fake_territory_cells.region_at = lambda *_: 66701

        with (
            patch("wakfu_server.achievements.service._owner"),
            patch(
                "wakfu_server.achievements.service._event", return_value=event
            ) as event_mock,
            patch.object(scoped, "_admission", return_value=True),
            patch.object(scoped, "_drop_source", return_value=True),
            patch.object(scoped, "_eligible", return_value=True) as eligible_mock,
            patch.object(scoped, "_profile", return_value=True),
            patch.dict(
                sys.modules,
                {
                    "wakfu_server.monsters": fake_monsters,
                    "wakfu_server.native_catalog": fake_native_catalog,
                    "wakfu_server.territory_cells": fake_territory_cells,
                },
            ),
        ):
            with db.transaction():
                staged = scoped.stage(
                    db,
                    object(),
                    character,
                    fight,
                    [monster],
                    [(11, 10)],
                    scene,
                    fresh=True,
                )
            pending_key = "regional-mission-pending:99:2135"
            self.assertEqual(1, staged)
            self.assertIn((3, pending_key), db.events)
            with db.transaction():
                self.assertEqual(
                    0,
                    scoped.stage(
                        db,
                        object(),
                        character,
                        fight,
                        [monster],
                        [(11, 10)],
                        scene,
                        fresh=True,
                    ),
                )

            def fail_settlement(*_args):
                raise RuntimeError("simulated count processor failure")

            with patch.object(
                scoped.mission_toolkit, "settle", side_effect=fail_settlement
            ):
                with self.assertRaisesRegex(RuntimeError, "processor failure"):
                    with db.transaction():
                        scoped.process(db, object(), character, 99)
            self.assertIn((3, pending_key), db.events)

            successful_settlements = []

            def durable_settlement(
                _db, _store, _character, token, kind, reference, quantity
            ):
                successful_settlements.append((token, kind, reference, quantity))
                receipt_key = (
                    f"mission-toolkit:{kind}:{reference}:"
                    + sha256(token.encode()).hexdigest()
                )
                storage.record_event(
                    db,
                    character["id"],
                    receipt_key,
                    {"kind": kind, "reference": reference, "quantity": quantity},
                )
                return ["objective-update"]

            with patch.object(
                scoped.mission_toolkit, "settle", side_effect=durable_settlement
            ):
                with db.transaction():
                    result = scoped.process(db, object(), character, 99)
                self.assertEqual(["objective-update"], result)
                with db.transaction():
                    replay = scoped.process(db, object(), character, 99)
            self.assertEqual([], replay)
            self.assertEqual(
                [("fight:99:scope:2135", "scoped_monster_defeat", 2135, 1)],
                successful_settlements,
            )
            self.assertIn((3, pending_key + ":done"), db.events)
            db.events[(3, pending_key)]["payload"]["quantity"] = 2
            with self.assertRaisesRegex(ValueError, "receipt digest changed"):
                with db.transaction():
                    scoped.process(db, object(), character, 99)

            # A quest assigned after the fight has no frozen pending job to
            # discover, so processing that old fight cannot backfill it.
            old_event = dict(event, fight_id=100)
            old_fight = type(
                "Fight",
                (),
                {
                    "id": 100,
                    "actors": {3: type("Actor", (), {"effective_level": 20})()},
                },
            )()
            old_db = FakeDB(db.state)
            with old_db.transaction():
                storage.record_event(old_db, character["id"], "fight:100", old_event)
            event_mock.return_value = old_event
            eligible_mock.return_value = False
            with old_db.transaction():
                self.assertEqual(
                    0,
                    scoped.stage(
                        old_db,
                        object(),
                        character,
                        old_fight,
                        [monster],
                        [(11, 10)],
                        scene,
                        fresh=True,
                    ),
                )
            eligible_mock.return_value = True
            with old_db.transaction():
                self.assertEqual([], scoped.process(old_db, object(), character, 100))

    def test_drop_award_source_requires_matching_digest_and_non_dungeon_fight(self):
        snapshot = {
            "account_id": 7,
            "character_id": 3,
            "fight_id": 99,
            "can_loot": True,
            "fight_context": {"in_dungeon": False, "in_infinite_waves": False},
            "monsters": [{"actor_id": 11, "reference": 10}],
        }
        digest = sha256(
            json.dumps(
                snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
        db = type(
            "DropDB",
            (),
            {
                "execute": lambda _self, *_args: Result(
                    row={"snapshot": snapshot, "snapshot_sha256": digest}
                )
            },
        )()
        character = {"id": 3, "account_id": 7}
        event = {"original_monsters": [[11, 10]]}
        self.assertTrue(scoped._drop_source(db, character, 99, event))

        snapshot["fight_context"]["in_dungeon"] = True
        digest = sha256(
            json.dumps(
                snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
        db.execute = lambda *_args: Result(
            row={"snapshot": snapshot, "snapshot_sha256": digest}
        )
        self.assertFalse(scoped._drop_source(db, character, 99, event))

        snapshot["fight_context"]["in_dungeon"] = False
        db.execute = lambda *_args: Result(
            row={"snapshot": snapshot, "snapshot_sha256": "bad"}
        )
        with self.assertRaisesRegex(ValueError, "source digest changed"):
            scoped._drop_source(db, character, 99, event)


if __name__ == "__main__":
    unittest.main()
