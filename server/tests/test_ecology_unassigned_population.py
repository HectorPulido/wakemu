"""Explicit unassigned native terrain must not suppress another ecosystem UI."""
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server import (
    ecology_context,
    ecology_population,
    territory_bonuses,
    territory_bonus_updates,
)


class EcologyUnassignedPopulationTests(unittest.TestCase):
    def population(self, locate, **options):
        class DB:
            def execute(self, sql, parameters):
                return [
                    {
                        "members": [
                            dict(id=-7, ref=6, x=-163, y=-125, z=-4),
                            dict(id=-8, ref=6, x=1, y=2, z=3),
                        ]
                    }
                ]

        with patch.object(
            ecology_population, "reference", return_value={"family_id": 9}
        ):
            return ecology_population.snapshot(
                DB(), 527, 0, kinds=("monster",), locate=locate, **options
            )

    def test_strict_default_still_incomplete_but_opt_in_excludes_only_minus_one(self):
        locate = lambda m, x, y, z: {"region_id": -1 if x == -163 else 7}
        self.assertFalse(self.population(locate)["complete"])
        result = self.population(locate, exclude_unassigned=True)
        self.assertTrue(result["complete"])
        self.assertEqual(result["regions"][7]["monster"], {9: 1})
        for unknown in (0, -2, None, False):
            with self.subTest(unknown=unknown):
                result = self.population(
                    lambda *args: {"region_id": unknown}, exclude_unassigned=True
                )
                self.assertFalse(result["complete"])
                self.assertEqual(len(result["unresolved"]), 2)
        with self.assertRaises(ValueError):
            self.population(locate, exclude_unassigned=1)

    def test_exact_surface_sentinel_required_grid_hole_never_implies_unassigned(self):
        with patch.object(
            ecology_context.territory_cells,
            "region_at",
            side_effect=ValueError("unknown"),
        ):
            with patch.object(
                ecology_context.planting_cells,
                "surface",
                return_value={"region_id": -1, "ground_id": 0},
            ) as surface:
                self.assertEqual(
                    ecology_context.population_region(527, -163, -125, -4),
                    {"region_id": -1},
                )
                surface.assert_called_once_with(527, -163, -125, -4)
            for value in ({"region_id": 7}, {"region_id": 0}, {"region_id": None}, {}):
                with patch.object(
                    ecology_context.planting_cells, "surface", return_value=value
                ), self.assertRaises(ValueError):
                    ecology_context.population_region(527, -163, -125, -4)
            with patch.object(
                ecology_context.planting_cells,
                "surface",
                side_effect=ValueError("unknown height"),
            ), self.assertRaises(ValueError):
                ecology_context.population_region(527, -163, -125, -5)

    def test_known_regional_grid_does_not_require_plantable_height(self):
        with patch.object(
            ecology_context.territory_cells, "region_at", return_value=7
        ), patch.object(
            ecology_context.planting_cells,
            "surface",
            side_effect=AssertionError("unneeded"),
        ):
            self.assertEqual(
                ecology_context.population_region(527, 1, 2, 300), {"region_id": 7}
            )

    def test_certified_unassigned_tofu_preserves_other_region_counts(self):
        def region(map_id, x, y):
            if x == -163:
                raise ValueError("outside native ecosystem territories")
            return 7

        with patch.object(
            ecology_context.territory_cells, "region_at", side_effect=region
        ), patch.object(
            ecology_context.planting_cells, "surface", return_value={"region_id": -1}
        ) as surface:
            result = self.population(
                ecology_context.population_region, exclude_unassigned=True
            )
        self.assertTrue(result["complete"])
        self.assertEqual(result["unresolved"], [])
        self.assertEqual(result["regions"], {7: {"plant": {}, "monster": {9: 1}}})
        surface.assert_called_once_with(527, -163, -125, -4)

    def test_unknown_tofu_height_keeps_other_counts_but_snapshot_incomplete(self):
        def region(map_id, x, y):
            if x == -163:
                raise ValueError("outside native ecosystem territories")
            return 7

        with patch.object(
            ecology_context.territory_cells, "region_at", side_effect=region
        ), patch.object(
            ecology_context.planting_cells,
            "surface",
            side_effect=ValueError("unknown native height"),
        ):
            result = self.population(
                ecology_context.population_region, exclude_unassigned=True
            )
        self.assertFalse(result["complete"])
        self.assertEqual(result["unresolved"], [("monster", -7)])
        self.assertEqual(result["regions"][7]["monster"], {9: 1})

    def test_bonus_consumers_ignore_only_certified_unassigned_monsters(self):
        class DB:
            def execute(self, sql, parameters):
                if "planted_resources" in sql:
                    return []
                return [
                    {
                        "members": [
                            dict(id=-7, ref=6, x=-163, y=-125, z=-4),
                            dict(id=-8, ref=6, x=1, y=2, z=3),
                        ]
                    }
                ]

        def region(map_id, x, y):
            if x == -163:
                raise ValueError("outside native ecosystem territories")
            return 7

        store = SimpleNamespace(connection=lambda: nullcontext(DB()))
        character = dict(map_id=527, instance_id=0, x=1, y=2, z=3)
        with patch.object(
            ecology_context.territory_cells, "region_at", side_effect=region
        ), patch.object(
            ecology_population, "reference", return_value={"family_id": 81}
        ), patch.object(
            territory_bonuses, "evaluate_population", return_value={"verified": True}
        ) as evaluate, patch.object(
            territory_bonus_updates, "_revision", return_value=0
        ), patch.object(
            territory_bonuses,
            "_catalog",
            return_value={"territories": {"7": {"map_id": 527}}},
        ), patch.object(
            territory_bonuses,
            "stat_bonuses",
            side_effect=lambda value: {33: 30} if value else {},
        ):
            with patch.object(
                ecology_context.planting_cells,
                "surface",
                return_value={"region_id": -1},
            ):
                self.assertEqual(
                    territory_bonuses.current_region(DB(), character),
                    {"verified": True},
                )
                evaluate.assert_called_once_with(7, {81: 1}, {})
                evaluate.reset_mock()
                proposals = territory_bonus_updates.prepare(
                    store, dict(world_epoch="epoch", players=[character])
                )
                self.assertEqual(proposals[0]["regions"], {"7": {"33": 30}})
                evaluate.assert_called_once_with(7, {81: 1}, {})
            evaluate.reset_mock()
            with patch.object(
                ecology_context.planting_cells,
                "surface",
                side_effect=ValueError("unknown native height"),
            ):
                self.assertIsNone(territory_bonuses.current_region(DB(), character))
                proposals = territory_bonus_updates.prepare(
                    store, dict(world_epoch="epoch", players=[character])
                )
                self.assertEqual(proposals[0]["regions"], {"7": {}})
                evaluate.assert_not_called()

    def test_packet_uses_certified_exclusion_and_unknown_still_blocks_entire_packet(
        self,
    ):
        class DB:
            def execute(self, sql, parameters):
                if "planted_resources" in sql:
                    return []
                return [
                    {
                        "members": [
                            dict(id=-1125899907399040, ref=6, x=-163, y=-125, z=-4)
                        ]
                    }
                ]

        store = SimpleNamespace(connection=lambda: nullcontext(DB()))
        character = dict(map_id=527, instance_id=0, x=1, y=2, z=3)

        def region(m, x, y):
            if x == 1:
                return 7
            raise ValueError("unknown grid")

        with patch.object(
            ecology_context.territory_cells, "region_at", side_effect=region
        ), patch.object(
            ecology_population, "reference", return_value={"family_id": 9}
        ), patch.object(
            ecology_context.planting_cells,
            "region_context",
            return_value=(12789, b"valid"),
        ) as encode:
            with patch.object(
                ecology_context.planting_cells,
                "surface",
                return_value={"region_id": -1, "ground_id": 0},
            ):
                self.assertEqual(
                    ecology_context.packet(store, character), (12789, b"valid")
                )
                self.assertEqual(encode.call_args.kwargs["monster_counts"], {})
            encode.reset_mock()
            with patch.object(
                ecology_context.planting_cells,
                "surface",
                side_effect=ValueError("missing geometry"),
            ), self.assertRaisesRegex(ValueError, "incomplete"):
                ecology_context.packet(store, character)
            encode.assert_not_called()
