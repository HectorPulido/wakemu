"""Private ranch gardens retain native geometry and actor-owned inventory."""
import unittest
from unittest.mock import MagicMock, patch


class HavenRanchGardenTests(unittest.TestCase):
    def test_private_ranch_flora_actions_never_change_personal_affinity(self):
        from wakfu_server import flora_ecology

        db = MagicMock()
        resource = {"map_id": 1440, "instance_id": 77, "resource_reference": 1}
        with patch.object(flora_ecology, "is_fish", return_value=False), patch.object(
            flora_ecology, "is_mineral", return_value=False
        ), patch.object(flora_ecology, "apply") as affinity:
            for action in ("plant", "remove", "harvest"):
                result = flora_ecology.change(
                    db, 12, resource, operation="garden", action=action
                )
                self.assertEqual(result["packets"], [])
        affinity.assert_not_called()
        db.execute.assert_not_called()

    def setUp(self):
        self.character = dict(
            id=12,
            account_id=4,
            map_id=1440,
            instance_id=77,
            x=28,
            y=6,
            z=4,
            inventory_items=[{"uid": 9}],
            haven_bag={"owner_id": 77},
            haven_ranch_session=True,
        )
        self.store = MagicMock()

    def test_only_authoritative_positive_private_ranch_is_a_garden(self):
        from wakfu_server import haven_bag_garden as garden

        self.assertTrue(garden.is_private_garden(self.character))
        for changed in (
            {"instance_id": 0},
            {"instance_id": True},
            {"instance_id": 78},
            {"map_id": 1466},
            {"haven_bag": {}},
            {"haven_ranch_session": False},
        ):
            self.assertFalse(garden.is_private_garden(dict(self.character, **changed)))

    def test_owner_and_visitor_keep_their_own_durable_inventory(self):
        from wakfu_server import haven_bag_garden as garden

        for visitor in (False, True):
            stored = dict(self.character, map_id=1134, instance_id=0)
            live = dict(
                self.character,
                inventory_items=[{"uid": 999}],
                haven_bag_visitor=visitor,
            )
            with patch.object(garden, "_load_owner_bag", return_value={"owner_id": 77}):
                current = garden.active_character(stored, [live], store=self.store)
            self.assertEqual(current["inventory_items"], [{"uid": 9}])
            self.assertEqual((current["id"], current["account_id"]), (12, 4))
            self.assertEqual(current["instance_id"], 77)

    def test_scalar_worker_snapshot_resolves_host_bag_without_replacing_visitor_items(
        self,
    ):
        from wakfu_server import haven_bag_garden as garden

        live = {
            key: self.character[key]
            for key in ("id", "account_id", "map_id", "instance_id", "x", "y", "z")
        }
        stored = dict(
            self.character, map_id=1134, instance_id=0, haven_bag={"owner_id": 12}
        )
        with patch.object(
            garden, "_load_owner_bag", return_value={"owner_id": 77}
        ) as load:
            current = garden.active_character(stored, [live], store=self.store)
        load.assert_called_once_with(self.store, 77)
        self.assertEqual(current["inventory_items"], [{"uid": 9}])
        self.assertEqual(current["haven_bag"]["owner_id"], 77)

    def test_stale_host_configuration_or_foreign_account_is_rejected(self):
        from wakfu_server import haven_bag_garden as garden

        with patch.object(garden, "_load_owner_bag", return_value={"owner_id": 78}):
            with self.assertRaises(ValueError):
                garden.active_character(
                    self.character, [self.character], store=self.store
                )
        with self.assertRaises(ValueError):
            garden.active_character(
                self.character, [dict(self.character, account_id=999)]
            )

    def test_native_height_is_unique_and_unknown_or_ambiguous_height_is_rejected(self):
        from wakfu_server import haven_bag_garden as garden

        with patch(
            "wakfu_server.planting_cells.private_surfaces", return_value=[{"z": 4}]
        ):
            self.assertEqual(garden.validate_target(self.character, 29, 6), 4)
            with self.assertRaises(ValueError):
                garden.validate_target(self.character, 29, 6, z=0)
        for candidates in ([], [{"z": 4}, {"z": 8}]):
            with patch(
                "wakfu_server.planting_cells.private_surfaces", return_value=candidates
            ):
                with self.assertRaises(ValueError):
                    garden.validate_target(self.character, 29, 6)

    def test_reachability_uses_native_edge_including_actual_height(self):
        from wakfu_server import haven_bag_garden as garden

        target = {"x": 29, "y": 6, "z": 5}
        with patch(
            "wakfu_server.planting_cells.private_surfaces", return_value=[{"z": 5}]
        ), patch(
            "wakfu_server.combat_terrain.map_geometry",
            return_value={"edges": [((28, 6, 4), (29, 6, 5))]},
        ):
            self.assertTrue(garden.reachable(self.character, target))
            self.assertFalse(garden.reachable(dict(self.character, z=0), target))

    def test_ranch_authorization_accepts_monster_seeds_with_same_native_fences(self):
        from wakfu_server import haven_bag_garden as garden

        request = {"x": 29, "y": 6}
        with patch.object(garden, "validate_target", return_value=5), patch.object(
            garden, "reachable", return_value=True
        ), patch(
            "wakfu_server.planting_cells.assert_private_cell_unoccupied"
        ) as occupancy:
            for monster in (False, True):
                self.assertEqual(
                    garden.authorize(
                        self.store,
                        self.character,
                        request,
                        {},
                        {"monster_resource": monster},
                    ),
                    5,
                )
            self.assertEqual(occupancy.call_count, 2)
        with self.assertRaises(ValueError):
            garden.authorize(
                self.store,
                dict(self.character, map_id=9),
                request,
                {},
                {"monster_resource": True},
            )
        with self.assertRaises(ValueError):
            garden.validate_target(dict(self.character, instance_id=0), 29, 6)

    def test_private_surfaces_intersect_exact_native_walkable_height(self):
        from wakfu_server import planting_cells

        surfaces = {
            (29, 6): [
                dict(z=4, ground_id=0, region_id=-1),
                dict(z=8, ground_id=0, region_id=-1),
            ],
            (30, 6): [dict(z=4, ground_id=0, region_id=-1)],
        }
        planting_cells._ranch_cells.cache_clear()
        self.addCleanup(planting_cells._ranch_cells.cache_clear)
        with patch.object(planting_cells, "cells", return_value=surfaces), patch(
            "wakfu_server.combat_terrain.map_geometry",
            return_value={"cells": [(29, 6, 4)]},
        ):
            self.assertEqual(
                [cell["z"] for cell in planting_cells.private_surfaces(1440, 29, 6)],
                [4],
            )
            with self.assertRaises(ValueError):
                planting_cells.private_surfaces(1440, 30, 6)

    def test_private_ranch_uses_world_policy_for_flora_and_monsters(self):
        from wakfu_server import haven_bag_garden as garden, planting_probability

        prepared = dict(
            character=self.character,
            request={"x": 29, "y": 6},
            z=4,
            definition={
                "monster_resource": False,
                "resource_reference": 999,
                "family_id": 19,
            },
        )
        self.store.connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = {
            "value": 0.01
        }
        resolve = planting_probability.resolver(
            self.store, profession_bonus=lambda _: 0, open_test_policy=True
        )
        with patch.object(garden, "validate_target", return_value=4):
            for monster in (False, True):
                self.assertEqual(
                    resolve(
                        dict(
                            prepared,
                            definition=dict(
                                prepared["definition"], monster_resource=monster
                            ),
                        )
                    ),
                    0.01,
                )
            with self.assertRaises(ValueError):
                resolve(dict(prepared, character=dict(self.character, instance_id=0)))

    def test_closed_ranch_probability_retains_native_surface_resolver(self):
        from wakfu_server import haven_bag_garden as garden, planting_probability

        prepared = dict(
            character=self.character,
            request={"x": 29, "y": 6},
            z=4,
            definition={"monster_resource": True},
        )
        resolve = planting_probability.resolver(
            self.store, profession_bonus=lambda _: 2
        )
        with patch.object(garden, "validate_target", return_value=4), patch(
            "wakfu_server.territory_weather.context", return_value={"weather": "ABSENT"}
        ), patch.object(
            planting_probability, "for_cell", return_value={"probability": 0.6}
        ) as native:
            self.assertEqual(resolve(prepared), 0.6)
            native.assert_called_once_with(
                self.character,
                prepared["request"],
                prepared["definition"],
                z=4,
                weather="ABSENT",
                profession_bonus_percent=2,
            )

    def test_furniture_fence_locks_host_before_checking_guest_target(self):
        from wakfu_server.planting_cells import assert_private_furniture_unoccupied

        db = MagicMock()
        db.execute.return_value.fetchone.side_effect = [{"character_id": 77}, None]
        visitor = dict(self.character, haven_bag_visitor=True)
        assert_private_furniture_unoccupied(
            db, visitor, {"x": 29, "y": 6}, lock_owner=True
        )
        self.assertEqual(
            db.execute.call_args_list[0].args,
            (
                "SELECT character_id FROM haven_bags WHERE character_id=%s FOR UPDATE",
                (77,),
            ),
        )
        self.assertEqual(db.execute.call_args_list[1].args[1], (77, 29, 6))

    def test_furniture_collision_and_removed_host_reject_plant_commit(self):
        from wakfu_server.planting_cells import assert_private_furniture_unoccupied

        for rows, reason in (
            ([{"character_id": 77}, {"occupied": 1}], "furniture"),
            ([None], "host no longer exists"),
        ):
            db = MagicMock()
            db.execute.return_value.fetchone.side_effect = rows
            with self.assertRaisesRegex(ValueError, reason):
                assert_private_furniture_unoccupied(
                    db, self.character, {"x": 29, "y": 6}, lock_owner=True
                )
