"""Portable station authority remains tied to ownership, placement and native data."""
import unittest
from types import SimpleNamespace

from wakfu_server.items.craft_station import resolve_haven_bag
from wakfu_server.items.crafting import _station


class HavenBagCraftStationTests(unittest.TestCase):
    def setUp(self):
        self.character = dict(
            id=42,
            map_id=9,
            instance_id=42,
            x=2,
            y=1,
            z=0,
            haven_bag=dict(
                rooms=[dict(index=0, enabled=True, primary_ref=4264)],
                furniture=[
                    dict(
                        template_id=3661,
                        deployed=True,
                        room=0,
                        x=1,
                        y=1,
                        z=0,
                        direction=0,
                    )
                ],
            ),
        )
        self.catalog = SimpleNamespace(
            definitions={
                113: dict(definition_id=113, profession_id=73, allowed_recipe_ids=[100])
            }
        )
        self.templates = {
            3661: dict(
                craft_definition_id=113, interaction_cells_by_direction=[[[1, 0, 0]]]
            )
        }

    def resolve(self):
        return resolve_haven_bag(self.character, 3661, self.catalog, self.templates)

    def test_owned_deployed_station_uses_native_definition_and_instance(self):
        station = self.resolve()
        self.assertEqual(station["instance_id"], 42)
        self.assertEqual(
            _station(self.catalog, self.character, 3661, station)["profession_id"], 73
        )

    def test_sibling_character_uses_shared_account_instance(self):
        self.character["haven_bag"]["owner_id"] = 41
        self.character["instance_id"] = 41
        self.assertEqual(self.resolve()["instance_id"], 41)

    def test_guest_uses_visited_station_without_becoming_layout_owner(self):
        self.character["haven_bag"]["owner_id"] = 77
        self.character.update(instance_id=77, haven_bag_visitor=True)
        station = self.resolve()
        self.assertEqual(station["instance_id"], 77)
        self.assertEqual(self.character["id"], 42)
        self.assertEqual(
            _station(self.catalog, self.character, 3661, station)["profession_id"], 73
        )

    def test_portable_station_works_in_any_installed_room_type(self):
        for gem in (4262, 4263, 4264, 4266):
            self.character["haven_bag"]["rooms"][0]["primary_ref"] = gem
            with self.subTest(gem=gem):
                self.assertTrue(self.resolve()["in_range"])

    def test_cannot_craft_outside_native_interaction_cell(self):
        self.character["x"] = 3
        with self.assertRaisesRegex(ValueError, "not reachable"):
            self.resolve()

    def test_removal_room_change_or_foreign_instance_revokes_station(self):
        for mutation in ("undeploy", "room", "instance"):
            self.setUp()
            if mutation == "undeploy":
                self.character["haven_bag"]["furniture"][0]["deployed"] = False
            elif mutation == "room":
                self.character["haven_bag"]["rooms"][0]["primary_ref"] = -1
            else:
                self.character["instance_id"] = 43
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.resolve()

    def test_unknown_definition_and_missing_topology_are_denied(self):
        self.templates[3661]["craft_definition_id"] = 999
        with self.assertRaises(ValueError):
            self.resolve()
        self.setUp()
        self.templates[3661]["interaction_cells_by_direction"] = []
        with self.assertRaisesRegex(ValueError, "topology"):
            self.resolve()
