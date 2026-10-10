"""Isolated PostgreSQL lifecycle for every offline native physical candidate."""
import json
import hashlib
import os
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

from postgres_case import PostgresCase
from wakfu_server import (
    combat_group_store,
    dungeon_instances,
    dungeon_transport,
    combat_rewards,
    reward_policy,
)
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.maps import (
    dungeon_exit,
    dungeon_progression,
    dungeon_runtime,
    dungeon_runtime_config,
)
from wakfu_server.maps import (
    dungeon_transition_delivery,
    dungeon_hydration,
    dungeon_physical_doors,
)

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/reports/dungeons/AUTOMATIC-COMPLETE-CANDIDATES.json"


class PreparedPhysicalFlowPostgresTests(PostgresCase):
    from test_dungeon_instances import DungeonInstanceTests as Fixture

    player = Fixture.player
    party = Fixture.party

    def test_all_prepared_candidates_party_entry_victories_exit_and_reentry(self):
        if not REPORT.exists():
            self.skipTest("Offline candidate report not generated")
        candidates = [
            r
            for r in json.loads(REPORT.read_text())["records"]
            if r["status"] == "offline_configuration_prepared"
        ]
        self.assertTrue(candidates)
        candidate_config_hashes = {
            r["path"]: hashlib.sha256((ROOT / r["path"]).read_bytes()).hexdigest()
            for r in candidates
        }
        self.addCleanup(
            setattr, dungeon_instances, "_ROUTES", dungeon_instances._ROUTES
        )
        registry = [
            json.loads((ROOT / r["path"]).read_text())["route"] for r in candidates
        ]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_runtime_routes',%s::jsonb) ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (json.dumps(dict(schema_version=1, routes=registry)),),
            )
        dungeon_instances.load_runtime_routes(self.store)
        self.store.clock = lambda: 2_000_000_000.0
        audit = []
        groups = combat_group_store.PersistentGroups(self.store)
        for candidate in candidates:
            with self.subTest(route=candidate["route"]):
                config = json.loads((ROOT / candidate["path"]).read_text())
                # Assign a disposable version without replacing migration-seeded immutable configs.
                config = dungeon_runtime_config.prepare_configuration(
                    config["compiled_plan"],
                    config["topology"],
                    config["route"],
                    version=10001,
                    provenance=config["provenance"],
                )
                route = config["route"]
                geometry = map_geometry(route["start_map_id"])
                with self.store.connection() as db:
                    dungeon_runtime_config.install_configuration(db, config)
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
                            ">qiBi",
                            route["entry_object_id"],
                            route["destination_id"],
                            0,
                            2,
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
                        k: event["source_" + k]
                        for k in ("map_id", "instance_id", "x", "y", "z")
                    }
                    location["x"] += 1  # Companion moved before worker observed entry.

                    def bootstrap(e):
                        plan = dungeon_hydration.prepare_transition(
                            self.store,
                            member["account"],
                            member["generation"],
                            identity,
                            e,
                        )
                        self.assertEqual(
                            plan.character["instance_id"], e["destination_instance_id"]
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
                # Partial exit and nonleader reentry must preserve inside members.
                outside = members[1]
                before = self.store.character(
                    members[2]["account"], members[2]["character"]["id"]
                )
                dungeon_exit.leave_automatic(
                    self.store,
                    outside["account"],
                    outside["generation"],
                    outside["character"]["id"],
                    in_fight=lambda _: False,
                )
                deliver(outside)
                self.assertEqual(enter(outside)["instance_id"], instance)
                deliver(outside)
                after = self.store.character(
                    members[2]["account"], members[2]["character"]["id"]
                )
                self.assertEqual(
                    tuple(before[k] for k in ("map_id", "instance_id", "x", "y", "z")),
                    tuple(after[k] for k in ("map_id", "instance_id", "x", "y", "z")),
                )
                room_count = len(config["topology"]["rooms"])
                for order in range(1, room_count + 1):
                    with self.store.connection() as db:
                        spawned = dungeon_runtime.ensure_current_room(
                            db, groups, instance, geometry
                        )
                        self.assertEqual(spawned["room_order"], order)
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
                            "UPDATE combat_fights SET status='finished' WHERE id=%s",
                            (fight,),
                        )
                        actors = {
                            m["character"]["id"]: SimpleNamespace(
                                controlled=True, owner_id=m["account"], team=0
                            )
                            for m in members
                        }
                        finished = SimpleNamespace(
                            id=fight, phase="finished", winner=0, actors=actors
                        )
                        context = dict(
                            winner_team=0,
                            challenge_percent=0,
                            star_percent=0,
                            winners=[
                                dict(
                                    level=self.store.character(
                                        m["account"], m["character"]["id"], db
                                    )["level"],
                                    player=True,
                                    eligible=True,
                                    character_id=m["character"]["id"],
                                    wisdom=0,
                                )
                                for m in members
                            ],
                            losers=[
                                dict(level=npc["level"], monster_reference=npc["ref"])
                                for npc in spawned["members"]
                            ],
                        )

                        def award_party():
                            for member in members:
                                identity = member["character"]["id"]
                                decision = reward_policy.resolve(
                                    self.store,
                                    db,
                                    account_id=member["account"],
                                    generation=member["generation"],
                                    character_id=identity,
                                    fight_id=fight,
                                    context=context,
                                    kamas_roll_index=0,
                                )
                                self.assertEqual(
                                    [
                                        m["reference"]
                                        for m in decision.snapshot["monster_catalog"]
                                    ],
                                    [m["ref"] for m in spawned["members"]],
                                )
                                award = combat_rewards.award(
                                    self.store,
                                    member["account"],
                                    member["generation"],
                                    identity,
                                    finished,
                                    decision.policy,
                                    db=db,
                                )
                                self.assertTrue(award["awarded"])
                                self.assertGreaterEqual(award["xp"], 0)
                                self.assertGreaterEqual(award["kamas"], 0)
                                duplicate = combat_rewards.award(
                                    self.store,
                                    member["account"],
                                    member["generation"],
                                    identity,
                                    finished,
                                    decision.policy,
                                    db=db,
                                )
                                self.assertFalse(duplicate["awarded"])

                        if order == 1:
                            with self.assertRaisesRegex(
                                RuntimeError, "Atomic candidate rollback"
                            ):
                                with db.transaction():
                                    award_party()
                                    dungeon_progression.settle_encounter(db, finished)
                                    raise RuntimeError("Atomic candidate rollback")
                            self.assertEqual(
                                db.execute(
                                    "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s",
                                    (fight,),
                                ).fetchone()["n"],
                                0,
                            )
                            self.assertEqual(
                                db.execute(
                                    "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                                    (instance,),
                                ).fetchone()["current_room"],
                                1,
                            )
                        award_party()
                        result = dungeon_progression.settle_encounter(db, finished)
                        self.assertEqual(
                            db.execute(
                                "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s",
                                (fight,),
                            ).fetchone()["n"],
                            3,
                        )
                        self.assertTrue(result["victory"])
                        self.assertFalse(result["replay"])
                        self.assertTrue(
                            dungeon_progression.settle_encounter(
                                db,
                                SimpleNamespace(id=fight, phase="finished", winner=0),
                            )["replay"]
                        )
                        current = result["current_room"]
                        packets = dungeon_physical_doors.packets(
                            config["topology"],
                            map_id=route["start_map_id"],
                            instance_id=instance,
                            unlocked_room=current,
                        )
                        gate_packets = {
                            struct.unpack(">q", body[:8])[0]: body
                            for opcode, body in packets
                        }
                        for gate in config["topology"]["physical_doors"]:
                            body = gate_packets[gate["source_id"]]
                            expected = 0 if gate["destination_room"] <= current else 1
                            self.assertEqual(
                                struct.unpack(">h", body[17:19])[0], expected
                            )
                        next_spawn = dungeon_runtime.ensure_current_room(
                            db, groups, instance, geometry
                        )
                        if order < room_count:
                            self.assertEqual(next_spawn["room_order"], order + 1)
                        else:
                            self.assertIsNone(next_spawn)
                final_exit = next(
                    e
                    for e in config["topology"]["physical_exit_objects"]
                    if e["room_order"] == room_count
                )
                approach = final_exit["native_approach_cells"][0]
                for member in members:
                    with self.store.connection() as db:
                        db.execute(
                            "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
                            (*approach, member["character"]["id"]),
                        )
                    dungeon_exit.leave(
                        self.store,
                        member["account"],
                        member["generation"],
                        member["character"]["id"],
                        struct.pack(
                            ">qiBi",
                            final_exit["source_id"],
                            final_exit["destination_id"],
                            0,
                            2,
                        ),
                        source_allowed=lambda actor, source: source["id"]
                        == final_exit["source_id"]
                        and [actor[k] for k in ("x", "y", "z")]
                        in final_exit["native_approach_cells"],
                        in_fight=lambda _: False,
                    )
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
                        room_count,
                    )
                fresh = enter(members[0])
                self.assertNotEqual(fresh["instance_id"], instance)
                for member in members:
                    deliver(member)

                with self.store.connection() as db:
                    economy = db.execute(
                        "SELECT count(*) AS receipt_count,sum(r.xp) AS awarded_xp,sum(r.kamas) AS awarded_kamas FROM fight_rewards r JOIN dungeon_room_encounters e ON e.fight_id=r.fight_id WHERE e.instance_id=%s",
                        (instance,),
                    ).fetchone()
                self.assertEqual(economy["receipt_count"], 3 * room_count)
                audit.append(
                    dict(
                        route=route["key"],
                        name=candidate["name"],
                        status="isolated_postgres_lifecycle_and_economy_passed",
                        player_count=3,
                        room_count=room_count,
                        economy={k: int(v) for k, v in economy.items()},
                        atomic_reward_progression_rollback_verified=True,
                        receipt_replay_verified=True,
                        native_exit_and_party_reentry_verified=True,
                    )
                )
        self.assertEqual(len(audit), len(candidates))
        if os.environ.get("WAKFU_DUNGEON_LIFECYCLE_AUDIT"):
            path = Path(os.environ["WAKFU_DUNGEON_LIFECYCLE_AUDIT"])
            sources = [
                "server/tests/test_prepared_physical_flow_postgres.py",
                "server/wakfu_server/storage/reward_policy.py",
                "server/migrations/099_native_npc_reward_levels.sql",
            ]
            source_hashes = {
                p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources
            }
            source_hashes.update(candidate_config_hashes)
            report = dict(
                scope="Actual isolated PostgreSQL service lifecycle and native-roster reward policy; authoritative terminal fight fixtures, no boss AI or spells simulated",
                runtime_activated=False,
                source_sha256=source_hashes,
                records=audit,
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, indent=2) + "\n")
