"""Habitat, terrain and bounded idempotence contracts for native flora genesis."""
import unittest
from unittest.mock import patch

from wakfu_server import ecology_flora_planner as subject


def definition(family, profession, ground=1):
    return {
        "family_id": family,
        "monster_resource": False,
        "ground": ground,
        "stage_definitions": [
            {
                "stage_id": 2,
                "actions": [{"profession_id": profession, "product_references": [10]}],
            },
            {
                "stage_id": 3,
                "actions": [
                    {"profession_id": profession, "product_references": [10]},
                    {"profession_id": profession, "product_references": [11]},
                ],
            },
        ],
    }


class FloraPlannerTests(unittest.TestCase):
    def setUp(self):
        subject._walkable.cache_clear()
        self.addCleanup(subject._walkable.cache_clear)
        self.resources = {
            10: definition(1, 71),
            20: definition(2, 72),
            30: definition(3, 64),
            40: definition(4, 73),
            60: definition(6, 75),
            50: dict(definition(5, 72), monster_resource=True),
        }
        self.patcher = patch.dict(subject.RESOURCES, self.resources, clear=True)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def prepared(self, count=12):
        return dict(
            map_id=1134,
            region_id=7,
            targets={1: 2, 2: 2, 3: 2},
            warnings=[],
            definitions={
                10: {"family_id": 1, "stage": 3},
                20: {"family_id": 2, "stage": 3},
                30: {"family_id": 3, "stage": 3},
            },
            cells=[(index, 0, 0, (10, 20, 30)) for index in range(count)],
        )

    def test_classification_covers_flora_but_excludes_monsters_minerals_and_fish(
        self,
    ):
        self.assertEqual(
            {reference for reference in self.resources if subject.is_flora(reference)},
            {10, 20, 30},
        )
        self.assertFalse(subject.is_flora(99999))

    def test_prepare_uses_only_native_families_walkable_suitable_surfaces_and_mature_stage(
        self,
    ):
        habitat = {
            "plant_capacity": 100,
            "native_spawn_definitions": [{"lVQ": [10, 20]}],
            "plant_families": [
                {"family_id": 1, "parameter_bKR": 3, "parameter_bKQ": 5}
            ],
        }
        surfaces = {
            (0, 0): [{"z": 0, "ground_id": 1, "region_id": 7}],
            (1, 0): [{"z": 0, "ground_id": 2, "region_id": 7}],
            (2, 0): [{"z": 0, "ground_id": 1, "region_id": 8}],
            (3, 0): [{"z": 0, "ground_id": 1, "region_id": 7}],
        }
        with patch.object(subject, "region", return_value=habitat), patch.object(
            subject, "cells", return_value=surfaces
        ), patch.object(
            subject,
            "map_geometry",
            return_value={"cells": [(0, 0, 0), (1, 0, 0), (2, 0, 0)]},
        ), patch.object(
            subject,
            "suitability",
            side_effect=lambda ground, _definition: int(ground == 1),
        ), patch.dict(
            subject.SEEDS,
            {1: {"resource_reference": 10}, 2: {"resource_reference": 20}},
            clear=True,
        ):
            prepared = subject.prepare(1134, 7)
        self.assertEqual(prepared["cells"], [(0, 0, 0, (10,))])
        self.assertEqual(prepared["definitions"], {10: {"family_id": 1, "stage": 3}})
        self.assertEqual(prepared["targets"], {1: 1})

    def test_family_targets_fill_once_respect_occupied_and_replenish_harvested_flora(
        self,
    ):
        prepared = self.prepared()
        first = subject.plan(prepared, [], {(0, 0), (1, 0)})
        self.assertEqual(len(first["rows"]), 6)
        self.assertTrue(
            all((row["x"], row["y"]) not in {(0, 0), (1, 0)} for row in first["rows"])
        )
        occupied = {(row["x"], row["y"]) for row in first["rows"]}
        second = subject.plan(prepared, first["rows"], occupied)
        self.assertEqual(second["rows"], [])
        harvested = first["rows"].pop()
        occupied.remove((harvested["x"], harvested["y"]))
        refill = subject.plan(prepared, first["rows"], occupied)
        self.assertEqual(len(refill["rows"]), 1)
        self.assertEqual(
            refill["rows"][0]["resource_reference"], harvested["resource_reference"]
        )

    def test_flora_outside_region_does_not_reduce_native_regional_target(self):
        existing = [
            dict(resource_reference=10, x=1000 + index, y=0) for index in range(900)
        ]
        result = subject.plan(self.prepared(), existing, set())
        self.assertEqual(len(result["rows"]), 6)
        self.assertEqual(result["warnings"], [])

    def prepare_terrain(self, count, capacity):
        subject._walkable.cache_clear()
        habitat = {
            "plant_capacity": capacity,
            "native_spawn_definitions": [{"lVQ": [10]}],
            "plant_families": [{"family_id": 1, "parameter_bKR": 1000}],
        }
        surfaces = {
            (index, 0): [{"z": 0, "ground_id": 1, "region_id": 7}]
            for index in range(count)
        }
        with patch.object(subject, "region", return_value=habitat), patch.object(
            subject, "cells", return_value=surfaces
        ), patch.object(
            subject,
            "map_geometry",
            return_value={"cells": [(index, 0, 0) for index in range(count)]},
        ), patch.object(
            subject, "suitability", return_value=1
        ), patch.dict(
            subject.SEEDS, {1: {"resource_reference": 10}}, clear=True
        ):
            return subject.prepare(1134, 7)

    def test_prepare_population_scales_with_suitable_terrain(self):
        for terrain, expected in ((1000, 20), (2000, 40)):
            with self.subTest(terrain=terrain):
                prepared = self.prepare_terrain(terrain, 10000)
                self.assertEqual(sum(prepared["targets"].values()), expected)

    def test_prepare_population_is_bounded_by_native_capacity(self):
        prepared = self.prepare_terrain(2000, 12)
        self.assertEqual(sum(prepared["targets"].values()), 12)

    def test_tiny_supported_habitat_still_gets_one_resource(self):
        prepared = self.prepare_terrain(10, 1000)
        self.assertEqual(sum(prepared["targets"].values()), 1)

    def test_apportioned_budget_preserves_supported_families_when_space_allows(self):
        habitat = {
            "plant_capacity": 10000,
            "native_spawn_definitions": [{"lVQ": [10, 20, 30]}],
            "plant_families": [
                {"family_id": family, "parameter_bKR": 1000} for family in (1, 2, 3)
            ],
        }
        surfaces = {
            (index, 0): [{"z": 0, "ground_id": 1, "region_id": 7}]
            for index in range(1000)
        }
        with patch.object(subject, "region", return_value=habitat), patch.object(
            subject, "cells", return_value=surfaces
        ), patch.object(
            subject,
            "map_geometry",
            return_value={"cells": [(index, 0, 0) for index in range(1000)]},
        ), patch.object(
            subject, "suitability", return_value=1
        ), patch.dict(
            subject.SEEDS,
            {
                reference: {"resource_reference": reference}
                for reference in (10, 20, 30)
            },
            clear=True,
        ):
            prepared = subject.prepare(1134, 7)
        self.assertEqual(set(prepared["targets"]), {1, 2, 3})
        self.assertTrue(all(target > 0 for target in prepared["targets"].values()))
        self.assertEqual(sum(prepared["targets"].values()), 20)

    def test_explicit_native_spawn_list_excludes_other_species_in_same_family(self):
        habitat = {
            "plant_capacity": 100,
            "plant_families": [{"family_id": 1, "parameter_bKR": 10}],
            "native_spawn_definitions": [{"lVQ": [10]}],
        }
        with patch.dict(subject.RESOURCES, {11: definition(1, 71)}), patch.object(
            subject, "region", return_value=habitat
        ), patch.object(
            subject,
            "cells",
            return_value={(0, 0): [{"z": 0, "ground_id": 1, "region_id": 7}]},
        ), patch.object(
            subject, "map_geometry", return_value={"cells": [(0, 0, 0)]}
        ), patch.object(
            subject, "suitability", return_value=1
        ), patch.dict(
            subject.SEEDS,
            {1: {"resource_reference": 10}, 2: {"resource_reference": 11}},
            clear=True,
        ):
            prepared = subject.prepare(1134, 7)
        self.assertEqual(set(prepared["definitions"]), {10})
        self.assertEqual(prepared["cells"], [(0, 0, 0, (10,))])
        self.assertEqual(
            {
                row["resource_reference"]
                for row in subject.plan(prepared, [], set())["rows"]
            },
            {10},
        )

    def test_missing_or_empty_native_species_list_generates_nothing_and_warns(self):
        for spawn_definitions in (None, [], [{"lVQ": []}]):
            with self.subTest(spawn_definitions=spawn_definitions):
                habitat = {
                    "plant_capacity": 100,
                    "plant_families": [{"family_id": 1, "parameter_bKR": 10}],
                }
                if spawn_definitions is not None:
                    habitat["native_spawn_definitions"] = spawn_definitions
                with patch.object(
                    subject, "region", return_value=habitat
                ), patch.object(
                    subject,
                    "cells",
                    side_effect=AssertionError(
                        "unsupported native species must fail closed"
                    ),
                ):
                    prepared = subject.prepare(1134, 7)
                self.assertEqual(prepared["definitions"], {})
                self.assertEqual(prepared["targets"], {})
                self.assertTrue(prepared["warnings"])
                self.assertEqual(subject.plan(prepared, [], set())["rows"], [])
