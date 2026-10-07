import struct
import unittest
from types import SimpleNamespace

from wakfu_server.combat.combat_external_markers import ExternalFightMarkers
from wakfu_server.combat.combat_multiplayer_wire import (
    decode_external,
    external_marker_actor_id,
)
from wakfu_server import monsters


def sample_shared(*, instance_id=0, duel=False):
    actor1 = SimpleNamespace(id=17, team=0)
    actor2 = SimpleNamespace(id=-201, team=1)
    fight = SimpleNamespace(
        id=53,
        phase="placement",
        native_table_turn=0,
        actors={17: actor1, -201: actor2},
    )
    arena = {
        "map_id": 1134,
        # Fight-arena wire instance may be character-owned. The external
        # marker's world scope is the shared fight instance, not this field.
        "instance_id": 17,
        "x": 1,
        "y": 2,
        "width": 1,
        "height": 1,
        "min_z": -1,
        "max_z": 0,
        "cell_masks": [0],
        "team_values": [],
    }
    participants = {
        1: SimpleNamespace(character_id=17, account_id=1, generation="g1"),
    }
    return SimpleNamespace(
        fight=fight,
        map_id=1134,
        instance_id=instance_id,
        is_duel=duel,
        participants=participants,
        group_lease=((1134, 0, 77), "g1", 53, 1),
        join_context={
            "arena": arena,
            # Native combat bootstrap uses this terrain/effect-area template
            # (cuY.eHc -> fbr.iU), distinct from public map_id 1134.
            "terrain_effect_id": 46,
            "leaders": {0: 17, 1: -201},
            "monsters": {
                -201: monsters.owned_instance(
                    5525, 1, -201, map_id=1134, x=14, y=9, z=2
                )
            },
            "world_marker_cells": ((14, 9),),
            "world_marker_origin": (14, 9, 2),
            "fight_started_at": 99.5,
        },
    )


