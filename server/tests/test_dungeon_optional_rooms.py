"""Reviewed optional dungeon rooms stay physically present but unenterable."""
from copy import deepcopy
import unittest

from wakfu_server.dungeon_optional_rooms import (
    canonical_completion_preview,
    main_room_orders,
    partition_rooms,
    require_main_room,
    validate_movement,
)
from wakfu_server.dungeon_runtime_config import canonical_hash, plan_from_configuration


def fixture(source_orders=(1, 2, 3, 4)):
    plan_rooms = [
        {
            "order": order,
            "diagnostics": [],
            "monsters": [
                {
                    "name": f"native-{order}",
                    "ref_id": 100 + order,
                    "count": 1,
                    "role": "ordinary",
                    "native_min_level": 10,
                    "native_max_level": 10,
                    "guide_min_level": None,
                    "guide_max_level": None,
                }
            ],
            "source_identity": f"roster-{order}",
        }
        for order in source_orders
    ]
    terrain_rooms = [
        {
            "order": order,
            "anchor": [order * 10, 0, 0],
            "cells": [[order * 10, 0, 0], [order * 10 + 1, 0, 0]],
            "source_identity": f"terrain-{order}",
        }
        for order in source_orders
    ]
    topology = {
        "policy": "local_accessible_anchor_policy",
        "asset_map_id": 910,
        "rooms": terrain_rooms,
        "doors": [],
        "auto_edges": [
            {"source_room": source_orders[i], "destination_room": source_orders[i + 1]}
            for i in range(len(source_orders) - 1)
        ],
    }
    plan = {
        "slug": "fixture",
        "source_url": "https://example.invalid/fixture",
        "source_sha256": "fixture-source",
        "document_sha256": "fixture-document",
        "definition_id": 1,
        "template_id": 2,
        "asset_map_id": 910,
        "diagnostics": [],
        "rooms": plan_rooms,
    }
    return plan, topology


