"""Isolated PostgreSQL traversal gate for the seven frozen hybrid routes."""
import hashlib
import json
import os
import struct
import unittest
from pathlib import Path
from types import SimpleNamespace

from postgres_case import PostgresCase
from test_dungeon_instances import DungeonInstanceTests as _Fixture
from wakfu_server import (
    combat_group_store,
    dungeon_doors,
    dungeon_exit,
    dungeon_instances,
    dungeon_native_flow,
    dungeon_progression,
    dungeon_runtime,
    dungeon_runtime_config,
    dungeon_transport,
    generic_transports,
)
from wakfu_server.combat_terrain import map_geometry

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(
    os.environ.get(
        "WAKFU_HYBRID_CANDIDATE_REPORT",
        "docs/reports/dungeons/HYBRID-NATIVE-FULL-ROOM-CANDIDATES-V7-20261010.json",
    )
)
if not REPORT.is_absolute():
    REPORT = ROOT / REPORT


class HybridNativeCandidatePostgresTests(PostgresCase):
    player = _Fixture.player
    party = _Fixture.party

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0

    @staticmethod
    def gate_walk(topology, gate):
        edges = {
            (tuple(a), tuple(b)) for a, b in topology["exploration_geometry"]["edges"]
        }
        starts = sorted(
            a
            for a, b in edges
            if b == tuple(gate["position"])
            and a
            in {tuple(c) for c in topology["rooms"][gate["source_room"] - 1]["cells"]}
        )
        ends = sorted(
            b
            for a, b in edges
            if a == tuple(gate["position"])
            and b
            in {
                tuple(c)
                for c in topology["rooms"][gate["destination_room"] - 1]["cells"]
            }
        )
        if not starts or not ends:
            raise AssertionError(
                f"Physical gate {gate['source_id']} lacks literal walk edges"
            )
        path = [starts[0], tuple(gate["position"]), ends[0]]
        return dict(
            start_position=dict(zip(("x", "y", "z"), path[0])),
            end_position=dict(zip(("x", "y", "z"), path[-1])),
            steps=[
                dict(dx=b[0] - a[0], dy=b[1] - a[1], dz=b[2] - a[2])
                for a, b in zip(path, path[1:])
            ],
        )

    @staticmethod
    def walk_to(topology, start, targets, frontier):
        edges = {
            (tuple(a), tuple(b)) for a, b in topology["exploration_geometry"]["edges"]
        }
        cells = {
            tuple(c): room["order"] for room in topology["rooms"] for c in room["cells"]
        }
        cells.update(
            {
                tuple(g["position"]): g["destination_room"]
                for g in topology.get("physical_doors", ())
            }
        )
        targets = {tuple(c) for c in targets}
        queue = [tuple(start)]
        previous = {tuple(start): None}
        found = None
        for cell in queue:
            if cell in targets:
                found = cell
                break
            for a, b in edges:
                if (
                    a == cell
                    and b not in previous
                    and cells.get(b, frontier + 1) <= frontier
                ):
                    previous[b] = cell
                    queue.append(b)
        if found is None:
            raise AssertionError(
                f"No literal, unlocked native path from {start} to {targets}"
            )
        path = []
        cell = found
        while cell is not None:
            path.append(cell)
            cell = previous[cell]
        path.reverse()
        return dict(
            start_position=dict(zip(("x", "y", "z"), path[0])),
            end_position=dict(zip(("x", "y", "z"), path[-1])),
            steps=[
                dict(dx=b[0] - a[0], dy=b[1] - a[1], dz=b[2] - a[2])
                for a, b in zip(path, path[1:])
            ],
        )

    def test_prepared_literal_hybrid_routes_complete_with_receipts_and_bound_sources(
        self,
    ):
        report_bytes = REPORT.read_bytes()
        report = json.loads(report_bytes)
        candidates = [
            row
            for row in report["records"]
            if row.get("status") == "offline_configuration_prepared"
        ]
        self.assertTrue(candidates, "report contains no prepared candidates")
        self.assertEqual(
            len(candidates),
            sum(
                row.get("status") == "offline_configuration_prepared"
                for row in report["records"]
            ),
        )
        originals = dungeon_instances._ROUTES
        self.addCleanup(setattr, dungeon_instances, "_ROUTES", originals)
        routes = [
            json.loads((ROOT / row["path"]).read_text())["route"] for row in candidates
        ]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_runtime_routes',%s::jsonb) "
                "ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
                (json.dumps(dict(schema_version=1, routes=routes)),),
            )
        dungeon_instances.load_runtime_routes(self.store)
        groups = combat_group_store.PersistentGroups(self.store)
        audits = []
        config_hashes = {}

        for candidate in candidates:
            config_path = ROOT / candidate["path"]
            config_bytes = config_path.read_bytes()
            config_hashes[candidate["path"]] = hashlib.sha256(config_bytes).hexdigest()
            candidate_config = json.loads(config_bytes)
            if "configuration_canonical_sha256" in candidate:
                self.assertEqual(
                    dungeon_runtime_config.canonical_hash(candidate_config),
                    candidate["configuration_canonical_sha256"],
                )
                self.assertEqual(
                    hashlib.sha256(config_bytes).hexdigest(),
                    candidate["configuration_file_sha256"],
                )
                if "evidence_integrity_verified" in candidate:
                    self.assertTrue(candidate["evidence_integrity_verified"])
            topology = candidate_config["topology"]
            route = candidate_config["route"]
            rooms = topology["rooms"]
            count = len(rooms)
            self.assertEqual(count, candidate["rooms"])
            self.assertEqual(topology["policy"], dungeon_native_flow.MIXED_POLICY)
            self.assertTrue(topology["exploration_geometry"]["edges"])
            self.assertTrue(topology["doors"] or topology["physical_doors"])
            self.assertIn(len(topology["physical_exit_objects"]), (1, 2))

            # Verify catalog-bound exclusions, including canonical record hashes,
            # and that they neither overlap nor replace a mandatory route object.
            disabled = dungeon_native_flow.disabled_source_ids(
                topology, generic_transports._CATALOG
            )
            disabled_records = topology.get("disabled_native_sources", [])
            self.assertEqual(disabled, {r["source_id"] for r in disabled_records})
            mandatory = {
                binding["source_id"]
                for field in ("doors", "physical_doors", "physical_exit_objects")
                for binding in topology.get(field, ())
            }
            self.assertTrue(disabled.isdisjoint(mandatory))
            for record in disabled_records:
                source = generic_transports.source(
                    route["start_map_id"], record["source_id"]
                )
                self.assertIsNotNone(source)
                self.assertEqual(
                    dungeon_runtime_config.canonical_hash(source),
                    record["source_sha256"],
                )

            config = dungeon_runtime_config.prepare_configuration(
                candidate_config["compiled_plan"],
                topology,
                route,
                version=10020,
                provenance=candidate_config["provenance"],
            )
            with self.store.connection() as db:
                dungeon_runtime_config.install_configuration(db, config)
            members, party_id = self.party(6)
            for member in members:
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE characters SET map_id=%s,instance_id=0 WHERE id=%s",
                        (route["entry_map_id"], member["character"]["id"]),
                    )
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
            physical_room = 1

            def place(point):
                for member in members:
                    with self.store.connection() as db:
                        db.execute(
                            "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                            (
                                route["start_map_id"],
                                instance,
                                *point,
                                member["character"]["id"],
                            ),
                        )

            def room_at(map_id, x, y, z):
                point = (x, y, z)
                for room in rooms:
                    if point in {tuple(c) for c in room["cells"]}:
                        return room["order"]
                for binding in topology["doors"]:
                    if point == tuple(binding["destination_position"]):
                        return binding["destination_room"]
                return None

            def interact(binding):
                source_id = binding["source_id"]
                source = generic_transports.source(route["start_map_id"], source_id)
                self.assertIsNotNone(source, f"native source {source_id} missing")
                targets = binding["native_approach_cells"]
                with self.store.connection() as db:
                    actor = db.execute(
                        "SELECT x,y,z FROM characters WHERE id=%s",
                        (members[0]["character"]["id"],),
                    ).fetchone()
                path = self.walk_to(
                    topology,
                    tuple(actor[k] for k in ("x", "y", "z")),
                    targets,
                    frontier=current_frontier(instance),
                )
                dungeon_native_flow.validate_movement(
                    topology, path, unlocked_room=current_frontier(instance)
                )
                place(tuple(path["end_position"][k] for k in ("x", "y", "z")))
                response = dungeon_doors.advance(
                    self.store,
                    members[0]["account"],
                    members[0]["generation"],
                    members[0]["character"]["id"],
                    struct.pack(">qiBi", source_id, binding["destination_id"], 0, 2),
                    source_allowed=lambda actor, candidate: (
                        candidate["id"] == source_id
                        and [actor[k] for k in ("x", "y", "z")] in targets
                    ),
                    room_for_position=room_at,
                    in_fight=lambda _: False,
                    topology=topology,
                )
                self.assertEqual(len(response["members"]), 6)
                for member in members:
                    actor = self.store.character(
                        member["account"], member["character"]["id"]
                    )
                    self.assertEqual(
                        tuple(actor[k] for k in ("x", "y", "z")),
                        tuple(binding["destination_position"]),
                    )
                return response

            def current_frontier(instance_id):
                with self.store.connection() as db:
                    return db.execute(
                        "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                        (instance_id,),
                    ).fetchone()["current_room"]

            def reviewed_transport_route(start, target, frontier):
                """Find the shortest native door sequence through a reviewed hub."""
                queue = [start]
                previous = {start: None}
                previous_door = {}
                for room_order in queue:
                    if room_order == target:
                        break
                    for binding in topology["doors"]:
                        if binding["source_room"] != room_order:
                            continue
                        gate = dungeon_native_flow.validate_transport_binding(
                            topology, binding
                        )
                        if (
                            max(binding["source_room"], binding["destination_room"])
                            > frontier
                        ):
                            continue
                        if gate is not None and gate >= frontier:
                            # Forward destination room frontier is only authorized
                            # after the corresponding committed victory advances it.
                            continue
                        destination_room = binding["destination_room"]
                        if destination_room not in previous:
                            previous[destination_room] = room_order
                            previous_door[destination_room] = binding
                            queue.append(destination_room)
                if target not in previous:
                    return None
                path = []
                cursor = target
                while previous[cursor] is not None:
                    path.append(previous_door[cursor])
                    cursor = previous[cursor]
                path.reverse()
                return path

            def walk_to_native_approach(targets, room_order, frontier):
                """Walk or traverse exact same-stage ports to a native approach."""
                with self.store.connection() as db:
                    actor = db.execute(
                        "SELECT x,y,z FROM characters WHERE id=%s",
                        (members[0]["character"]["id"],),
                    ).fetchone()
                start = tuple(actor[k] for k in ("x", "y", "z"))
                queue, previous = [start], {start: None}
                found, final_walk = None, None
                for position in queue:
                    try:
                        final_walk = self.walk_to(topology, position, targets, frontier)
                        found = position
                        break
                    except AssertionError:
                        pass
                    for binding in topology["doors"]:
                        if (
                            binding["source_room"] != room_order
                            or binding["destination_room"] != room_order
                        ):
                            continue
                        dungeon_native_flow.validate_transport_binding(
                            topology, binding
                        )
                        try:
                            self.walk_to(
                                topology,
                                position,
                                binding["native_approach_cells"],
                                frontier,
                            )
                        except AssertionError:
                            continue
                        destination = tuple(binding["destination_position"])
                        if destination not in previous:
                            previous[destination] = (position, binding)
                            queue.append(destination)
                if found is None:
                    raise AssertionError(
                        f"No native walk/same-stage transport reaches {targets} in room {room_order}"
                    )
                transits, cursor = [], found
                while previous[cursor] is not None:
                    cursor, binding = previous[cursor]
                    transits.append(binding)
                transits.reverse()
                return transits, final_walk

            receipts = 0
            stage_transitions = []
            for order in range(1, count + 1):
                # All unbound optional sources stay hidden and are rejected by
                # request resolution, while mandatory source IDs remain present.
                if disabled_records:
                    packets = dungeon_native_flow.packets(
                        topology,
                        map_id=route["start_map_id"],
                        instance_id=instance,
                        unlocked_room=current_frontier(instance),
                    )
                    bodies = {
                        struct.unpack_from(">q", body)[0]: body for _, body in packets
                    }
                    for record in disabled_records:
                        self.assertIn(record["source_id"], bodies)
                        self.assertEqual(
                            bodies[record["source_id"]][19:21], bytes((0, 0))
                        )
                        native = generic_transports.source(
                            route["start_map_id"], record["source_id"]
                        )
                        with self.assertRaisesRegex(ValueError, "explicitly excluded"):
                            dungeon_doors.resolve(
                                dict(
                                    map_id=route["start_map_id"], instance_id=instance
                                ),
                                struct.pack(
                                    ">qiBi",
                                    record["source_id"],
                                    native["destinations"][0]["destination_id"],
                                    0,
                                    2,
                                ),
                                source_allowed=lambda actor, item: True,
                                room_for_position=room_at,
                                criterion_allowed=lambda criterion: True,
                                topology=topology,
                            )

                sequential_door = next(
                    (
                        d
                        for d in topology["doors"]
                        if d["source_room"] == order
                        and d["destination_room"] == order + 1
                    ),
                    None,
                )
                sequential_gate = next(
                    (
                        g
                        for g in topology["physical_doors"]
                        if g["source_room"] == order
                        and g["destination_room"] == order + 1
                    ),
                    None,
                )
                sequential_trigger = next(
                    (
                        g
                        for g in topology.get("position_trigger_gates", ())
                        if g["source_room"] == order
                        and g["destination_room"] == order + 1
                    ),
                    None,
                )
                gate_request = (
                    self.gate_walk(topology, sequential_gate)
                    if sequential_gate
                    else None
                )
                if gate_request:
                    with self.assertRaisesRegex(ValueError, "locked room"):
                        dungeon_native_flow.validate_movement(
                            topology, gate_request, unlocked_room=order
                        )
                if sequential_door:
                    source = generic_transports.source(
                        route["start_map_id"], sequential_door["source_id"]
                    )
                    self.assertIsNotNone(source)
                    door_approaches = sequential_door["native_approach_cells"]
                    same_stage_transits, approach_walk = walk_to_native_approach(
                        door_approaches, order, order
                    )
                    for same_stage_binding in same_stage_transits:
                        interact(same_stage_binding)
                        stage_transitions.append(same_stage_binding["source_id"])
                    dungeon_native_flow.validate_movement(
                        topology, approach_walk, unlocked_room=order
                    )
                    place(
                        tuple(approach_walk["end_position"][k] for k in ("x", "y", "z"))
                    )
                    with self.assertRaisesRegex(ValueError, "committed victory"):
                        dungeon_doors.advance(
                            self.store,
                            members[0]["account"],
                            members[0]["generation"],
                            members[0]["character"]["id"],
                            struct.pack(
                                ">qiBi",
                                sequential_door["source_id"],
                                sequential_door["destination_id"],
                                0,
                                2,
                            ),
                            source_allowed=lambda actor, item: (
                                item["id"] == sequential_door["source_id"]
                                and [actor[k] for k in ("x", "y", "z")]
                                in door_approaches
                            ),
                            room_for_position=room_at,
                            in_fight=lambda _: False,
                            topology=topology,
                        )

                # Native trigger boundaries are movement-only: they have no
                # Door packet to dispatch. Prove the next arena is still
                # unreachable before this room's committed victory receipt.
                if sequential_trigger:
                    with self.store.connection() as db:
                        actor = db.execute(
                            "SELECT x,y,z FROM characters WHERE id=%s",
                            (members[0]["character"]["id"],),
                        ).fetchone()
                    with self.assertRaisesRegex(
                        AssertionError, "No literal, unlocked native path"
                    ):
                        self.walk_to(
                            topology,
                            tuple(actor[k] for k in ("x", "y", "z")),
                            topology["rooms"][order]["cells"],
                            frontier=order,
                        )

                with self.store.connection() as db:
                    spawned = dungeon_runtime.ensure_current_room(
                        db, groups, instance, geometry
                    )
                    self.assertIsNotNone(spawned)
                    self.assertEqual(spawned["room_order"], order)
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
                        "UPDATE combat_fights SET status='finished' WHERE id=%s",
                        (fight,),
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
                    receipts += 1
                frontier = current_frontier(instance)
                self.assertEqual(frontier, min(order + 1, count))
                if sequential_trigger:
                    with self.store.connection() as db:
                        actor = db.execute(
                            "SELECT x,y,z FROM characters WHERE id=%s",
                            (members[0]["character"]["id"],),
                        ).fetchone()
                    trigger_cells = set(
                        map(
                            tuple,
                            sequential_trigger.get(
                                "native_activation_cells",
                                (sequential_trigger["position"],),
                            ),
                        )
                    )
                    activation_targets = trigger_cells.intersection(
                        set(map(tuple, topology["rooms"][order]["cells"]))
                    ) or {tuple(sequential_trigger["position"])}
                    path = self.walk_to(
                        topology,
                        tuple(actor[k] for k in ("x", "y", "z")),
                        activation_targets,
                        frontier=frontier,
                    )
                    traversed = [
                        tuple(path["start_position"][k] for k in ("x", "y", "z"))
                    ]
                    current = traversed[0]
                    for step in path["steps"]:
                        current = tuple(
                            current[i] + step["d" + axis]
                            for i, axis in enumerate(("x", "y", "z"))
                        )
                        traversed.append(current)
                    self.assertTrue(
                        trigger_cells.intersection(traversed),
                        "Literal movement path did not cross the native trigger activation set",
                    )
                    dungeon_native_flow.validate_movement(
                        topology, path, unlocked_room=frontier
                    )
                    place(tuple(path["end_position"][k] for k in ("x", "y", "z")))
                    stage_transitions.append(
                        {
                            "kind": "native_trigger_frontier",
                            "source_id": sequential_trigger["source_id"],
                            "from_room": order,
                            "to_room": order + 1,
                            "activation_cell_crossed": True,
                        }
                    )
                    physical_room = order + 1
                elif gate_request:
                    dungeon_native_flow.validate_movement(
                        topology, gate_request, unlocked_room=frontier
                    )
                    place(
                        tuple(gate_request["end_position"][k] for k in ("x", "y", "z"))
                    )
                    stage_transitions.append(sequential_gate["source_id"])
                    physical_room = order + 1
                elif sequential_door:
                    moved = interact(sequential_door)
                    self.assertEqual(
                        tuple(moved[k] for k in ("x", "y", "z")),
                        tuple(sequential_door["destination_position"]),
                    )
                    stage_transitions.append(sequential_door["source_id"])
                    physical_room = sequential_door["destination_room"]
                elif order == count:
                    self.assertEqual(order, count)
                else:
                    route_bindings = reviewed_transport_route(
                        physical_room, order + 1, frontier
                    )
                    if route_bindings:
                        for binding in route_bindings:
                            moved = interact(binding)
                            self.assertEqual(
                                tuple(moved[k] for k in ("x", "y", "z")),
                                tuple(binding["destination_position"]),
                            )
                            stage_transitions.append(binding["source_id"])
                            physical_room = binding["destination_room"]
                    else:
                        self.assertTrue(
                            route_bindings,
                            f"candidate has no literal native route from room {physical_room} to {order + 1}",
                        )
            final_exit = next(
                (
                    e
                    for e in topology["physical_exit_objects"]
                    if e["room_order"] == count
                ),
                None,
            )
            if final_exit is None:
                cycle_exits = [
                    e for e in topology["physical_exit_objects"] if e["room_order"] == 1
                ]
                self.assertEqual(len(cycle_exits), 1)
                final_exit = cycle_exits[0]
                with self.store.connection() as db:
                    actor = db.execute(
                        "SELECT x,y,z FROM characters WHERE id=%s",
                        (members[0]["character"]["id"],),
                    ).fetchone()
                return_walk = self.walk_to(
                    topology,
                    tuple(actor[k] for k in ("x", "y", "z")),
                    final_exit["native_approach_cells"],
                    frontier=count,
                )
                path_cells = [
                    tuple(return_walk["start_position"][k] for k in ("x", "y", "z"))
                ]
                cursor = path_cells[0]
                for step in return_walk["steps"]:
                    cursor = tuple(
                        cursor[i] + step["d" + axis]
                        for i, axis in enumerate(("x", "y", "z"))
                    )
                    path_cells.append(cursor)
                return_gate = next(
                    (
                        gate
                        for gate in topology["physical_doors"]
                        if gate["source_room"] != gate["destination_room"]
                        and tuple(gate["position"]) in path_cells
                    ),
                    None,
                )
                self.assertIsNotNone(
                    return_gate,
                    "Cycle exit return path did not traverse a reviewed native gate",
                )
                dungeon_native_flow.validate_movement(
                    topology, return_walk, unlocked_room=count
                )
                place(tuple(return_walk["end_position"][k] for k in ("x", "y", "z")))
                stage_transitions.append(
                    {
                        "kind": "completed_native_return_walk",
                        "source_id": return_gate["source_id"],
                        "from_room": count,
                        "to_room": 1,
                    }
                )
            native_exit = generic_transports.source(
                route["start_map_id"], final_exit["source_id"]
            )
            self.assertIsNotNone(native_exit)
            packets = dungeon_native_flow.packets(
                topology,
                map_id=route["start_map_id"],
                instance_id=instance,
                unlocked_room=count,
                completed=False,
            )
            exit_body = next(
                body
                for _, body in packets
                if struct.unpack_from(">q", body)[0] == final_exit["source_id"]
            )
            self.assertEqual(
                exit_body[19:21],
                bytes((1, 1)) if final_exit["room_order"] == 1 else bytes((0, 0)),
            )
            with self.store.connection() as db:
                spawned = dungeon_runtime.ensure_current_room(
                    db, groups, instance, geometry
                )
                self.assertIsNone(spawned)
            # Last stage was completed above; confirm the native exit state flips.
            # Run completion is recorded by the final victory receipt.
            packets = dungeon_native_flow.packets(
                topology,
                map_id=route["start_map_id"],
                instance_id=instance,
                unlocked_room=count,
                completed=True,
            )
            exit_body = next(
                body
                for _, body in packets
                if struct.unpack_from(">q", body)[0] == final_exit["source_id"]
            )
            self.assertEqual(exit_body[19:21], bytes((1, 1)))
            place(final_exit["native_approach_cells"][0])
            for member in members:
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
                    source_allowed=lambda actor, source: (
                        source["id"] == final_exit["source_id"]
                        and [actor[k] for k in ("x", "y", "z")]
                        in final_exit["native_approach_cells"]
                    ),
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
                        "SELECT count(*) AS n FROM dungeon_room_spawn_receipts WHERE instance_id=%s",
                        (instance,),
                    ).fetchone()["n"],
                    count,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM dungeon_room_encounters WHERE instance_id=%s AND status='victory'",
                        (instance,),
                    ).fetchone()["n"],
                    count,
                )
            audits.append(
                dict(
                    route=route["key"],
                    name=candidate.get("name", route["key"]),
                    rooms=count,
                    players=6,
                    victory_receipts=receipts,
                    stage_transitions=stage_transitions,
                    disabled_sources=sorted(disabled),
                    status="isolated_postgres_hybrid_lifecycle_passed",
                )
            )

        self.assertEqual(len(audits), len(candidates))
        for row in candidates:
            candidate_path = ROOT / row["path"]
            self.assertEqual(
                hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
                config_hashes[row["path"]],
            )
        if os.environ.get("WAKFU_DUNGEON_LIFECYCLE_AUDIT"):
            evidence = Path(os.environ["WAKFU_DUNGEON_LIFECYCLE_AUDIT"])
            paths = (
                "server/tests/test_hybrid_native_candidates_postgres.py",
                "server/local_game_server.py",
                "server/wakfu_server/maps/dungeon_doors.py",
                "server/wakfu_server/maps/dungeon_branches.py",
                "server/wakfu_server/maps/dungeon_native_flow.py",
                "server/wakfu_server/maps/dungeon_object_states.py",
                "server/wakfu_server/maps/dungeon_progression.py",
                "server/wakfu_server/maps/dungeon_physical_doors.py",
                "server/wakfu_server/maps/dungeon_exit.py",
                "server/wakfu_server/maps/dungeon_runtime.py",
                "server/wakfu_server/maps/dungeon_runtime_config.py",
                "server/wakfu_server/maps/dungeon_instances.py",
                "server/wakfu_server/maps/dungeon_transport.py",
                "server/wakfu_server/maps/dungeon_room_spawns.py",
                "server/migrations/112_dungeon_branch_selection.sql",
            )
            hashes = {
                p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths
            }
            report_relpath = str(REPORT.relative_to(ROOT))
            hashes[f"candidate_report:{report_relpath}"] = hashlib.sha256(
                report_bytes
            ).hexdigest()
            source_report = os.environ.get("WAKFU_DUNGEON_SOURCE_REPORT")
            if source_report:
                source_report_path = Path(source_report)
                if not source_report_path.is_absolute():
                    source_report_path = ROOT / source_report_path
                hashes[
                    f"candidate_source_report:{source_report_path.relative_to(ROOT)}"
                ] = hashlib.sha256(source_report_path.read_bytes()).hexdigest()
            hashes.update(config_hashes)
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(
                json.dumps(
                    {
                        "scope": f"Isolated PostgreSQL lifecycle for {len(audits)} source-only hybrid native routes from {REPORT.relative_to(ROOT)}; literal transport and walking gates, six-player parties, authoritative encounter receipts; no boss AI or spells simulated",
                        "runtime_activated": False,
                        "source_sha256": hashes,
                        "records": audits,
                    },
                    indent=2,
                )
                + "\n"
            )


del _Fixture
