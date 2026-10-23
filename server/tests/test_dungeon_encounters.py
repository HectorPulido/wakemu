import copy
import unittest
from unittest.mock import patch
from wakfu_server.dungeon_encounters import room_members, reachable_cells
from wakfu_server.monsters import reference


class DungeonEncounterTests(unittest.TestCase):
    def setUp(self):
        native = reference(1)
        self.run = dict(
            status="active",
            instance_id=123456,
            current_room=1,
            rooms=[
                dict(
                    order=1,
                    monsters=[
                        dict(
                            ref_id=1,
                            count=2,
                            min_level=native["min_level"],
                            max_level=native["max_level"],
                        )
                    ],
                )
            ],
        )
        self.geometry = dict(
            cells=[[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]],
            edges=[
                [[0, 0, 0], [1, 0, 0]],
                [[1, 0, 0], [2, 0, 0]],
                [[2, 0, 0], [3, 0, 0]],
            ],
        )

    def test_unadmitted_pinned_roster_refuses_before_actor_construction(self):
        before = copy.deepcopy(self.run)
        policy = dict(schema="native-npc-activation-v1", enabled_monsters={})
        with patch(
            "wakfu_server.dungeon_monster_admission.current_policy", return_value=policy
        ):
            with patch("wakfu_server.dungeon_encounters.owned_instance") as constructor:
                with self.assertRaisesRegex(
                    ValueError, "1 lacks ordinary NPC admission"
                ):
                    self.build()
                constructor.assert_not_called()
        self.assertEqual(self.run, before)

    def build(self, **kwargs):
        options = dict(
            asset_map_id=1086,
            anchor=(0, 0, 0),
            geometry=self.geometry,
            group_id=100,
            select_level=lambda native, row: native["min_level"],
        )
        options.update(kwargs)
        return room_members(self.run, **options)

    def test_asset_and_runtime_instance_are_distinct(self):
        members = self.build()
        self.assertEqual(
            [(-100, 1086, 123456), (-101, 1086, 123456)],
            [(m["id"], m["map_id"], m["instance_id"]) for m in members],
        )
        self.assertEqual(
            [(1, 0, 0), (2, 0, 0)], [(m["x"], m["y"], m["z"]) for m in members]
        )

    def test_occupied_cell_is_skipped_but_reachable_neighbor_used(self):
        self.assertEqual(
            ((2, 0, 0), (3, 0, 0)),
            reachable_cells(self.geometry, (0, 0, 0), 2, occupied=[(1, 0, 0)]),
        )

    def test_disconnected_room_cannot_supply_spawn_cells(self):
        self.geometry["edges"] = self.geometry["edges"][:1]
        with self.assertRaises(ValueError):
            self.build()

    def test_grade_policy_cannot_override_native_bounds(self):
        with self.assertRaises(ValueError):
            self.build(select_level=lambda native, row: native["max_level"] + 1)

    def test_catalog_drift_rejected(self):
        self.run["rooms"][0]["monsters"][0]["min_level"] += 1
        with self.assertRaises(ValueError):
            self.build()

    def test_unknown_count_and_completed_run_rejected(self):
        self.run["rooms"][0]["monsters"][0]["count"] = None
        with self.assertRaises(ValueError):
            self.build()
        self.run["status"] = "completed"
        with self.assertRaises(ValueError):
            self.build()

    def test_wire_identity_overflow_rejected(self):
        with self.assertRaises(ValueError):
            self.build(group_id=2**63 - 1)

    def test_missing_authoritative_policy_rejected(self):
        with self.assertRaises(ValueError):
            self.build(select_level=None)

    def test_native_groups_larger_than_eight_keep_all_monsters(self):
        from wakfu_server.combat_monster_world import spawn_group

        for count in (9, 10, 16):
            with self.subTest(count=count):
                self.run["rooms"][0]["monsters"][0]["count"] = count
                self.geometry = dict(
                    cells=[(n, 0, 0) for n in range(count + 1)],
                    edges=[((n, 0, 0), (n + 1, 0, 0)) for n in range(count)],
                )
                members = self.build()
                self.assertEqual(len(members), count)
                self.assertEqual(len({m["id"] for m in members}), count)
                self.assertEqual(spawn_group(members, group_id=100)[1], count)

    def test_capacity_reserves_the_maximum_player_party(self):
        from wakfu_server.maps.dungeon_capacity import (
            MAX_DUNGEON_MONSTERS,
            MAX_PARTY_PLAYERS,
            MAX_PLACEMENT_ACTORS,
        )

        self.assertEqual(MAX_DUNGEON_MONSTERS + MAX_PARTY_PLAYERS, MAX_PLACEMENT_ACTORS)
        self.run["rooms"][0]["monsters"][0]["count"] = MAX_DUNGEON_MONSTERS + 1
        with self.assertRaisesRegex(ValueError, "placement capacity"):
            self.build()
