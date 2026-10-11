"""Policy tests for the user-authorized classic family encounter builder."""
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from prepare_family_linear_dungeons import family_roster
from native_family_configuration_base import base as build_family_base


def native_family():
    return {
        "native_species_pool": [
            dict(ref_id=101, name_es="Family Mob A", min_level=10, max_level=12),
            dict(ref_id=102, name_es="Alternate Boss", min_level=10, max_level=12),
            dict(ref_id=103, name_es="Final Boss", min_level=10, max_level=12),
        ]
    }


class FamilyRosterPolicyTests(unittest.TestCase):
    def test_one_family_boss_only_in_final_room_and_six_player_quantity(self):
        pool = native_family()
        roster = family_roster(pool, 3, 103, quantity=8, exclude=[102])
        pool_refs = {m["ref_id"] for m in pool["native_species_pool"]}
        self.assertEqual(roster["boss_references"], [103])
        for room in roster["rooms"]:
            monsters = room["monsters"]
            self.assertEqual(sum(m["count"] for m in monsters), 8)
            self.assertTrue({m["ref_id"] for m in monsters} <= pool_refs)
            self.assertNotIn(102, {m["ref_id"] for m in monsters})
            self.assertEqual(
                sum(m["count"] for m in monsters if m["role"] == "boss"),
                1 if room["order"] == 3 else 0,
            )

    def test_quantity_one_keeps_preliminary_rooms_nonempty(self):
        roster = family_roster(native_family(), 3, 103, quantity=1, exclude=[102])
        self.assertEqual(
            [sum(m["count"] for m in room["monsters"]) for room in roster["rooms"]],
            [1, 1, 1],
        )
        self.assertEqual(
            [
                [m["ref_id"] for m in room["monsters"] if m["role"] == "boss"]
                for room in roster["rooms"]
            ],
            [[], [], [103]],
        )

    def test_rejects_missing_boss_or_unavailable_preliminary_family(self):
        with self.assertRaisesRegex(ValueError, "outside the native dungeon family"):
            family_roster(native_family(), 2, 999)
        with self.assertRaisesRegex(ValueError, "No resolved non-boss family"):
            family_roster(native_family(), 2, 103, exclude=[101, 102])


class FamilyConfigurationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.record = {
            "native": {"id": 9, "type": "DUNGEON_2_ROOMS"},
            "native_species_pool": [
                dict(ref_id=101, min_level=10, max_level=12),
                dict(ref_id=103, min_level=13, max_level=15),
                dict(ref_id=104, min_level=16, max_level=18),
            ],
        }
        self.route = dict(
            key="native_dungeon_9", definition_id=9, template_id=2, start_map_id=3
        )
        self.rooms = [
            dict(order=1, monsters=[self.monster(101)]),
            dict(order=2, monsters=[self.monster(103, role="boss")]),
        ]

    @staticmethod
    def monster(ref_id, *, role="monster", count=1, levels=None):
        bounds = levels or {101: (10, 12), 103: (13, 15), 104: (16, 18)}[ref_id]
        return dict(
            ref_id=ref_id,
            count=count,
            role=role,
            native_min_level=bounds[0],
            native_max_level=bounds[1],
        )

    def build(self, *, route=None, rooms=None):
        # The structural unit cases do not need a native catalog fixture.
        with patch("wakfu_server.dungeon_instances._load_routes") as load_routes:
            result = build_family_base(
                self.record, route or self.route, rooms or self.rooms
            )
        return result, load_routes

    def test_valid_base_uses_canonical_route_loader_and_allows_multiple_final_bosses(
        self,
    ):
        rooms = [
            dict(order=1, monsters=[self.monster(101)]),
            dict(
                order=2,
                monsters=[
                    self.monster(103, role="boss"),
                    self.monster(104, role="boss"),
                ],
            ),
        ]
        result, load_routes = self.build(rooms=rooms)
        load_routes.assert_called_once_with([self.route])
        self.assertEqual(result["compiled_plan"]["boss_references"], [103, 104])

    def test_rejects_route_for_a_different_native_dungeon(self):
        foreign_route = dict(self.route, definition_id=10)
        with self.assertRaisesRegex(ValueError, "contradicts native dungeon identity"):
            self.build(route=foreign_route)

    def test_rejects_foreign_family_species(self):
        rooms = [
            dict(order=1, monsters=[self.monster(999, levels=(10, 12))]),
            self.rooms[1],
        ]
        with self.assertRaisesRegex(ValueError, "not in its native pool"):
            self.build(rooms=rooms)

    def test_rejects_native_level_mismatch(self):
        rooms = [
            dict(order=1, monsters=[self.monster(101, levels=(9, 12))]),
            self.rooms[1],
        ]
        with self.assertRaisesRegex(ValueError, "contradicts native level bounds"):
            self.build(rooms=rooms)

    def test_rejects_boss_before_final_stage(self):
        rooms = [
            dict(order=1, monsters=[self.monster(103, role="boss")]),
            self.rooms[1],
        ]
        with self.assertRaisesRegex(ValueError, "final stage only"):
            self.build(rooms=rooms)

    def test_rejects_malformed_quantity_including_boolean(self):
        for count in (0, -1, True, 1.5):
            with self.subTest(count=count):
                rooms = [
                    dict(order=1, monsters=[self.monster(101, count=count)]),
                    self.rooms[1],
                ]
                with self.assertRaisesRegex(ValueError, "quantity must be positive"):
                    self.build(rooms=rooms)


if __name__ == "__main__":
    unittest.main()
