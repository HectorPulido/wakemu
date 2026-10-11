"""Regressions for explicitly reviewed nonadjacent mixed dungeon transports."""
import copy
import struct
import unittest
from unittest.mock import patch

from wakfu_server import dungeon_doors, dungeon_native_flow, dungeon_object_states


class HubTransportBindingTests(unittest.TestCase):
    def setUp(self):
        self.topology = {
            "policy": dungeon_native_flow.MIXED_POLICY,
            "rooms": [
                {"order": order, "cells": [[order, 0, 0]], "anchor": [order, 0, 0]}
                for order in range(1, 5)
            ],
            "doors": [],
        }

    def binding(self, start=2, end=4, gate=3):
        result = {"source_room": start, "destination_room": end}
        if gate is not None:
            result["progression_gate_room"] = gate
        return result

    def test_nonadjacent_forward_and_return_share_the_reviewed_frontier(self):
        self.assertEqual(
            dungeon_native_flow.validate_transport_binding(
                self.topology, self.binding(2, 4, 3)
            ),
            3,
        )
        self.assertEqual(
            dungeon_native_flow.validate_transport_binding(
                self.topology, self.binding(4, 2, 3)
            ),
            3,
        )

    def test_adjacent_and_same_stage_bindings_keep_existing_contract(self):
        self.assertEqual(
            dungeon_native_flow.validate_transport_binding(
                self.topology, self.binding(2, 3, None)
            ),
            2,
        )
        self.assertIsNone(
            dungeon_native_flow.validate_transport_binding(
                self.topology, self.binding(2, 2, None)
            )
        )

    def test_nonadjacent_binding_requires_exact_mixed_gate(self):
        for topology, binding in (
            (self.topology, self.binding(2, 4, None)),
            (self.topology, self.binding(2, 4, 2)),
            (self.topology, self.binding(2, 4, 4)),
            (self.topology, self.binding(2, 4, True)),
            (
                {**self.topology, "policy": dungeon_native_flow.TELEPORT_POLICY},
                self.binding(2, 4, 3),
            ),
            (self.topology, self.binding(2, 5, 3)),
            (self.topology, self.binding(0, 4, 3)),
            (self.topology, self.binding(2, 2, 1)),
        ):
            with self.subTest(topology=topology["policy"], binding=binding):
                with self.assertRaises(ValueError):
                    dungeon_native_flow.validate_transport_binding(topology, binding)


class HubTransportResolutionTests(unittest.TestCase):
    def test_literal_native_2_to_4_transport_requires_exact_binding_and_gate(self):
        source = {
            "map_id": 1079,
            "id": 26747,
            "x": 10,
            "y": 0,
            "z": 0,
            "approach_positions": [{"x": 9, "y": 0, "z": 0}],
            "approach_blocks_center": True,
            "destinations": [
                {
                    "destination_id": 0,
                    "map_id": 1079,
                    "x": 40,
                    "y": 0,
                    "z": 0,
                    "criterion": "",
                    "cyZ": -1,
                    "cyX": 0,
                    "cyW": 0,
                    "item_reference": 0,
                    "native_altitude_walkable": True,
                }
            ],
        }
        binding = {
            "source_id": 26747,
            "destination_id": 0,
            "source_room": 2,
            "destination_room": 4,
            "progression_gate_room": 3,
            "source_position": [10, 0, 0],
            "native_approach_cells": [[9, 0, 0]],
            "destination_position": [40, 0, 0],
        }
        topology = {
            "policy": dungeon_native_flow.MIXED_POLICY,
            "asset_map_id": 1079,
            "rooms": [
                {"order": order, "cells": [[pos, 0, 0]], "anchor": [pos, 0, 0]}
                for order, pos in ((1, 0), (2, 9), (3, 20), (4, 40))
            ],
            "doors": [binding],
        }
        body = struct.pack(">qiBi", 26747, 0, 0, 2)
        with patch("wakfu_server.generic_transports.source", return_value=source):
            self.assertEqual(
                dungeon_doors.resolve(
                    {"map_id": 1079, "instance_id": 7},
                    body,
                    source_allowed=lambda actor, native: True,
                    room_for_position=lambda map_id, x, y, z: 2 if x == 10 else 4,
                    criterion_allowed=lambda criterion: True,
                    topology=topology,
                )[:2],
                (2, 4),
            )
            for mutate in (
                lambda row: row.update(progression_gate_room=2),
                lambda row: row.update(destination_position=[41, 0, 0]),
            ):
                invalid = copy.deepcopy(topology)
                mutate(invalid["doors"][0])
                with self.subTest(binding=invalid["doors"][0]):
                    with self.assertRaises(ValueError):
                        dungeon_doors.resolve(
                            {"map_id": 1079, "instance_id": 7},
                            body,
                            source_allowed=lambda actor, native: True,
                            room_for_position=lambda map_id, x, y, z: 2
                            if x == 10
                            else 4,
                            criterion_allowed=lambda criterion: True,
                            topology=invalid,
                        )


class HubTransportConfigurationAndPacketTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "map_id": 1079,
            "id": 26747,
            "x": 2,
            "y": 0,
            "z": 0,
            "approach_positions": [{"x": 2, "y": 0, "z": 0}],
            "approach_blocks_center": False,
            "destinations": [
                {
                    "destination_id": 2488,
                    "map_id": 1079,
                    "x": 4,
                    "y": 0,
                    "z": 0,
                    "criterion": "",
                    "cyZ": -1,
                    "cyX": 0,
                    "cyW": 0,
                    "item_reference": 0,
                    "native_altitude_walkable": True,
                }
            ],
        }
        self.binding = {
            "source_id": 26747,
            "destination_id": 2488,
            "source_room": 2,
            "destination_room": 4,
            "progression_gate_room": 3,
            "source_position": [2, 0, 0],
            "native_approach_cells": [[2, 0, 0]],
            "destination_position": [4, 0, 0],
        }
        self.topology = {
            "asset_map_id": 1079,
            "policy": dungeon_native_flow.MIXED_POLICY,
            "rooms": [
                {"order": 1, "anchor": [1, 0, 0], "cells": [[1, 0, 0]]},
                {"order": 2, "anchor": [2, 0, 0], "cells": [[2, 0, 0]]},
                {"order": 3, "anchor": [3, 0, 0], "cells": [[3, 0, 0]]},
                {"order": 4, "anchor": [4, 0, 0], "cells": [[4, 0, 0]]},
            ],
            "doors": [self.binding],
            "physical_doors": [],
            "physical_exit_objects": [],
        }

    def test_object_state_packet_uses_the_nonadjacent_destination_frontier(self):
        with patch("wakfu_server.generic_transports.source", return_value=self.source):
            locked = dungeon_object_states.packets(
                self.topology,
                [self.source],
                map_id=1079,
                instance_id=77,
                unlocked_room=3,
            )
            open_ = dungeon_object_states.packets(
                self.topology,
                [self.source],
                map_id=1079,
                instance_id=77,
                unlocked_room=4,
            )
        self.assertEqual(len(locked), 1)
        self.assertEqual(len(open_), 1)
        self.assertEqual(struct.unpack_from(">q", locked[0][1])[0], 26747)
        self.assertEqual((locked[0][1][19], locked[0][1][20]), (0, 0))
        self.assertEqual((open_[0][1][19], open_[0][1][20]), (1, 1))

    def test_configuration_accepts_only_a_consistent_explicit_hub_gate(self):
        from wakfu_server.dungeon_runtime_config import prepare_configuration

        monster = {
            "name": "Native",
            "ref_id": 1,
            "count": 1,
            "role": "monster",
            "native_min_level": 1,
            "native_max_level": 1,
            "guide_min_level": None,
            "guide_max_level": None,
        }
        plan = {
            "slug": "hub",
            "source_url": "native",
            "source_sha256": "a" * 64,
            "document_sha256": "b" * 64,
            "definition_id": 115,
            "template_id": 118,
            "asset_map_id": 1079,
            "diagnostics": [],
            "roster_ready": True,
            "rooms": [
                {"order": order, "diagnostics": [], "monsters": [dict(monster)]}
                for order in range(1, 5)
            ],
        }
        route = {
            "key": "native_dungeon_115",
            "definition_id": 115,
            "template_id": 118,
            "start_map_id": 1079,
        }
        self.assertEqual(
            prepare_configuration(
                plan,
                self.topology,
                route,
                version=1,
                provenance="test",
            )["topology"]["doors"][0]["progression_gate_room"],
            3,
        )
        malformed = copy.deepcopy(self.topology)
        malformed["doors"][0]["progression_gate_room"] = 2
        with self.assertRaisesRegex(ValueError, "progression gate"):
            prepare_configuration(
                plan,
                malformed,
                route,
                version=1,
                provenance="test",
            )


if __name__ == "__main__":
    unittest.main()
