import copy
import json
import os
import struct
import unittest
from pathlib import Path
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

    def test_intermediate_exterior_requires_explicit_completed_exit_proof(self):
        source = self.source(16, 10, 106, 99, target_map=2)
        sources = self.sources + [source]
        self.registry[16] = source
        with self.assertRaisesRegex(ValueError, "intermediate room"):
            self.hydrate(3, completed=True, sources=sources)
        topology = copy.deepcopy(self.topology)
        topology["completed_exit_witness"] = dict(source_id=16, room_order=2)
        topology["physical_exit_objects"] = [dict(source_id=16, room_order=2)]
        before = self.flags(self.hydrate(3, sources=sources, topology=topology))
        after = self.flags(
            self.hydrate(3, completed=True, sources=sources, topology=topology)
        )
        self.assertEqual(before[16], (0, 0))
        self.assertEqual(after[16], (1, 1))
        topology["completed_exit_witness"]["source_id"] = 999
        with self.assertRaisesRegex(ValueError, "intermediate room"):
            self.hydrate(3, completed=True, sources=sources, topology=topology)

    def test_pinned_crypt_and_nest_exits_hydrate_at_the_initial_frontier(self):
        root = Path(__file__).parent
        fixture = json.loads(
            (root / "fixtures/native_astrub_crypt_nest_sources.json").read_text()
        )
        configs = (
            root.parent
            / "wakfu_server/maps/owned_story_profiles/astrub-crypt-889.configuration.json",
            root.parent
            / "wakfu_server/maps/owned_story_profiles/astrub-nest-728.configuration.json",
        )
        expected = {889: (23618,), 728: (20652, 26431)}
        for path in configs:
            document = json.loads(path.read_text())
            topology = document["topology"]
            map_id = topology["asset_map_id"]
            sources = [row for row in fixture if row["map_id"] == map_id]
            indexed = {row["id"]: row for row in sources}
            self.assertEqual(
                {row["source_id"] for row in topology["native_story_exits"]},
                set(expected[map_id]),
            )
            with patch(
                "wakfu_server.generic_transports.source",
                side_effect=lambda asset, identity: indexed.get(identity)
                if asset == map_id
                else None,
            ):
                states = self.flags(
                    packets(
                        topology,
                        sources,
                        map_id=map_id,
                        instance_id=144115188075855924,
                        unlocked_room=1,
                        completed=False,
                    )
                )
            for source_id in expected[map_id]:
                self.assertEqual(states[source_id], (1, 1))

    def test_zinit_reef_shared_arena_uses_pinned_native_story_exits(self):
        root = Path(__file__).parent.parent / "wakfu_server/maps/owned_story_profiles"
        configuration = json.loads(
            (root / "zinit-reef-980.configuration.json").read_text()
        )
        native = json.loads((root / "zinit-reef-980.native.v1.json").read_text())
        topology = configuration["topology"]
        self.assertEqual(topology["doors"], [])
        self.assertEqual(len(topology["rooms"]), 6)
        self.assertEqual(topology["rooms"][0]["cells"], topology["rooms"][1]["cells"])

        sources = list(native["teleporters"].values())
        indexed = {source["id"]: source for source in sources}
        with patch(
            "wakfu_server.generic_transports.source",
            side_effect=lambda asset, identity: indexed.get(identity)
            if asset == 980
            else None,
        ):
            states = self.flags(
                packets(
                    topology,
                    sources,
                    map_id=980,
                    instance_id=144115188075855924,
                    unlocked_room=1,
                    completed=False,
                )
            )

        # These are the two actual story exits, and their native asset
        # ownership/source guards are checked by packets(). Other portal
        # availability is deliberately left to the native criteria.
        self.assertEqual(states[25420], (1, 1))
        self.assertEqual(states[25401], (1, 1))
        self.assertTrue(set(states) <= set(indexed))
        self.assertNotIn(25402, states)

        with patch(
            "wakfu_server.generic_transports.source",
            side_effect=lambda asset, identity: indexed.get(identity)
            if asset == 980
            else None,
        ):
            completed_states = self.flags(
                packets(
                    topology,
                    sources,
                    map_id=980,
                    instance_id=144115188075855924,
                    unlocked_room=6,
                    completed=True,
                )
            )
        self.assertEqual(completed_states[25420], (1, 1))
        self.assertEqual(completed_states[25401], (1, 1))
        self.assertTrue(set(completed_states) <= set(indexed))

        tampered = copy.deepcopy(topology)
        tampered["native_story_exits"][0]["source_sha256"] = "0" * 64
        with patch(
            "wakfu_server.generic_transports.source",
            side_effect=lambda asset, identity: indexed.get(identity)
            if asset == 980
            else None,
        ), self.assertRaises(ValueError):
            packets(
                tampered,
                sources,
                map_id=980,
                instance_id=144115188075855924,
                unlocked_room=1,
                completed=False,
            )

        # Shared cells are accepted only for the typed, map-bound story whose
        # real victory dependencies attest the sequential arena reuse.
        for mutate in (
            lambda value: value.pop("owned_story_controller"),
            lambda value: value["owned_story_controller"].update(map_id=981),
            lambda value: value["rooms"][2].update(requires=[]),
        ):
            invalid = copy.deepcopy(topology)
            mutate(invalid)
            with patch(
                "wakfu_server.generic_transports.source",
                side_effect=lambda asset, identity: indexed.get(identity)
                if asset == 980
                else None,
            ), self.assertRaises(ValueError):
                packets(
                    invalid,
                    sources,
                    map_id=980,
                    instance_id=144115188075855924,
                    unlocked_room=1,
                    completed=False,
                )

        ordinary = copy.deepcopy(self.topology)
        ordinary["rooms"][1]["cells"] = ordinary["rooms"][0]["cells"]
        with self.assertRaises(ValueError):
            self.hydrate(1, topology=ordinary)

        # Adding optional-room policy restores strict ambiguity rejection even
        # when the owned story controller is otherwise valid.
        optional = copy.deepcopy(topology)
        optional["optional_room_policy"] = {"schema": "ambiguous-guard"}
        with patch(
            "wakfu_server.generic_transports.source",
            side_effect=lambda asset, identity: indexed.get(identity)
            if asset == 980
            else None,
        ), self.assertRaises(ValueError):
            packets(
                optional,
                sources,
                map_id=980,
                instance_id=144115188075855924,
                unlocked_room=1,
                completed=False,
            )

    @unittest.skipUnless(
        os.environ.get("WAKFU_DATABASE_URL"), "requires native teleporter catalog"
    )
    def test_huppermage_platform_hides_unclaimed_exterior_sources_but_keeps_story_exit(
        self,
    ):
        # Replace the synthetic small-map source registry from setUp with the
        # real pinned generic transport catalog for this source-bound case.
        self.native.stop()
        root = Path(__file__).parent.parent / "wakfu_server/maps/owned_story_profiles"
        configuration = json.loads(
            (root / "huppermage-platform-1030.configuration.json").read_text()
        )
        from wakfu_server.generic_transports import source as native_source

        identities = (25668, 25671, 25674, 25677)
        sources = [native_source(1030, identity) for identity in identities]
        self.assertTrue(all(source is not None for source in sources))
        states = self.flags(
            packets(
                configuration["topology"],
                sources,
                map_id=1030,
                instance_id=144115188075855952,
                unlocked_room=1,
                completed=False,
            )
        )
        self.assertEqual(states[25668], (0, 0))
        self.assertEqual(states[25671], (0, 0))
        self.assertEqual(states[25677], (0, 0))
        self.assertEqual(states[25674], (1, 1))
