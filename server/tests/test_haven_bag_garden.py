"""Private garden admission and authoritative interior isolation."""
import unittest
from unittest.mock import MagicMock

from wakfu_server.haven_bag_garden import (
    active_character,
    authorize,
    reachable,
    room_at,
)


class HavenBagGardenTests(unittest.TestCase):
    def setUp(self):
        self.character = dict(
            id=12,
            account_id=4,
            map_id=9,
            instance_id=12,
            x=6,
            y=7,
            z=0,
            inventory_items=[{"uid": 9}],
            haven_bag={
                "rooms": [{"index": 4, "enabled": True, "primary_ref": 4266}],
                "furniture": [],
            },
        )
        self.request = {"x": 7, "y": 7}
        self.store = MagicMock()
        self.store.connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = (
            None
        )

    def test_own_live_location_preserves_durable_inventory(self):
        stored = dict(self.character, map_id=1134, instance_id=0, x=51, y=8)
        live = dict(self.character, inventory_items=[])
        result = active_character(stored, [live])
        self.assertEqual(result["map_id"], 9)
        self.assertEqual(result["inventory_items"], stored["inventory_items"])

    def test_foreign_interior_rejected(self):
        with self.assertRaises(ValueError):
            active_character(self.character, [dict(self.character, instance_id=77)])

    def test_leaving_interior_restores_durable_location(self):
        stored = dict(self.character, map_id=1134, instance_id=0)
        self.assertIs(active_character(stored, []), stored)
        self.assertIs(active_character(stored, [stored]), stored)

    def test_installed_garden_admits_adjacent_flora(self):
        self.assertEqual(
            authorize(
                self.store,
                self.character,
                self.request,
                {},
                {"monster_resource": False},
            ),
            0,
        )
        self.assertTrue(reachable(self.character, dict(self.request, z=0)))

    def test_monster_seed_and_non_garden_room_rejected(self):
        with self.assertRaises(ValueError):
            authorize(
                self.store, self.character, self.request, {}, {"monster_resource": True}
            )
        with self.assertRaises(ValueError):
            room_at(self.character, 3, 3)

    def test_far_or_wrong_height_rejected(self):
        self.assertFalse(reachable(self.character, {"x": 10, "y": 7, "z": 0}))
        self.assertFalse(reachable(self.character, {"x": 7, "y": 7, "z": 1}))

    def test_disabled_room_or_outside_coordinates_rejected(self):
        self.character["haven_bag"]["rooms"][0]["enabled"] = False
        with self.assertRaises(ValueError):
            room_at(self.character, 7, 7)
        for x, y in ((-1, 7), (18, 7), (7, 18), (True, 7)):
            with self.assertRaises(ValueError):
                room_at(self.character, x, y)

    def test_furniture_and_existing_plant_block_cell(self):
        self.character["haven_bag"]["furniture"] = [{"deployed": True, "x": 7, "y": 7}]
        with self.assertRaises(ValueError):
            authorize(
                self.store,
                self.character,
                self.request,
                {},
                {"monster_resource": False},
            )
        self.character["haven_bag"]["furniture"] = []
        self.store.connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = {
            "exists": True
        }
        with self.assertRaises(ValueError):
            authorize(
                self.store,
                self.character,
                self.request,
                {},
                {"monster_resource": False},
            )


if __name__ == "__main__":
    unittest.main()
