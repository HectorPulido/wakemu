import copy
import struct
import unittest
from unittest.mock import patch
from wakfu_server.maps.dungeon_object_states import (
    packets,
    native_interactions_enabled,
    transition_packets,
)


class AutomaticDungeonObjectTests(unittest.TestCase):
    def setUp(self):
        self.topology = dict(
            asset_map_id=1,
            policy="local_accessible_anchor_policy",
            doors=[],
            rooms=[
                dict(order=1, cells=[[0, 0, 0]]),
                dict(order=2, cells=[[10, 0, 0]]),
                dict(order=3, cells=[[20, 0, 0]]),
            ],
        )
        self.sources = [
            dict(
                id=1,
                map_id=1,
                x=99,
                y=0,
                z=0,
                destinations=[dict(destination_id=1, map_id=2)],
            ),
            dict(
                id=2,
                map_id=1,
                x=10,
                y=0,
                z=0,
                destinations=[dict(destination_id=2, map_id=2)],
            ),
            dict(
                id=3,
                map_id=1,
                x=0,
                y=0,
                z=0,
                destinations=[dict(destination_id=3, map_id=1)],
            ),
            dict(
                id=4,
                map_id=1,
                x=20,
                y=0,
                z=0,
                destinations=[
                    dict(destination_id=4, map_id=2, criterion="IsNeoServer()")
                ],
            ),
        ]
        registry = {row["id"]: row for row in self.sources}
        mocked = patch(
            "wakfu_server.generic_transports.source",
            side_effect=lambda map_id, identity: registry.get(identity)
            if map_id == 1
            else None,
        )
        mocked.start()
        self.addCleanup(mocked.stop)

    def hydrate(self, frontier, completed=False):
        return packets(
            self.topology,
            self.sources,
            map_id=1,
            instance_id=99,
            unlocked_room=frontier,
            completed=completed,
        )

    def test_outside_region_and_intermediate_exits_do_not_break_bootstrap(self):
        for frontier, completed in [(1, False), (2, False), (3, True)]:
            rows = self.hydrate(frontier, completed)
            self.assertEqual(
                [struct.unpack_from(">q", body)[0] for _, body in rows], [1, 2, 3, 4]
            )
            self.assertTrue(all(body[19:21] == b"\0\0" for _, body in rows))

    def test_local_policy_never_authorizes_native_interaction(self):
        self.assertFalse(native_interactions_enabled(self.topology))
        self.assertTrue(native_interactions_enabled(dict(doors=[])))
        self.assertTrue(
            native_interactions_enabled(dict(policy="strict_native_topology"))
        )

    def test_cannot_mix_generated_auto_rooms_and_claimed_native_doors(self):
        self.topology["doors"] = [
            dict(source_id=3, destination_id=3, source_room=1, destination_room=2)
        ]
        with self.assertRaisesRegex(ValueError, "cannot claim"):
            self.hydrate(1)

    def test_unknown_native_object_still_rejected(self):
        self.sources.append(dict(self.sources[0], id=999))
        with self.assertRaisesRegex(ValueError, "native asset"):
            self.hydrate(1)

    def test_victory_does_not_enable_unreviewed_native_exit(self):
        self.assertEqual(
            (),
            transition_packets(
                self.topology,
                self.sources,
                map_id=1,
                instance_id=99,
                previous_unlocked_room=2,
                unlocked_room=3,
                completed=True,
            ),
        )

    def test_strict_native_branch_keeps_intermediate_exit_rejection(self):
        self.topology.pop("policy")
        with self.assertRaisesRegex(ValueError, "intermediate room"):
            self.hydrate(2)