class DungeonOptionalRoomsTests(unittest.TestCase):
    def test_partition_preserves_nonprefix_rosters_and_closes_optional_room(self):
        plan, topology = fixture((1, 2, 3, 5, 4))
        original_plan, original_topology = deepcopy(plan), deepcopy(topology)
        plan, topology = partition_rooms(
            plan,
            topology,
            main_source_orders=[1, 2, 3, 5],
            access_evidence={
                4: {"source": "native-access-review", "status": "unresolved"}
            },
        )
        self.assertEqual([r["source_order"] for r in plan["rooms"]], [1, 2, 3, 5, 4])
        self.assertEqual(
            [r["source_identity"] for r in plan["rooms"]],
            ["roster-1", "roster-2", "roster-3", "roster-5", "roster-4"],
        )
        self.assertEqual(
            [r["source_identity"] for r in topology["rooms"]],
            ["terrain-1", "terrain-2", "terrain-3", "terrain-5", "terrain-4"],
        )
        self.assertEqual(main_room_orders(topology), (1, 2, 3, 4))
        self.assertEqual(
            topology["optional_room_policy"]["optional_rooms"][0]["order"], 5
        )
        self.assertEqual(
            topology["auto_edges"],
            [
                {"source_room": 1, "destination_room": 2},
                {"source_room": 2, "destination_room": 3},
                {"source_room": 3, "destination_room": 4},
            ],
        )
        self.assertEqual(
            (
                original_plan["rooms"][0]["order"],
                original_topology["rooms"][0]["order"],
            ),
            (1, 1),
        )
        with self.assertRaisesRegex(ValueError, "Optional room"):
            require_main_room(topology, 5)
        with self.assertRaisesRegex(ValueError, "Optional native access"):
            validate_movement(
                topology,
                {
                    "start_position": {"x": 30, "y": 0, "z": 0},
                    "steps": [{"dx": 10, "dy": 0, "dz": 0}],
                },
            )
        # A legacy occupant can leave the optional room, but cannot step back in.
        validate_movement(
            topology,
            {
                "start_position": {"x": 40, "y": 0, "z": 0},
                "steps": [{"dx": -10, "dy": 0, "dz": 0}],
            },
        )
        with self.assertRaisesRegex(ValueError, "Optional native access"):
            validate_movement(
                topology,
                {
                    "start_position": {"x": 40, "y": 0, "z": 0},
                    "steps": [
                        {"dx": -10, "dy": 0, "dz": 0},
                        {"dx": 10, "dy": 0, "dz": 0},
                    ],
                },
            )

    def test_runtime_plan_and_completion_stop_at_main_terminal_without_reward_replay(
        self,
    ):
        plan, topology = fixture()
        plan, topology = partition_rooms(
            plan,
            topology,
            main_source_orders=[1, 2, 3],
            access_evidence={4: {"source": "native-access-review"}},
        )
        configuration = {
            "compiled_plan": plan,
            "topology": topology,
            "evidence_hashes": {"plan": canonical_hash(plan)},
        }
        runtime_plan = plan_from_configuration(configuration)
        self.assertEqual(tuple(room.order for room in runtime_plan.rooms), (1, 2, 3))
        require_main_room(topology, runtime_plan.rooms[-1].order)
        with self.assertRaisesRegex(ValueError, "Optional room"):
            require_main_room(topology, 4)
        rooms = [
            {
                "order": room.order,
                "monsters": [
                    {
                        "role": monster.role,
                        "count": monster.count,
                        "ref_id": monster.ref_id,
                        "min_level": monster.native_min_level,
                        "max_level": monster.native_max_level,
                    }
                    for monster in room.monsters
                ],
            }
            for room in runtime_plan.rooms
        ]
        run = {
            "instance_id": 7001,
            "catalog_hash": "old-hash",
            "status": "active",
            "current_room": 4,
            "revision": 4,
            "rooms": rooms,
        }
        encounters = [
            {
                "instance_id": 7001,
                "room_order": order,
                "status": "victory",
                "fight_id": 500 + order,
            }
            for order in (1, 2, 3)
        ]
        old_run, old_encounters = deepcopy(run), deepcopy(encounters)
        proposal = canonical_completion_preview(
            run,
            encounters,
            configuration,
            expected_old_hash="old-hash",
        )
        self.assertEqual(
            (proposal["status"], proposal["current_room"], proposal["revision"]),
            ("completed", 3, 5),
        )
        self.assertEqual(proposal["earned_fight_ids"], [501, 502, 503])
        self.assertFalse(proposal["reward_replay"])
        self.assertEqual(proposal["encounter_updates"], [])
        self.assertEqual((run, encounters), (old_run, old_encounters))

    def test_legacy_topology_keeps_all_rooms_required(self):
        _, topology = fixture()
        self.assertEqual(main_room_orders(topology), (1, 2, 3, 4))
        require_main_room(topology, 4)
        request = {
            "start_position": {"x": 30, "y": 0, "z": 0},
            "steps": [{"dx": 10, "dy": 0, "dz": 0}],
        }
        validate_movement(topology, request)

    def test_shared_main_optional_floor_resolves_to_main_in_real_lookups(self):
        from wakfu_server.dungeon_native_flow import object_room
        from wakfu_server.dungeon_object_states import packets
        from wakfu_server.dungeon_optional_rooms import cell_rooms
        from wakfu_server.dungeon_runtime import room_for_position

        plan, topology = fixture()
        plan, topology = partition_rooms(
            plan,
            topology,
            main_source_orders=[1, 2, 3],
            access_evidence={4: {"source": "native-access-review"}},
        )
        shared = tuple(topology["rooms"][0]["cells"][0])
        topology["rooms"][3]["cells"].append(list(shared))
        self.assertEqual(cell_rooms(topology)[shared], 1)
        source = {
            "id": 88,
            "map_id": 910,
            "x": shared[0],
            "y": shared[1],
            "z": shared[2],
        }
        self.assertEqual(object_room(topology, source), 1)
        self.assertEqual(room_for_position({"topology": topology}, 910, *shared), 1)
        self.assertEqual(
            packets(topology, [], map_id=910, instance_id=7001, unlocked_room=1),
            (),
        )

        main_overlap = deepcopy(topology)
        main_overlap["rooms"][1]["cells"].append(list(shared))
        with self.assertRaisesRegex(ValueError, "Ambiguous required or optional"):
            cell_rooms(main_overlap)
        legacy = deepcopy(topology)
        legacy.pop("optional_room_policy")
        self.assertEqual(cell_rooms(legacy)[shared], 4)
        with self.assertRaisesRegex(ValueError, "Dungeon terrain belongs to multiple"):
            cell_rooms(legacy, reject_ambiguous=True)

    def test_physical_and_shared_exits_complete_at_required_not_physical_terminal(self):
        from unittest.mock import patch
        from wakfu_server.dungeon_physical_doors import packets as physical_packets
        from wakfu_server.dungeon_shared_arena import packets as shared_packets

        plan, topology = fixture()
        _, topology = partition_rooms(
            plan,
            topology,
            main_source_orders=[1, 2, 3],
            access_evidence={4: {"source": "native-access-review"}},
        )
        topology["policy"] = "native_physical_door_victory_policy"
        topology["physical_doors"] = [
            {
                "source_id": 88,
                "destination_room": 3,
                "position": [30, 0, 0],
            }
        ]
        self.assertEqual(
            len(
                physical_packets(
                    topology,
                    map_id=910,
                    instance_id=7001,
                    unlocked_room=3,
                    completed=True,
                )
            ),
            1,
        )
        with self.assertRaisesRegex(ValueError, "progress frontier"):
            physical_packets(
                topology,
                map_id=910,
                instance_id=7001,
                unlocked_room=4,
                completed=False,
            )

        legacy = deepcopy(topology)
        legacy.pop("optional_room_policy")
        with self.assertRaisesRegex(ValueError, "completion state"):
            physical_packets(
                legacy,
                map_id=910,
                instance_id=7001,
                unlocked_room=3,
                completed=True,
            )

        shared_plan, shared = fixture()
        _, shared = partition_rooms(
            shared_plan,
            shared,
            main_source_orders=[1, 2, 3],
            access_evidence={4: {"source": "native-access-review"}},
        )
        shared["policy"] = "native_shared_arena_sequential_policy"
        shared["doors"] = []
        shared["auto_edges"] = []
        same_cells = deepcopy(shared["rooms"][0]["cells"])
        for room in shared["rooms"]:
            room["cells"] = deepcopy(same_cells)
            room["anchor"] = same_cells[0]
        shared["exploration_geometry"] = {
            "cells": deepcopy(same_cells),
            "edges": [],
        }
        shared["shared_arena_evidence"] = {
            "source_url": "reviewed",
            "authority": "native",
        }
        shared["physical_exit_objects"] = [
            {
                "source_id": 88,
                "room_order": 1,
                "native_approach_cells": [same_cells[0]],
            }
        ]
        source = {"id": 88, "map_id": 910}
        with patch("wakfu_server.generic_transports.source", return_value=source):
            self.assertEqual(
                len(
                    shared_packets(
                        shared,
                        map_id=910,
                        instance_id=7001,
                        unlocked_room=3,
                        completed=True,
                    )
                ),
                1,
            )
            legacy_shared = deepcopy(shared)
            legacy_shared.pop("optional_room_policy")
            with self.assertRaisesRegex(
                ValueError, "completion contradicts progression"
            ):
                shared_packets(
                    legacy_shared,
                    map_id=910,
                    instance_id=7001,
                    unlocked_room=3,
                    completed=True,
                )


if __name__ == "__main__":
    unittest.main()
