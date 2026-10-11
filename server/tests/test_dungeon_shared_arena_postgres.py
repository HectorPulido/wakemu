"""Isolated PostgreSQL lifecycle for Arena Danzante's native shared arena."""
import json
import os
import struct
from pathlib import Path
from types import SimpleNamespace
import unittest

from postgres_case import PostgresCase
from test_dungeon_instances import DungeonInstanceTests as _Fixture
from wakfu_server import (
    combat_group_store,
    dungeon_exit,
    dungeon_instances,
    dungeon_native_flow,
    dungeon_progression,
    dungeon_runtime,
    dungeon_runtime_config,
    dungeon_transport,
)
from wakfu_server.combat_terrain import map_geometry

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/reports/dungeons/DANCEHALL-SHARED-ARENA-20261010-V1.json"


class SharedArenaPostgresTests(PostgresCase):
    player = _Fixture.player
    party = _Fixture.party

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0

    def test_six_player_three_receipt_sequence_and_native_exit(self):
        report = json.loads(REPORT.read_text())
        candidate = next(r for r in report["records"] if r["key"] == "native:11")
        config_bytes = (ROOT / candidate["path"]).read_bytes()
        config = json.loads(config_bytes)
        route = config["route"]
        originals = dungeon_instances._ROUTES
        self.addCleanup(setattr, dungeon_instances, "_ROUTES", originals)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_runtime_routes',%s::jsonb) "
                "ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (json.dumps(dict(schema_version=1, routes=[route])),),
            )
        dungeon_instances.load_runtime_routes(self.store)
        prepared = dungeon_runtime_config.prepare_configuration(
            config["compiled_plan"],
            config["topology"],
            route,
            version=10031,
            provenance=config["provenance"],
        )
        with self.store.connection() as db:
            dungeon_runtime_config.install_configuration(db, prepared)
        members, party_id = self.party(6)
        for member in members:
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=0 WHERE id=%s",
                    (route["entry_map_id"], member["character"]["id"]),
                )
        groups = combat_group_store.PersistentGroups(self.store)
        geometry = map_geometry(route["start_map_id"])
        run = dungeon_transport.enter(
            self.store,
            members[0]["account"],
            members[0]["generation"],
            members[0]["character"]["id"],
            route["entry_map_id"],
            struct.pack(
                ">qiBi", route["entry_object_id"], route["destination_id"], 0, 2
            ),
            criterion_allowed=lambda actor, criterion: True,
            source_allowed=lambda actor, source: True,
            resolve_destination=dungeon_runtime.entry_destination,
            initialize_instance=lambda db, session: dungeon_runtime.initialize_instance(
                db,
                session,
                groups=groups,
                geometry=geometry,
            ),
        )
        instance = run["instance_id"]
        self.assertEqual(len(run["transition"]["members"]), 6)
        self.assertEqual(
            run["transition"]["x"], config["topology"]["rooms"][0]["anchor"][0]
        )
        exit_binding = config["topology"]["physical_exit_objects"][0]

        def reject_early_exit():
            for member in members:
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                        (
                            route["start_map_id"],
                            instance,
                            *exit_binding["native_approach_cells"][0],
                            member["character"]["id"],
                        ),
                    )
            with self.assertRaisesRegex(ValueError, "Shared arena exit is locked"):
                dungeon_exit.leave(
                    self.store,
                    members[0]["account"],
                    members[0]["generation"],
                    members[0]["character"]["id"],
                    struct.pack(
                        ">qiBi",
                        exit_binding["source_id"],
                        exit_binding["destination_id"],
                        0,
                        2,
                    ),
                    source_allowed=lambda actor, source: source["id"]
                    == exit_binding["source_id"],
                    in_fight=lambda _: False,
                )
            self.assertEqual(
                self.store.character(
                    members[0]["account"], members[0]["character"]["id"]
                )["instance_id"],
                instance,
            )

        for order in range(1, 4):
            if order < 3:
                reject_early_exit()
            exit_state = dungeon_native_flow.packets(
                prepared["topology"],
                map_id=route["start_map_id"],
                instance_id=instance,
                unlocked_room=order,
                completed=False,
            )
            self.assertEqual(len(exit_state), 1)
            self.assertEqual(exit_state[0][1][19:21], bytes((0, 0)))
            with self.store.connection() as db:
                spawn = dungeon_runtime.ensure_current_room(
                    db, groups, instance, geometry
                )
                self.assertEqual(spawn["room_order"], order)
                self.assertEqual(
                    db.execute(
                        "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                        (instance,),
                    ).fetchone()["current_room"],
                    order,
                )
                fight = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                ).fetchone()["id"]
                for member in members:
                    db.execute(
                        "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                        "VALUES(%s,%s,%s,0)",
                        (fight, member["character"]["id"], member["account"]),
                    )
                dungeon_progression.bind_encounter(
                    db,
                    instance,
                    party_id,
                    members[0]["character"]["id"],
                    fight,
                    player_team=0,
                )
                db.execute(
                    "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight,)
                )
                settled = dungeon_progression.settle_encounter(
                    db, SimpleNamespace(id=fight, phase="finished", winner=0)
                )
                self.assertTrue(settled["victory"])
                replay = dungeon_progression.settle_encounter(
                    db, SimpleNamespace(id=fight, phase="finished", winner=0)
                )
                self.assertTrue(replay["replay"])

        with self.store.connection() as db:
            run_row, pinned = dungeon_runtime.configuration_for_instance(db, instance)
            self.assertEqual(pinned["topology"]["_current_room"], 3)
            progress = db.execute(
                "SELECT status,current_room FROM dungeon_room_runs WHERE instance_id=%s",
                (instance,),
            ).fetchone()
            self.assertEqual(
                (progress["status"], progress["current_room"]), ("completed", 3)
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_room_spawn_receipts WHERE instance_id=%s",
                    (instance,),
                ).fetchone()["n"],
                3,
            )
        exit_packets = dungeon_native_flow.packets(
            pinned["topology"],
            map_id=route["start_map_id"],
            instance_id=instance,
            unlocked_room=3,
            completed=True,
        )
        self.assertTrue(exit_packets)
        self.assertEqual(exit_packets[0][1][19:21], bytes((1, 1)))
        exit_binding = pinned["topology"]["physical_exit_objects"][0]
        self.assertEqual(exit_binding["room_order"], 1)
        for member in members:
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                    (
                        route["start_map_id"],
                        instance,
                        *exit_binding["native_approach_cells"][0],
                        member["character"]["id"],
                    ),
                )
            dungeon_exit.leave(
                self.store,
                member["account"],
                member["generation"],
                member["character"]["id"],
                struct.pack(
                    ">qiBi",
                    exit_binding["source_id"],
                    exit_binding["destination_id"],
                    0,
                    2,
                ),
                source_allowed=lambda actor, source: source["id"]
                == exit_binding["source_id"],
                in_fight=lambda _: False,
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM dungeon_instances WHERE instance_id=%s",
                    (instance,),
                ).fetchone()["status"],
                "closed",
            )

        evidence = os.environ.get("WAKFU_DUNGEON_LIFECYCLE_AUDIT")
        if evidence:
            import hashlib

            paths = (
                "server/tests/test_dungeon_shared_arena_postgres.py",
                "server/local_game_server.py",
                "server/wakfu_server/maps/dungeon_branches.py",
                "server/wakfu_server/maps/dungeon_shared_arena.py",
                "server/wakfu_server/maps/dungeon_runtime.py",
                "server/wakfu_server/maps/dungeon_progression.py",
                "server/wakfu_server/maps/dungeon_exit.py",
                "server/wakfu_server/maps/dungeon_native_flow.py",
                "server/wakfu_server/maps/dungeon_runtime_config.py",
                "server/wakfu_server/maps/dungeon_instances.py",
                "server/migrations/112_dungeon_branch_selection.sql",
            )
            hashes = {
                p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths
            }
            hashes[f"candidate_report:{REPORT.relative_to(ROOT)}"] = hashlib.sha256(
                REPORT.read_bytes()
            ).hexdigest()
            hashes[candidate["path"]] = hashlib.sha256(config_bytes).hexdigest()
            target = ROOT / evidence
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(
                    {
                        "scope": "Isolated PostgreSQL shared-arena lifecycle; six-player entry, three authoritative encounters, replay, and native completion exit",
                        "runtime_activated": False,
                        "source_sha256": hashes,
                        "records": [
                            {
                                "route": route["key"],
                                "rooms": 3,
                                "players": 6,
                                "victory_receipts": 3,
                                "status": "isolated_postgres_shared_arena_passed",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n"
            )


del _Fixture
