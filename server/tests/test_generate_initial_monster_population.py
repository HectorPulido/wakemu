import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# The generator is also a directly executable script and intentionally imports
# its sibling planner as a top-level module.
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
from tools import generate_initial_monster_population as generator


class InitialMonsterPopulationGeneratorTests(unittest.TestCase):
    def test_regular_candidates_require_native_family_regular_flags_and_mobile_stats(
        self,
    ):
        growth = {
            "families": [
                {
                    "family_id": 1,
                    "tiers": [
                        {
                            "candidates": [
                                {
                                    "reference": 10,
                                    "boss_classification": "regular",
                                    "world_properties": [],
                                },
                                {
                                    "reference": 11,
                                    "boss_classification": "boss",
                                    "world_properties": [],
                                },
                                {
                                    "reference": 12,
                                    "boss_classification": "regular",
                                    "world_properties": [43],
                                },
                                {
                                    "reference": 13,
                                    "boss_classification": "regular",
                                    "world_properties": [],
                                },
                                {
                                    "reference": 14,
                                    "boss_classification": "regular",
                                    "world_properties": [],
                                },
                            ]
                        },
                        {
                            "candidates": [
                                {
                                    "reference": 10,
                                    "boss_classification": "regular",
                                    "world_properties": [],
                                }
                            ]
                        },
                    ],
                },
                {
                    "family_id": 2,
                    "tiers": [
                        {
                            "candidates": [
                                {
                                    "reference": 20,
                                    "boss_classification": "regular",
                                    "world_properties": [],
                                }
                            ]
                        }
                    ],
                },
            ]
        }
        reference_rows = {
            ref: {"family_id": family, "min_level": 3}
            for ref, family in ((10, 1), (11, 1), (12, 1), (13, 1), (14, 1), (20, 2))
        }
        stat_rows = {
            10: {"HP": 10, "MP": 1},
            13: {"HP": 0, "MP": 1},
            14: {"HP": 10, "MP": 0},
        }
        with patch.object(
            generator, "reference", side_effect=reference_rows.__getitem__
        ), patch.object(
            generator, "statistics", side_effect=lambda ref, _level: stat_rows[ref]
        ):
            self.assertEqual(
                generator.regular_candidates(
                    {"monster_families": [{"family_id": 1}]}, growth
                ),
                [(3, 10)],
            )

    def test_generation_preserves_existing_and_reports_skips_exclusions_and_reserved_cells(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "monster-growth-catalog.json").write_text("{}")
            (root / "native-map-objects.json").write_text(
                json.dumps(
                    [
                        {"map_id": 42, "type": "Zaap", "x": 0.0, "y": 0.0},
                        {"map_id": 42, "type": "Decoration", "x": 20.0, "y": 0.0},
                    ]
                )
            )
            (root / "native-generic-teleporters.json").write_text("[]")
            (root / "native-transport-objects.json").write_text(
                json.dumps(
                    [
                        {"map_id": 42, "type": "Boat", "x": 30.0, "y": 0.0},
                    ]
                )
            )

            old = {
                "map_id": 42,
                "instance_id": 0,
                "region_id": 100,
                "members": [{"reference": 10, "level": 3, "x": 10, "y": 0, "z": 0}],
            }
            regions = {
                (42, region): {
                    "monster_capacity": 8,
                    "monster_families": [{"family_id": 1}],
                }
                for region in (100, 101, 102)
            }
            regions[(43, 103)] = {
                "monster_capacity": 8,
                "monster_families": [{"family_id": 1}],
            }
            regions[(44, 104)] = {
                "monster_capacity": 8,
                "monster_families": [{"family_id": 1}],
            }
            geometry_calls = []
            captured = {}

            def geometry(map_id):
                geometry_calls.append(map_id)
                if map_id == 43:
                    raise ValueError("missing geometry")
                return {
                    "map_id": map_id,
                    "cells": [(x, 0, 0) for x in (0, 4, 5, 10, 20, 30)],
                    "edges": [],
                }

            def propose(
                map_id, region_id, ref, level, *, excluded, geometry, minimum_component
            ):
                captured[region_id] = set(excluded)
                self.assertEqual((ref, level, minimum_component), (10, 3, 24))
                if region_id == 102:
                    raise ValueError("no component of at least24 cells")
                return {
                    "map_id": map_id,
                    "instance_id": 0,
                    "region_id": region_id,
                    "members": [
                        {"reference": ref, "level": level, "x": 1, "y": 1, "z": 0},
                        {"reference": ref, "level": level, "x": 2, "y": 1, "z": 0},
                    ],
                }

            with patch.object(generator, "DATA_ROOT", root), patch.object(
                generator, "REGIONS", regions
            ), patch.object(
                generator, "map_geometry", side_effect=geometry
            ), patch.object(
                generator, "regular_candidates", return_value=[(3, 10)]
            ), patch.object(
                generator, "candidate", side_effect=propose
            ):
                catalog, outcomes = generator.generate(
                    {"plans": [old]},
                    excluded_maps=(44,),
                    occupancy={"42": [[5, 0, 0]]},
                )

            self.assertEqual(catalog["plans"][0], old)
            self.assertEqual([p["region_id"] for p in catalog["plans"]], [100, 101])
            self.assertEqual(
                [(r["region_id"], r["status"]) for r in outcomes],
                [
                    (100, "preserved"),
                    (101, "generated"),
                    (102, "skipped"),
                    (103, "skipped"),
                    (104, "excluded"),
                ],
            )
            # Zaap exclusion uses Manhattan radius4. Existing plan and explicit
            # occupied cells are also reserved; arbitrary decoration is not.
            self.assertTrue(
                {(0, 0, 0), (4, 0, 0), (5, 0, 0), (10, 0, 0)} <= captured[101]
            )
            self.assertNotIn((20, 0, 0), captured[101])
            self.assertEqual(geometry_calls, [42, 43])


if __name__ == "__main__":
    unittest.main()
