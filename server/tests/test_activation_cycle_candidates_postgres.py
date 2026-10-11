"""Isolated durable lifecycle for exact native activation-cell candidates."""
import json
import os
from pathlib import Path
import struct
import sys
from types import SimpleNamespace

from postgres_case import PostgresCase
from test_dungeon_instances import DungeonInstanceTests as Fixture
from wakfu_server import (
    combat_group_store,
    dungeon_exit,
    dungeon_instances,
    dungeon_native_flow,
)
from wakfu_server import (
    dungeon_progression,
    dungeon_runtime,
    dungeon_runtime_config,
    dungeon_transport,
)
from wakfu_server.combat_terrain import map_geometry

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server/tools"))
from audit_classic_dungeon_hybrid_structure import audit_trigger_frontiers
from extract_native_door_flow import shortest_path
from validate_prepared_physical_flows import movement


class ActivationCyclePostgresTests(PostgresCase):
    player = Fixture.player
    party = Fixture.party

    def test_riktus_four_encounters_and_literal_final_frontier(self):
        self.lifecycle("RIKTUS-ELITE-ACTIVATION-CANDIDATE-V18-20261010.json")

    def test_base_susurro_four_encounters_and_nine_native_zone_cells(self):
        self.lifecycle("BASE-SUSURRO-ZONE-CANDIDATE-V22-20261010.json")

    def lifecycle(self, report_name):
        self.store.clock = lambda: 2_000_000_000.0
        candidate = json.loads(
            (ROOT / "docs/reports/dungeons" / report_name).read_text()
        )["records"][0]
        config = json.loads((ROOT / candidate["path"]).read_text())
        topology, route = config["topology"], config["route"]
        geometry = topology["exploration_geometry"]
        native = next(
            r
            for r in json.loads(
                (ROOT / "docs/reports/dungeons/inventory.json").read_text()
            )["records"]
            if r["key"] == candidate["key"]
        )
        evidence, issues = audit_trigger_frontiers(native, topology, geometry)
        self.assertEqual(issues, [])
        self.assertTrue(evidence["configured_frontiers"])
        original_routes = dungeon_instances._ROUTES
        self.addCleanup(setattr, dungeon_instances, "_ROUTES", original_routes)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_runtime_routes',%s::jsonb) ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (json.dumps(dict(schema_version=1, routes=[route])),),
            )
            dungeon_runtime_config.install_configuration(db, config)
        dungeon_instances.load_runtime_routes(self.store)
        members, party_id = self.party(6)
        for member in members:
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=0 WHERE id=%s",
                    (route["entry_map_id"], member["character"]["id"]),
                )
        groups = combat_group_store.PersistentGroups(self.store)
        combat = map_geometry(route["start_map_id"])
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
                db, session, groups=groups, geometry=combat
            ),
        )
        instance = run["instance_id"]
        self.assertEqual(len(run["transition"]["members"]), 6)
        victories = []
        for order, room in enumerate(topology["rooms"], 1):
            with self.store.connection() as db:
                frontier = db.execute(
                    "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                    (instance,),
                ).fetchone()["current_room"]
                self.assertEqual(frontier, order)
                actor = db.execute(
                    "SELECT x,y,z FROM characters WHERE id=%s",
                    (members[0]["character"]["id"],),
                ).fetchone()
                start = [actor[key] for key in ("x", "y", "z")]
                gates = topology.get("physical_doors", []) + topology.get(
                    "position_trigger_gates", []
                )
                blocked = [
                    gate["position"]
                    for gate in gates
                    if gate["destination_room"] > frontier
                ]
                walk = shortest_path(
                    geometry["edges"], start, room["anchor"], set(map(tuple, blocked))
                )
                self.assertTrue(
                    walk, "Native party ingress must reach the current encounter"
                )
                endpoint = dungeon_native_flow.validate_movement(
                    topology, movement(walk), unlocked_room=frontier
                )
                for member in members:
                    db.execute(
                        "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
                        (*endpoint, member["character"]["id"]),
                    )
                spawned = dungeon_runtime.ensure_current_room(
                    db, groups, instance, combat
                )
                self.assertEqual(spawned["room_order"], order)
                count = db.execute(
                    "SELECT count(*) AS n FROM dungeon_room_spawn_receipts WHERE instance_id=%s",
                    (instance,),
                ).fetchone()["n"]
                dungeon_runtime.ensure_current_room(db, groups, instance, combat)
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM dungeon_room_spawn_receipts WHERE instance_id=%s",
                        (instance,),
                    ).fetchone()["n"],
                    count,
                )
                for gate in topology.get("position_trigger_gates", []):
                    if gate["source_room"] == order:
                        observation = next(
                            row
                            for row in evidence["configured_frontiers"]
                            if row["source_id"] == gate["source_id"]
                            and row["position"] == gate["position"]
                        )
                        self.assertEqual(
                            [
                                check["status"]
                                for check in observation["runtime_checks"]
                            ],
                            ["rejected", "accepted"],
                        )
                fight = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                ).fetchone()["id"]
                for member in members:
                    db.execute(
                        "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
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
                result = dungeon_progression.settle_encounter(
                    db, SimpleNamespace(id=fight, phase="finished", winner=0)
                )
                self.assertTrue(result["victory"])
                self.assertTrue(
                    dungeon_progression.settle_encounter(
                        db, SimpleNamespace(id=fight, phase="finished", winner=0)
                    )["replay"]
                )
                victories.append(order)
            packets = dungeon_native_flow.packets(
                topology,
                map_id=route["start_map_id"],
                instance_id=instance,
                unlocked_room=min(order + 1, len(topology["rooms"])),
                completed=order == len(topology["rooms"]),
            )
            identities = {
                struct.unpack_from(">q", body)[0]
                for opcode, body in packets
                if opcode == 12344
            }
            trigger_ids = {
                gate["source_id"] for gate in topology.get("position_trigger_gates", [])
            }
            self.assertFalse(
                identities & trigger_ids,
                "Native activation cells must never emit fabricated Door updates",
            )
        exit_binding = next(
            e for e in topology["physical_exit_objects"] if e["room_order"] == 1
        )
        last_anchor = topology["rooms"][-1]["anchor"]
        path = shortest_path(
            geometry["edges"], last_anchor, exit_binding["native_approach_cells"][0]
        )
        self.assertTrue(path)
        dungeon_native_flow.validate_movement(
            topology, movement(path), unlocked_room=len(topology["rooms"])
        )
        point = exit_binding["native_approach_cells"][0]
        for member in members:
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
                    (*point, member["character"]["id"]),
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
                == exit_binding["source_id"]
                and [actor[k] for k in ("x", "y", "z")]
                in exit_binding["native_approach_cells"],
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
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_room_encounters WHERE instance_id=%s AND status='victory'",
                    (instance,),
                ).fetchone()["n"],
                len(topology["rooms"]),
            )
        output_path = os.environ.get("WAKFU_ACTIVATION_CYCLE_AUDIT_DIR")
        if output_path:
            output = Path(output_path)
            output.mkdir(parents=True, exist_ok=True)
            (output / (route["key"] + ".json")).write_text(
                json.dumps(
                    dict(
                        status="isolated_postgresql_lifecycle_passed",
                        candidate_report=report_name,
                        route=route["key"],
                        rooms=len(victories),
                        players=6,
                        victories=victories,
                        native_activation_frontiers=evidence,
                        no_fake_door_packets=True,
                        replay_idempotent=True,
                        native_completed_exit=True,
                    ),
                    indent=2,
                )
                + "\n"
            )
