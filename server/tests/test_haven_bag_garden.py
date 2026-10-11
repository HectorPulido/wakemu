"""Private garden admission and authoritative interior isolation."""
import unittest
from unittest.mock import MagicMock, patch

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

    def test_guest_uses_visited_layout_but_retains_own_items_and_identity(self):
        stored = dict(self.character, map_id=1134, instance_id=0)
        visited = dict(self.character["haven_bag"], owner_id=77)
        live = dict(
            self.character,
            instance_id=77,
            haven_bag=visited,
            haven_bag_visitor=True,
            inventory_items=[{"uid": 999}],
        )
        current = active_character(stored, [live])
        self.assertEqual((current["id"], current["account_id"]), (12, 4))
        self.assertEqual(current["inventory_items"], [{"uid": 9}])
        self.assertEqual(current["instance_id"], 77)
        self.assertEqual(room_at(current, 7, 7)["index"], 4)
        self.assertEqual(
            authorize(
                self.store, current, self.request, {}, {"monster_resource": False}
            ),
            0,
        )
        db = self.store.connection.return_value.__enter__.return_value
        self.assertEqual(db.execute.call_args.args[1], (9, 77, 7, 7))

    def test_guest_cannot_substitute_another_accounts_live_identity(self):
        live = dict(self.character, account_id=999)
        with self.assertRaisesRegex(ValueError, "account"):
            active_character(self.character, [live])

    def test_scalar_ecology_guest_resolves_visited_layout_from_instance(self):
        live = {
            key: self.character[key]
            for key in ("id", "account_id", "map_id", "instance_id", "x", "y", "z")
        }
        live["instance_id"] = 77
        layout = dict(self.character["haven_bag"], owner_id=77)
        with patch("wakfu_server.haven_bag_store.load", return_value=layout) as load:
            current = active_character(self.character, [live], store=self.store)
        self.assertEqual(load.call_args.args[1], 77)
        self.assertEqual(current["inventory_items"], self.character["inventory_items"])
        self.assertEqual(room_at(current, 7, 7)["index"], 4)

    def test_scalar_owner_snapshot_uses_durable_own_layout(self):
        live = {
            key: self.character[key]
            for key in ("id", "account_id", "map_id", "instance_id", "x", "y", "z")
        }
        current = active_character(self.character, [live])
        self.assertEqual(room_at(current, 7, 7)["index"], 4)

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