class ExternalFightMarkerTests(unittest.TestCase):
    def test_create_update_snapshot_and_remove_lifecycle(self):
        markers = ExternalFightMarkers()
        shared = sample_shared()
        created = markers.update(shared, now_ms=100_000, now_monotonic=100.0)
        self.assertEqual(created[0], 13753)
        body = decode_external(created[1])
        self.assertEqual(body["fight_id"], 53)
        self.assertEqual(body["kind"], 2)
        self.assertEqual(body["myo"], shared.join_context["terrain_effect_id"])
        self.assertNotEqual(body["myo"], shared.map_id)
        self.assertEqual(body["myp"], external_marker_actor_id(53))
        self.assertEqual(body["myr"], [17, -201])
        self.assertEqual(body["teams"], [(17, 0), (-201, 1)])
        self.assertEqual(body["phase_code"], 1)
        self.assertEqual(body["jqi"], 0)
        self.assertEqual(body["myu"], 99_500)
        # QI stays at the public world cell, while cuY.mys addresses the
        # native 18x18 scene partition containing that cell.
        self.assertEqual(body["mys"], [(0, 0)])
        self.assertEqual(body["flags"], [False] * 4)
        from wakfu_server.combat.combat_wire import decode_topology

        marker_topology = decode_topology(body["topology"])
        self.assertEqual(
            (marker_topology["x"], marker_topology["y"], marker_topology["min_z"]),
            (14, 9, 2),
        )
        self.assertEqual(marker_topology["max_z"], 3)
        self.assertEqual(marker_topology["instance_id"], 0)
        self.assertEqual(marker_topology["cell_masks"], [0])
        snapshots = markers.world_snapshots(1134, 0)
        self.assertEqual([packet[0] for packet in snapshots], [12608, 13753])
        self.assertEqual(snapshots[1], created)
        from wakfu_server.combat_monster_world import spawn_group

        self.assertEqual(
            snapshots[0][1],
            spawn_group(tuple(shared.join_context["monsters"].values()), group_id=77),
        )
        self.assertEqual(markers.snapshots(1134, 0), (created,))
        self.assertEqual(markers.snapshots(1134, 0, exclude_character_id=17), ())
        self.assertEqual(markers.snapshots(1134, 1), ())

        # Timestamp is fixed at creation. A phase/turn change refreshes the
        # late-join snapshot and uses the native END_PLACEMENT carrier for
        # clients that already registered this fight ID.
        self.assertIsNone(markers.update(shared, now_ms=101_000, now_monotonic=101.0))
        shared.fight.phase = "active"
        shared.fight.native_table_turn = 2
        update = markers.update(shared, now_ms=102_000, now_monotonic=102.0)
        self.assertEqual(update, (12233, struct.pack(">i", 53)))
        late_join = markers.snapshots(1134, 0)[0]
        latest = decode_external(late_join[1])
        self.assertEqual(latest["phase_code"], 2)
        self.assertEqual(latest["jqi"], 2)
        self.assertEqual(latest["myu"], 99_500)
        self.assertEqual(late_join[0], 13753)
        self.assertIsNone(markers.update(shared, now_ms=103_000, now_monotonic=103.0))

        removed = markers.remove(53)
        self.assertEqual(removed[0], 12238)
        self.assertEqual(struct.unpack(">iiiB", removed[1]), (53, 1, -1, 1))
        self.assertIsNone(markers.remove(53))
        self.assertEqual(markers.snapshots(1134, 0), ())

    def test_terminal_stale_tick_does_not_allocate_timestamp_or_keep_marker_state(self):
        markers = ExternalFightMarkers()
        shared = sample_shared()
        packet = markers.update(shared, now_ms=100_000, now_monotonic=100.0)
        self.assertEqual(packet[0], 13753)
        self.assertIn(53, markers.started_at_ms)

        shared.fight.phase = "finished"
        removed = markers.update(shared, now_ms=101_000, now_monotonic=101.0)
        self.assertEqual(removed[0], 12238)
        self.assertNotIn(53, markers.markers)
        self.assertNotIn(53, markers.started_at_ms)

        # A late stale callback after terminal cleanup neither recreates the
        # advertisement nor leaves a timestamp/tombstone entry behind.
        self.assertIsNone(markers.update(shared, now_ms=102_000, now_monotonic=102.0))
        self.assertEqual(markers.markers, {})
        self.assertEqual(markers.started_at_ms, {})
        self.assertFalse(hasattr(markers, "announced_fights"))

    def test_phase_update_reaches_existing_observers_and_refreshes_late_join(self):
        markers = ExternalFightMarkers()
        shared = sample_shared()
        first = markers.update(shared, now_ms=100_000, now_monotonic=100.0)
        self.assertEqual(first[0], 13753)

        joined_actor = SimpleNamespace(id=18, team=0)
        shared.fight.actors[18] = joined_actor
        shared.participants[2] = SimpleNamespace(
            character_id=18, account_id=2, generation="g2"
        )
        shared.fight.phase = "active"
        shared.fight.native_table_turn = 1
        self.assertEqual(
            markers.update(shared, now_ms=101_000, now_monotonic=101.0),
            (12233, struct.pack(">i", 53)),
        )

        body = decode_external(markers.snapshots(1134, 0)[0][1])
        self.assertEqual(body["phase_code"], 2)
        self.assertEqual(body["jqi"], 1)
        self.assertEqual(body["teams"], [(17, 0), (-201, 1), (18, 0)])
        self.assertEqual(body["myr"], [17, -201])

        # A terminal removal clears the state. The finished phase blocks a
        # stale later tick from announcing the same fight again.
        self.assertEqual(markers.remove(53)[0], 12238)
        shared.fight.phase = "finished"
        self.assertIsNone(markers.update(shared, now_ms=102_000, now_monotonic=102.0))
        self.assertNotIn(53, markers.started_at_ms)

    def test_ineligible_instance_duel_and_bad_world_cells_fail_closed(self):
        for shared in (sample_shared(instance_id=8), sample_shared(duel=True)):
            markers = ExternalFightMarkers()
            self.assertIsNone(
                markers.update(shared, now_ms=100_000, now_monotonic=100.0)
            )
            self.assertEqual(markers.snapshots(1134, 0), ())

        markers = ExternalFightMarkers()
        shared = sample_shared()
        self.assertEqual(
            markers.update(shared, now_ms=100_000, now_monotonic=100.0)[0], 13753
        )
        shared.join_context["monsters"][-201]["map_id"] = 99
        removed = markers.update(shared, now_ms=101_000, now_monotonic=101.0)
        self.assertEqual(removed[0], 12238)
        self.assertEqual(markers.snapshots(1134, 0), ())

    def test_missing_authoritative_fields_do_not_create_marker(self):
        markers = ExternalFightMarkers()
        shared = sample_shared()
        del shared.join_context["leaders"]
        self.assertIsNone(markers.update(shared, now_ms=100_000, now_monotonic=100.0))
        shared = sample_shared()
        del shared.join_context["fight_started_at"]
        self.assertIsNone(markers.update(shared, now_ms=100_000, now_monotonic=100.0))
        shared = sample_shared()
        del shared.join_context["terrain_effect_id"]
        self.assertIsNone(markers.update(shared, now_ms=100_000, now_monotonic=100.0))
        shared = sample_shared()
        shared.join_context["terrain_effect_id"] = 0
        self.assertIsNone(markers.update(shared, now_ms=100_000, now_monotonic=100.0))
        markers = ExternalFightMarkers()
        shared = sample_shared()
        del shared.join_context["world_marker_cells"]
        self.assertIsNone(markers.update(shared, now_ms=100_000, now_monotonic=100.0))
        shared = sample_shared()
        del shared.join_context["world_marker_origin"]
        self.assertIsNone(markers.update(shared, now_ms=100_000, now_monotonic=100.0))

    def test_marker_requires_matching_owned_npc_group_lease(self):
        markers = ExternalFightMarkers()
        for lease in (
            None,
            ((1134, 0, 77), "g1", 52, 1),
            ((1134, 9, 77), "g1", 53, 1),
            ((1134, 0, 77), "g1", 53, 0),
        ):
            shared = sample_shared()
            shared.group_lease = lease
            self.assertIsNone(
                markers.update(shared, now_ms=100_000, now_monotonic=100.0)
            )
            self.assertEqual(markers.snapshots(1134, 0), ())

        shared = sample_shared()
        shared.join_context["monsters"][-201]["id"] = 201
        self.assertIsNone(markers.update(shared, now_ms=100_000, now_monotonic=100.0))
        self.assertEqual(markers.snapshots(1134, 0), ())

        # The lease generation is the original group claim; a participant
        # may reconnect under a newer session generation while that claim
        # remains live, so actor reconstruction must use the durable lease key.
        shared = sample_shared()
        shared.group_lease = ((1134, 0, 77), "retired-owner-generation", 53, 1)
        self.assertEqual(
            markers.update(shared, now_ms=100_000, now_monotonic=100.0)[0], 13753
        )

    def test_translation_rejects_z_overflow_without_mutating_private_arena(self):
        from wakfu_server.combat.combat_external_markers import _marker_topology
        from wakfu_server.combat.combat_wire import decode_topology

        shared = sample_shared()
        arena = shared.join_context["arena"]
        arena["min_z"] = -32768
        arena["max_z"] = 32767
        original = dict(arena)
        with self.assertRaisesRegex(ValueError, "Z range"):
            _marker_topology(arena, (14, 9, 1))
        self.assertEqual(arena, original)

        # A valid shift preserves the private topology fields and moves only
        # its public origin and vertical interval in the returned packet.
        normal_arena = dict(sample_shared().join_context["arena"])
        shifted = decode_topology(_marker_topology(normal_arena, (14, 9, 2)))
        self.assertEqual((shifted["x"], shifted["y"]), (14, 9))
        self.assertEqual((shifted["min_z"], shifted["max_z"]), (2, 3))
        self.assertEqual((shifted["map_id"], shifted["instance_id"]), (1134, 0))
        self.assertEqual(shifted["cell_masks"], normal_arena["cell_masks"])

    def test_native_partition_coordinates_floor_negative_world_cells(self):
        from wakfu_server.combat.combat_external_markers import _native_map_partitions

        self.assertEqual(
            _native_map_partitions(((-22, 16), (-23, 17), (-1, -1), (0, 0))),
            ((-2, 0), (-1, -1), (0, 0)),
        )
        markers = ExternalFightMarkers()
        shared = sample_shared()
        shared.join_context["world_marker_cells"] = ((-22, 16), (-23, 17))
        shared.join_context["world_marker_origin"] = (-22, 16, -1)
        body = decode_external(
            markers.update(shared, now_ms=100_000, now_monotonic=100.0)[1]
        )
        self.assertEqual(body["mys"], [(-2, 0)])
        from wakfu_server.combat.combat_wire import decode_topology

        topology = decode_topology(body["topology"])
        self.assertEqual((topology["x"], topology["y"]), (-22, 16))

    def test_native_partitions_cover_all_partitions_intersecting_qi(self):
        from wakfu_server.combat.combat_external_markers import _topology_partitions

        # Official 13753 fixtures: map1388 QI (-8,-17), 17x10; map1385
        # rectangle (-14,10), 17x13. The second crosses four partitions.
        self.assertEqual(
            set(_topology_partitions({"x": -8, "y": -17, "width": 17, "height": 10})),
            {(0, -1), (-1, -1)},
        )
        self.assertEqual(
            set(_topology_partitions({"x": -14, "y": 10, "width": 17, "height": 13})),
            {(0, 0), (0, 1), (-1, 1), (-1, 0)},
        )
        self.assertEqual(
            set(_topology_partitions({"x": 12, "y": 29, "width": 18, "height": 16})),
            {(0, 1), (1, 1), (1, 2), (0, 2)},
        )

    def test_native_partition_list_rejects_oversized_or_malformed_topology(self):
        from wakfu_server.combat.combat_external_markers import _topology_partitions

        with self.assertRaisesRegex(ValueError, "too long"):
            _topology_partitions({"x": 0, "y": 0, "width": 18 * 12, "height": 18 * 11})
        with self.assertRaisesRegex(ValueError, "bounds"):
            _topology_partitions({"x": 0, "y": 0, "width": True, "height": 1})

    def test_map_change_removes_old_marker_and_reentry_only_sees_current(self):
        markers = ExternalFightMarkers()
        shared = sample_shared()
        packet = markers.update(shared, now_ms=100_000, now_monotonic=100.0)
        self.assertEqual(markers.snapshots(1134, 0), (packet,))
        shared.map_id = 1135
        removed = markers.update(shared, now_ms=101_000, now_monotonic=101.0)
        self.assertEqual(removed[0], 12238)
        self.assertEqual(markers.snapshots(1134, 0), ())
        self.assertEqual(markers.snapshots(1135, 0), ())

    def test_invalid_cell_pairs_and_leader_team_mismatch_fail_closed(self):
        markers = ExternalFightMarkers()
        shared = sample_shared()
        shared.join_context["world_marker_cells"] = ((14,),)
        self.assertIsNone(markers.update(shared, now_ms=100_000, now_monotonic=100.0))
        shared = sample_shared()
        shared.join_context["leaders"] = {0: -201, 1: 17}
        self.assertIsNone(markers.update(shared, now_ms=100_000, now_monotonic=100.0))


if __name__ == "__main__":
    unittest.main()
