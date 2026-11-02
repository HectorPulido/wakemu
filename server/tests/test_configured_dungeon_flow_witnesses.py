"""Replay retained traversal witnesses through real native public validators.

No battle, movement persistence, payment, transport consumption or client write
is performed. Victory frontiers and already-started paid scenes are explicit
inputs. Transport resolution and published usability are separate from the
SQL receipt guard exercised by the actual travel consumer.
"""
from contextlib import contextmanager
from pathlib import Path
import json
import os
import struct
import traceback
import unittest
from configured_dungeon_flow_fixture import (
    variants,
    native_approaches,
    declared_initial_open_scene,
)


class ConfiguredDungeonFlowWitnesses(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("WAKFU_FLOW_SNAPSHOT") or not os.environ.get(
            "WAKFU_FLOW_PATH_RECEIPTS"
        ):
            self.skipTest(
                "Exported canonical snapshot and retained path receipts required"
            )
        self.snapshot = json.loads(Path(os.environ["WAKFU_FLOW_SNAPSHOT"]).read_text())
        self.configurations = {
            (r["route"], key): config
            for r in self.snapshot["configurations"]
            for key, config in variants(r)
        }
        self.rows = []
        for filename in json.loads(os.environ["WAKFU_FLOW_PATH_RECEIPTS"]):
            self.rows.extend(json.loads(Path(filename).read_text())["configurations"])
        self.results = []

    def test_retained_frontiers_and_installed_paid_delta(self):
        for row in self.rows:
            config = self.configurations[(row["route"], row["variant"])]
            requested = os.environ.get("WAKFU_FLOW_ROUTES", "all")
            if requested != "all" and row["route"] not in requested.split(","):
                continue
            for evidence in row["checks"]:
                frontier = evidence["kind"] == "main_frontier_native_path"
                paid_delta = row["route"] in (
                    "native_dungeon_13",
                    "native_dungeon_134",
                    "native_dungeon_164",
                ) and evidence["kind"] in (
                    "initial_room_native_path",
                    "completed_native_exit_path",
                )
                open_completion = (
                    declared_initial_open_scene(config["topology"])
                    and evidence["kind"] == "completed_native_exit_path"
                )
                if not (frontier or paid_delta or open_completion):
                    continue
                identity = dict(
                    route=row["route"],
                    variant=row["variant"],
                    kind=evidence["kind"],
                    source=evidence.get("source"),
                    destination=evidence.get("destination"),
                )
                with self.subTest(**identity):
                    try:
                        self.assertTrue(evidence["passed"])
                        self.assertTrue(evidence["witness"])
                        result = self.replay(config, evidence)
                    except Exception as error:
                        self.results.append(
                            dict(
                                identity,
                                passed=False,
                                error=type(error).__name__,
                                detail=str(error),
                                traceback=traceback.format_exc(),
                            )
                        )
                        self.receipt()
                        raise
                    self.results.append(dict(identity, passed=True, **result))
                    self.receipt()
        self.assertTrue(self.results)

    def receipt(self):
        if os.environ.get("WAKFU_FLOW_WITNESS_RECEIPT"):
            Path(os.environ["WAKFU_FLOW_WITNESS_RECEIPT"]).write_text(
                json.dumps(
                    dict(
                        scope="Read-only actual public movement validator, source-authorized transport resolution and gate packets; no SQL transport consumption or native combat/UI claim",
                        cases=self.results,
                        passed=sum(r["passed"] for r in self.results),
                        failed=sum(not r["passed"] for r in self.results),
                    ),
                    indent=2,
                )
                + "\n"
            )

    @staticmethod
    def request(points):
        return dict(
            start_position=dict(zip(("x", "y", "z"), points[0])),
            end_position=dict(zip(("x", "y", "z"), points[-1])),
            steps=[
                dict(zip(("dx", "dy", "dz"), (b[i] - a[i] for i in range(3))))
                for a, b in zip(points, points[1:])
            ],
        )

    @staticmethod
    def states(topology, frontier, completed):
        from wakfu_server.dungeon_native_flow import packets

        return {
            struct.unpack_from(">q", body)[0]: dict(
                state=struct.unpack_from(">h", body, 17)[0],
                visible=bool(body[19]),
                usable=bool(body[20]),
                bk=bool(body[22]),
                bh=bool(body[23]),
            )
            for opcode, body in packets(
                topology,
                map_id=topology["asset_map_id"],
                instance_id=99,
                unlocked_room=frontier,
                completed=completed,
            )
            if opcode == 12344 and len(body) > 23
        }

    def gate_agreement(self, topology, frontier, completed, states):
        from wakfu_server import dungeon_physical_doors, dungeon_branches
        from wakfu_server.dungeon_native_door_collision import native_blocking_cells

        blocked = dungeon_physical_doors.blocked_cells(
            topology,
            frontier,
            completed=completed,
            blocked_source_ids=dungeon_branches.unselected_gate_ids(topology),
        )
        checked = 0
        for gate in topology.get("physical_doors", ()):
            state = states[gate["source_id"]]
            closed = state["state"] == 1
            self.assertEqual((state["bk"], state["bh"]), (closed, closed))
            if closed:
                self.assertTrue(
                    native_blocking_cells(topology["asset_map_id"], gate["position"])
                    <= blocked
                )
            checked += 1
        return checked

    def replay(self, config, evidence):
        from wakfu_server import (
            dungeon_native_flow,
            dungeon_optional_rooms,
            generic_transports,
        )

        topology = dict(config["topology"])
        main = dungeon_optional_rooms.main_room_orders(topology)
        is_frontier = evidence["kind"] == "main_frontier_native_path"
        source_open = declared_initial_open_scene(topology)
        if source_open:
            from wakfu_server.dungeon_main_completion import require_rule

            self.assertIsNotNone(require_rule(topology))
        completed = evidence["kind"] == "completed_native_exit_path"
        after = (
            evidence["destination"]
            if is_frontier
            else (main[-1] if completed else main[0])
        )
        before = evidence["source"] if is_frontier else after
        if topology.get("entry_path_policy"):
            topology["_entry_main_completed"] = completed
        if topology.get("native_scene_start"):
            topology["_native_scene_started"] = True
        after_states = self.states(topology, after, completed)
        before_states = self.states(topology, before, False)
        gate_checks = self.gate_agreement(
            topology, after, completed, after_states
        ) + self.gate_agreement(topology, before, False, before_states)
        edges = {
            (tuple(a), tuple(b)) for a, b in topology["exploration_geometry"]["edges"]
        }
        witness = list(map(tuple, evidence["witness"]))
        walk = [witness[0]]
        parts = []
        for a, b in zip(witness, witness[1:]):
            if (a, b) in edges:
                walk.append(b)
            else:
                parts.append(("walk", walk))
                parts.append(("transport", (a, b)))
                walk = [b]
        parts.append(("walk", walk))
        blocked_before = []
        walk_segments = 0
        transports = []
        for kind, value in parts:
            if kind == "walk":
                request = self.request(value)
                end = dungeon_native_flow.validate_movement(
                    topology, request, unlocked_room=after, completed=completed
                )
                self.assertEqual(end, value[-1])
                walk_segments += 1
                if is_frontier or source_open and completed:
                    try:
                        dungeon_native_flow.validate_movement(
                            topology, request, unlocked_room=before, completed=False
                        )
                    except ValueError as error:
                        blocked_before.append(dict(kind="walk", reason=str(error)))
            else:
                a, b = value
                matches = []
                for binding in topology.get("doors", ()):
                    source = generic_transports.source(
                        topology["asset_map_id"], binding["source_id"]
                    )
                    if tuple(
                        binding["destination_position"]
                    ) == b and a in native_approaches(source):
                        matches.append((binding, source))
                self.assertTrue(
                    matches, "Witness jump lacks an exact native transport binding"
                )
                admitted = [
                    (binding, source)
                    for binding, source in matches
                    if after_states[source["id"]]["visible"]
                    and after_states[source["id"]]["usable"]
                ]
                self.assertTrue(
                    admitted,
                    "Native transport is not published usable at the committed frontier",
                )
                binding, source = admitted[0]
                destination = self.resolve_transport(
                    config, topology, source, binding, a, after
                )
                self.assertEqual(tuple(destination[k] for k in ("x", "y", "z")), b)
                prior = before_states[source["id"]]
                if not (prior["visible"] and prior["usable"]):
                    blocked_before.append(
                        dict(kind="transport", source_id=source["id"])
                    )
                transports.append(
                    dict(
                        source_id=source["id"],
                        destination_id=binding["destination_id"],
                        resolved_by_public_api=True,
                        before_usable=prior["visible"] and prior["usable"],
                        after_usable=True,
                        consumed=False,
                    )
                )
        shared = topology["policy"] == "native_shared_arena_sequential_policy"
        if is_frontier and not (shared or source_open) or source_open and completed:
            self.assertTrue(
                blocked_before,
                "Witness was already traversable before its declared victory frontier",
            )
        if is_frontier and source_open:
            self.assertFalse(
                blocked_before,
                "Source-declared initially open walking unexpectedly became locked",
            )
        return dict(
            walk_segments=walk_segments,
            walk_steps=sum(len(value) - 1 for kind, value in parts if kind == "walk"),
            gate_state_collision_checks=gate_checks,
            before_blockers=blocked_before,
            transports=transports,
            shared_arena_progression_without_walking_lock=shared,
            source_declared_initial_open_walking=source_open,
            paid_scene_started_premise=bool(topology.get("native_scene_start")),
        )

    def resolve_transport(self, config, topology, source, binding, point, frontier):
        from wakfu_server import (
            dungeon_doors,
            dungeon_runtime,
            teleporter_approach,
            dungeon_criteria,
            native_catalog,
        )
        from wakfu_server.movement import Movement

        class ReadOnlySource:
            @contextmanager
            def connection(self):
                with native_catalog._database().connection() as db:
                    db.execute("SET TRANSACTION READ ONLY")
                    yield db

        def criterion_allowed(criterion):
            # The current literal doors only have this global source predicate.
            # Do not fabricate player achievement/item authority for new criteria.
            self.assertEqual(criterion.strip(), "not IsNeoServer()")
            return dungeon_criteria.evaluate(ReadOnlySource(), criterion)

        actor = dict(
            id=1,
            map_id=topology["asset_map_id"],
            instance_id=99,
            **dict(zip(("x", "y", "z"), point))
        )
        view = dict(config, topology=topology)
        start, end, destination = dungeon_doors.resolve(
            actor,
            struct.pack(">qiBi", source["id"], binding["destination_id"], 0, 2),
            source_allowed=teleporter_approach.callback(
                Movement(actor), map_id=actor["map_id"], instance_id=99
            ),
            room_for_position=lambda mid, x, y, z: dungeon_runtime.room_for_position(
                view, mid, x, y, z, current_room=frontier
            ),
            criterion_allowed=criterion_allowed,
            topology=topology,
        )
        self.assertEqual(
            (start, end), (binding["source_room"], binding["destination_room"])
        )
        return destination
