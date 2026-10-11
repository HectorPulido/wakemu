"""Isolated PostgreSQL proof for Sliptorium's native backward exit witness."""
import hashlib
import json
import os
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

from postgres_case import PostgresCase
from wakfu_server import combat_group_store, dungeon_instances, dungeon_transport
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.maps import (
    dungeon_doors,
    dungeon_exit,
    dungeon_hydration,
    dungeon_native_flow,
    dungeon_progression,
    dungeon_runtime,
    dungeon_runtime_config,
    dungeon_transition_delivery,
)

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/reports/dungeons/SLIPTORIUM-BACKWARD-EXIT-CANDIDATE.json"


class SliptoriumBackwardExitPostgresTests(PostgresCase):
    from test_dungeon_instances import DungeonInstanceTests as Fixture

    player = Fixture.player
    party = Fixture.party

    def test_completed_run_can_backtrack_to_witnessed_exterior_exit(self):
        report = json.loads(REPORT.read_text())
        self.assertEqual(report["status"], "offline_configuration_prepared")
        path = ROOT / report["path"]
        candidate_config_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        config = json.loads(path.read_text())
        self.assertEqual(
            dungeon_runtime_config.canonical_hash(config),
            report["configuration_sha256"],
        )
        self.assertEqual(config["route"]["key"], "native_dungeon_48")
        witness = config["topology"]["completed_exit_witness"]
        self.assertEqual(witness["source_id"], 14012)
        self.assertEqual(witness["room_order"], 2)
        self.assertEqual(witness["steps"][0]["source_id"], 16126)
        self.assertEqual(witness["steps"][0]["destination_room"], 2)
        self.assertEqual(witness["steps"][1]["source_id"], 14012)

        self.addCleanup(
            setattr, dungeon_instances, "_ROUTES", dungeon_instances._ROUTES
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_runtime_routes',%s::jsonb) "
                "ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (json.dumps(dict(schema_version=1, routes=[config["route"]])),),
            )
        dungeon_instances.load_runtime_routes(self.store)
        self.store.clock = lambda: 2_000_000_000.0
        runtime_config = dungeon_runtime_config.prepare_configuration(
            config["compiled_plan"],
            config["topology"],
            config["route"],
            version=10001,
            provenance=config["provenance"],
        )
        route = runtime_config["route"]
        topology = runtime_config["topology"]
        geometry = map_geometry(route["start_map_id"])
        groups = combat_group_store.PersistentGroups(self.store)
        with self.store.connection() as db:
            dungeon_runtime_config.install_configuration(db, runtime_config)

        members, party_id = self.party(3)
        with self.store.connection() as db:
            for member in members:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=0 WHERE id=%s",
                    (route["entry_map_id"], member["character"]["id"]),
                )

        def enter(member):
            return dungeon_transport.enter(
                self.store,
                member["account"],
                member["generation"],
                member["character"]["id"],
                route["entry_map_id"],
                struct.pack(
                    ">qiBi", route["entry_object_id"], route["destination_id"], 0, 2
                ),
                criterion_allowed=lambda actor, criterion: True,
                source_allowed=lambda actor, source: True,
                resolve_destination=dungeon_runtime.entry_destination,
                initialize_instance=lambda db, session: dungeon_runtime.initialize_instance(
                    db, session, groups=groups, geometry=geometry
                ),
            )

        run = enter(members[0])
        instance = run["instance_id"]
        self.assertEqual(len(run["transition"]["members"]), 3)

        def deliver(member):
            identity = member["character"]["id"]
            events = dungeon_instances.pending_transitions(
                self.store, member["account"], member["generation"], identity
            )
            self.assertEqual(len(events), 1)
            event = events[0]
            location = {
                key: event["source_" + key]
                for key in ("map_id", "instance_id", "x", "y", "z")
            }
            location["x"] += 1

            def bootstrap(pending):
                plan = dungeon_hydration.prepare_transition(
                    self.store,
                    member["account"],
                    member["generation"],
                    identity,
                    pending,
                )
                self.assertEqual(
                    plan.character["instance_id"], pending["destination_instance_id"]
                )
                self.assertTrue(plan.packets)
                return True

            result = dungeon_transition_delivery.deliver_pending_transitions(
                self.store,
                member["account"],
                member["generation"],
                identity,
                worker_generation=member["generation"],
                current_location=lambda: location,
                in_fight=lambda: False,
                bootstrap=bootstrap,
            )
            self.assertEqual(result["state"], "delivered")

        for member in members:
            deliver(member)

        def state_by_source(completed):
            state_packets = dungeon_native_flow.packets(
                topology,
                map_id=route["start_map_id"],
                instance_id=instance,
                unlocked_room=3,
                completed=completed,
            )
            return {
                struct.unpack_from(">q", body)[0]: body
                for opcode, body in state_packets
                if opcode == 12344
            }

        def settle(room_order):
            with self.store.connection() as db:
                spawned = dungeon_runtime.ensure_current_room(
                    db, groups, instance, geometry
                )
                self.assertEqual(spawned["room_order"], room_order)
                fight_id = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                ).fetchone()["id"]
                for member in members:
                    db.execute(
                        "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                        "VALUES(%s,%s,%s,0)",
                        (fight_id, member["character"]["id"], member["account"]),
                    )
                dungeon_progression.bind_encounter(
                    db,
                    instance,
                    party_id,
                    members[0]["character"]["id"],
                    fight_id,
                    player_team=0,
                )
                db.execute(
                    "UPDATE combat_fights SET status='finished' WHERE id=%s",
                    (fight_id,),
                )
                finished = SimpleNamespace(id=fight_id, phase="finished", winner=0)
                return dungeon_progression.settle_encounter(db, finished)

        def use_native_door(source_id, destination_id):
            binding = next(
                door for door in topology["doors"] if door["source_id"] == source_id
            )
            approach = binding["native_approach_cells"][0]
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
                    (*approach, members[0]["character"]["id"]),
                )
            moved = dungeon_doors.advance(
                self.store,
                members[0]["account"],
                members[0]["generation"],
                members[0]["character"]["id"],
                struct.pack(">qiBi", source_id, destination_id, 0, 2),
                source_allowed=lambda actor, source: source["id"] == source_id
                and [actor[key] for key in ("x", "y", "z")]
                in binding["native_approach_cells"],
                room_for_position=lambda map_id, x, y, z: dungeon_runtime.room_for_position(
                    runtime_config, map_id, x, y, z
                ),
                in_fight=lambda _: False,
            )
            self.assertEqual(moved["transition_kind"], "door")
            for member in members:
                deliver(member)
            for member in members:
                actor = self.store.character(
                    member["account"], member["character"]["id"]
                )
                self.assertEqual(
                    [actor[key] for key in ("x", "y", "z")],
                    binding["destination_position"],
                )

        # Room 1 victory unlocks room 2; room 2 victory unlocks room 3.
        self.assertFalse(settle(1)["completed"])
        use_native_door(14010, 693)
        room2_result = settle(2)
        self.assertFalse(room2_result["completed"])
        self.assertEqual(room2_result["current_room"], 3)
        before_final = state_by_source(completed=False)
        self.assertIn(14012, before_final)
        self.assertEqual((before_final[14012][19], before_final[14012][20]), (0, 0))
        use_native_door(27552, 899)

        final = settle(3)
        self.assertTrue(final["completed"])
        after_final = state_by_source(completed=True)
        self.assertIn(14012, after_final)
        self.assertEqual((after_final[14012][19], after_final[14012][20]), (1, 1))

        # Use the actual native return object from the final room to room 2.
        use_native_door(16126, 900)
        exterior = next(
            item
            for item in topology["physical_exit_objects"]
            if item["source_id"] == 14012
        )
        for member in members:
            approach = exterior["native_approach_cells"][0]
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
                    (*approach, member["character"]["id"]),
                )
            result = dungeon_exit.leave(
                self.store,
                member["account"],
                member["generation"],
                member["character"]["id"],
                struct.pack(">qiBi", 14012, 692, 0, 2),
                source_allowed=lambda actor, source: source["id"] == 14012
                and [actor[key] for key in ("x", "y", "z")]
                in exterior["native_approach_cells"],
                in_fight=lambda _: False,
            )
            self.assertEqual(result["map_id"], 323)
            deliver(member)

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
                    "SELECT count(*) AS n FROM dungeon_room_spawn_receipts WHERE instance_id=%s",
                    (instance,),
                ).fetchone()["n"],
                3,
            )

        if os.environ.get("WAKFU_DUNGEON_LIFECYCLE_AUDIT"):
            audit_path = Path(os.environ["WAKFU_DUNGEON_LIFECYCLE_AUDIT"])
            sources = [
                "server/tests/test_sliptorium_backward_exit_postgres.py",
                "server/wakfu_server/maps/dungeon_doors.py",
                "server/wakfu_server/maps/dungeon_object_states.py",
                "server/wakfu_server/maps/dungeon_progression.py",
                "server/wakfu_server/maps/dungeon_exit.py",
                "server/migrations/099_native_npc_reward_levels.sql",
                "docs/reports/dungeons/SLIPTORIUM-BACKWARD-EXIT-CANDIDATE.json",
            ]
            source_hashes = {
                source: hashlib.sha256((ROOT / source).read_bytes()).hexdigest()
                for source in sources
            }
            report_key = "candidate_report:" + str(REPORT.relative_to(ROOT))
            source_hashes[report_key] = hashlib.sha256(REPORT.read_bytes()).hexdigest()
            lineage_report = os.environ.get("WAKFU_DUNGEON_SOURCE_REPORT")
            if lineage_report:
                lineage_path = Path(lineage_report)
                if not lineage_path.is_absolute():
                    lineage_path = ROOT / lineage_path
                lineage_key = "candidate_source_report:" + str(
                    lineage_path.relative_to(ROOT)
                )
                source_hashes[lineage_key] = hashlib.sha256(
                    lineage_path.read_bytes()
                ).hexdigest()
            source_hashes[report["path"]] = candidate_config_hash
            result = dict(
                scope=(
                    "Isolated PostgreSQL run: three room victories, witnessed backward native transport, "
                    "intermediate exterior hidden before completion and usable after completion; no boss AI/spells simulated"
                ),
                runtime_activated=False,
                source_sha256=source_hashes,
                records=[
                    dict(
                        route=route["key"],
                        name=report["name"],
                        status="isolated_postgres_backward_exit_lifecycle_passed",
                        player_count=3,
                        room_count=3,
                        backward_native_transport="16126_to_room_2",
                        intermediate_exit_hidden_until_final_victory=True,
                        completed_exit_usable_after_final_victory=True,
                        native_exit="14012_to_map_323",
                        boss_mechanics="not_simulated",
                    )
                ],
            )
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            audit_path.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
