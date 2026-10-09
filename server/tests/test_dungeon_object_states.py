import copy
import struct
import unittest
from unittest.mock import patch

from wakfu_server.dungeon_object_states import (
    packets,
    state_packet,
    state_payload,
    transition_packets,
)


class DungeonObjectStateTests(unittest.TestCase):
    def setUp(self):
        self.topology = {
            "rooms": [
                {"order": 1, "cells": [(0, 0, 0)]},
                {"order": 2, "cells": [(10, 0, 0)]},
                {"order": 3, "cells": [(20, 0, 0)]},
            ],
            "doors": [
                {
                    "source_id": 10,
                    "destination_id": 100,
                    "source_room": 1,
                    "destination_room": 2,
                },
                {
                    "source_id": 11,
                    "destination_id": 101,
                    "source_room": 2,
                    "destination_room": 1,
                },
                {
                    "source_id": 12,
                    "destination_id": 102,
                    "source_room": 2,
                    "destination_room": 3,
                },
                {
                    "source_id": 13,
                    "destination_id": 103,
                    "source_room": 3,
                    "destination_room": 2,
                },
            ],
        }
        self.sources = [
            self.source(10, 0, 100, 10),
            self.source(11, 10, 101, 0),
            self.source(12, 10, 102, 20),
            self.source(13, 20, 103, 10),
            self.source(14, 0, 104, 99, target_map=2),
            self.source(15, 20, 105, 99, target_map=2),
        ]
        self.registry = {row["id"]: row for row in self.sources}
        self.native = patch(
            "wakfu_server.generic_transports.source",
            side_effect=lambda map_id, identity: self.registry.get(identity)
            if map_id == 1
            else None,
        )
        self.native.start()
        self.addCleanup(self.native.stop)

    @staticmethod
    def source(identity, x, destination, target_x, target_map=1):
        return {
            "id": identity,
            "map_id": 1,
            "x": x,
            "y": 0,
            "z": 0,
            "destinations": [
                {
                    "destination_id": destination,
                    "map_id": target_map,
                    "x": target_x,
                    "y": 0,
                    "z": 0,
                }
            ],
        }

    def hydrate(self, frontier, completed=False, **overrides):
        return packets(
            overrides.get("topology", self.topology),
            overrides.get("sources", self.sources),
            map_id=1,
            instance_id=99,
            unlocked_room=frontier,
            completed=completed,
        )

    @staticmethod
    def flags(rows):
        return {
            struct.unpack_from(">q", body)[0]: (body[19], body[20])
            for opcode, body in rows
        }

    def test_official_fixed_vectors_reveal_then_enable_without_base_rewrite(self):
        self.assertEqual(
            state_payload(visible=True, usable=False).hex(),
            "01020000000602000101000000000000000000",
        )
        self.assertEqual(
            state_payload(visible=True, usable=True).hex(),
            "01020000000602000101010000000000000000",
        )
        opcode, body = state_packet(
            self.sources[0], map_id=1, instance_id=99, visible=True, usable=True
        )
        self.assertEqual(opcode, 12344)
        self.assertEqual(struct.unpack_from(">qH", body), (10, 19))

    def test_frontier_unlocks_forward_and_reverse_while_final_exit_waits_for_victory(
        self,
    ):
        first = self.flags(self.hydrate(1))
        self.assertEqual(
            first,
            {10: (0, 0), 11: (0, 0), 12: (0, 0), 13: (0, 0), 14: (1, 1), 15: (0, 0)},
        )
        second = self.flags(self.hydrate(2))
        self.assertEqual(second[10], (1, 1))
        self.assertEqual(second[11], (1, 1))
        self.assertEqual(second[12], (0, 0))
        final = self.flags(self.hydrate(3))
        self.assertEqual(final[13], (1, 1))
        self.assertEqual(final[15], (0, 0))
        self.assertEqual(self.flags(self.hydrate(3, completed=True))[15], (1, 1))
        self.assertEqual(self.hydrate(2), self.hydrate(2))

    def test_state_rejects_unknown_object_wrong_asset_and_public_context(self):
        for source, map_id, instance in (
            ({**self.sources[0], "id": 999}, 1, 99),
            (self.sources[0], 2, 99),
            (self.sources[0], 1, 0),
            (self.sources[0], True, 99),
            (self.sources[0], 1, True),
        ):
            with self.assertRaises(ValueError):
                state_packet(
                    source,
                    map_id=map_id,
                    instance_id=instance,
                    visible=True,
                    usable=True,
                )
        for args in (
            {"visible": 1, "usable": True},
            {"visible": False, "usable": True},
            {"visible": True, "usable": True, "state_id": True},
        ):
            with self.assertRaises(ValueError):
                state_payload(**args)

    def test_malformed_topology_and_forged_route_fail_closed(self):
        topology = copy.deepcopy(self.topology)
        topology["doors"][0]["destination_room"] = 3
        with self.assertRaises(ValueError):
            self.hydrate(2, topology=topology)
        sources = copy.deepcopy(self.sources)
        sources[0]["destinations"][0]["x"] = 20
        with self.assertRaises(ValueError):
            self.hydrate(2, sources=sources)
        with self.assertRaises(ValueError):
            self.hydrate(2, completed=True)
        with self.assertRaises(ValueError):
            self.hydrate(True)
        with self.assertRaises(ValueError):
            self.hydrate(1, sources=self.sources + [self.sources[0]])

    def test_reviewed_internal_door_keeps_mutually_exclusive_neo_route_separate(self):
        sources = copy.deepcopy(self.sources)
        sources[0]["destinations"].append(
            {
                "destination_id": 999,
                "map_id": 1459,
                "x": 99,
                "y": 0,
                "z": 0,
                "criterion": "IsNeoServer()",
            }
        )
        self.assertEqual(self.flags(self.hydrate(2, sources=sources))[10], (1, 1))

    def test_committed_victory_reveals_then_enables_and_replay_has_no_delta(self):
        rows = transition_packets(
            self.topology,
            self.sources,
            map_id=1,
            instance_id=99,
            previous_unlocked_room=1,
            unlocked_room=2,
        )
        self.assertEqual(
            [
                (struct.unpack_from(">q", body)[0], body[19], body[20])
                for opcode, body in rows
            ],
            [(10, 1, 0), (10, 1, 1), (11, 1, 0), (11, 1, 1)],
        )
        self.assertEqual(
            transition_packets(
                self.topology,
                self.sources,
                map_id=1,
                instance_id=99,
                previous_unlocked_room=2,
                unlocked_room=2,
            ),
            (),
        )
        with self.assertRaises(ValueError):
            transition_packets(
                self.topology,
                self.sources,
                map_id=1,
                instance_id=99,
                previous_unlocked_room=2,
                unlocked_room=1,
            )
