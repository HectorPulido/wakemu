import unittest
from unittest.mock import patch

from wakfu_server.planting_probability import (
    RESOURCE_CLIMATES,
    calculate,
    for_cell,
    succeeds,
)
from wakfu_server import native_catalog


class PlantingProbabilityTests(unittest.TestCase):
    def test_climate_metadata_covers_every_catalog_resource(self):
        import json
        from pathlib import Path

        from wakfu_server.paths import DATA_ROOT

        resources = json.loads(
            native_catalog.read_text(DATA_ROOT / "plant-resources.json")
        )
        climates = json.loads(
            native_catalog.read_text(DATA_ROOT / "resource-climates.json")
        )
        resource_refs = [row["resource_reference"] for row in resources]
        climate_refs = [row["resource_reference"] for row in climates]
        self.assertEqual(len(resource_refs), 533)
        self.assertEqual(len(set(resource_refs)), len(resource_refs))
        self.assertEqual(set(climate_refs), set(resource_refs))
        self.assertEqual(len(RESOURCE_CLIMATES), 533)
        self.assertEqual(
            {row["climate"] for row in climates},
            {"NONE", "SUNNY", "LIGHT", "HEAVY"},
        )
        # Keep the metadata artifact synchronized with the normalized server
        # catalog without importing it into runtime policy.
        probe = (
            Path(__file__).resolve().parents[2]
            / "docs"
            / "soluciones-wakemu"
            / "04-probabilidad-de-plantacion"
            / "probe-climas-recursos.json"
        )
        if probe.exists():
            probe_rows = json.loads(native_catalog.read_text(probe))["records"]
            self.assertEqual(
                {row["resource_reference"] for row in probe_rows},
                set(resource_refs),
            )

    def test_for_cell_uses_native_climate_classes_and_compatible_weather(self):
        from wakfu_server import planting_cells

        surfaces = {(4, 9): [dict(z=2, ground_id=515, region_id=7001)]}
        ground = {"ground_id": 515, "resources": {}, "families": {"19": 100}}
        cases = (
            # The references resolve to native HEAVY, LIGHT, SUNNY and NONE.
            (76, "STORM", 1.0),
            (76, "LIGHT", 0.8),
            (60, "LIGHT", 1.0),
            (15, "LIGHT", 0.8),
            (37, "HEAVY", 1.0),
            (15, "ABSENT", 1.0),
        )
        with patch(
            "wakfu_server.planting_cells.cells", return_value=surfaces
        ), patch.dict(planting_cells.GROUNDS, {515: ground}, clear=True):
            for reference, weather, expected in cases:
                with self.subTest(reference=reference, weather=weather):
                    result = for_cell(
                        {"map_id": 999},
                        {"x": 4, "y": 9},
                        {"resource_reference": reference, "family_id": 19},
                        z=2,
                        weather=weather,
                        profession_bonus_percent=0,
                    )
                    self.assertEqual(result["probability"], expected)
                    self.assertEqual(result["displayed_percent"], round(expected * 100))
                    self.assertEqual(
                        (result["ground_id"], result["region_id"]), (515, 7001)
                    )

    def test_for_cell_prefers_explicit_resource_zero_to_family_fallback(self):
        from wakfu_server import planting_cells

        surfaces = {(4, 9): [dict(z=2, ground_id=515, region_id=7001)]}
        resource = {"resource_reference": 60, "family_id": 19}
        with patch("wakfu_server.planting_cells.cells", return_value=surfaces):
            with patch.dict(
                planting_cells.GROUNDS,
                {
                    515: {
                        "ground_id": 515,
                        "resources": {"60": 0},
                        "families": {"19": 100},
                    }
                },
                clear=True,
            ):
                explicit_zero = for_cell(
                    {"map_id": 999},
                    {"x": 4, "y": 9},
                    resource,
                    z=2,
                    weather="LIGHT",
                    profession_bonus_percent=0,
                )
            with patch.dict(
                planting_cells.GROUNDS,
                {
                    515: {
                        "ground_id": 515,
                        "resources": {},
                        "families": {"19": 70},
                    }
                },
                clear=True,
            ):
                family_fallback = for_cell(
                    {"map_id": 999},
                    {"x": 4, "y": 9},
                    resource,
                    z=2,
                    weather="LIGHT",
                    profession_bonus_percent=0,
                )
        self.assertEqual(explicit_zero["displayed_percent"], -1)
        self.assertEqual(explicit_zero["probability"], 0)
        self.assertEqual(family_fallback["probability"], 0.7)

    def test_for_cell_requires_one_exact_height_and_known_context(self):
        from wakfu_server import planting_cells

        resource = {"resource_reference": 60, "family_id": 19}
        character = {"map_id": 999}
        request = {"x": 4, "y": 9}
        ground = {515: {"ground_id": 515, "resources": {}, "families": {"19": 100}}}

        def evaluate(surfaces, *, z=2, weather="LIGHT", grounds=ground, ref=60):
            with patch(
                "wakfu_server.planting_cells.cells", return_value=surfaces
            ), patch.dict(planting_cells.GROUNDS, grounds, clear=True):
                return for_cell(
                    character,
                    request,
                    {"resource_reference": ref, "family_id": 19},
                    z=z,
                    weather=weather,
                    profession_bonus_percent=0,
                )

        base = {
            (4, 9): [
                dict(z=1, ground_id=514, region_id=7000),
                dict(z=2, ground_id=515, region_id=7001),
            ]
        }
        self.assertEqual(evaluate(base)["ground_id"], 515)
        with self.assertRaisesRegex(ValueError, "surface"):
            evaluate(base, z=3)
        ambiguous = {
            (4, 9): [
                dict(z=2, ground_id=515, region_id=7001),
                dict(z=2, ground_id=515, region_id=7001),
            ]
        }
        with self.assertRaisesRegex(ValueError, "surface"):
            evaluate(ambiguous)
        with self.assertRaisesRegex(ValueError, "weather"):
            evaluate(base, weather="UNKNOWN")
        with self.assertRaisesRegex(ValueError, "context"):
            evaluate(base, grounds={})
        with self.assertRaisesRegex(ValueError, "context"):
            evaluate(base, ref=-1)

    def test_native_golden_percentages_and_profession_modifier(self):
        cases = (
            (1, True, 0, 0.01, 1),
            (50, True, -50, 0.25, 25),
            (50, True, 0, 0.50, 50),
            (50, True, 50, 0.75, 75),
            (100, True, 0, 1.0, 100),
        )
        for threshold, compatible, bonus, probability, displayed in cases:
            with self.subTest(threshold=threshold, bonus=bonus):
                actual = calculate(
                    ground_percent=threshold,
                    climate_compatible=compatible,
                    profession_bonus_percent=bonus,
                )
                self.assertAlmostEqual(actual["probability"], probability)
                self.assertEqual(actual["displayed_percent"], displayed)

    def test_incompatible_climate_applies_native_eighty_percent_factor(self):
        actual = calculate(
            ground_percent=100,
            climate_compatible=False,
            profession_bonus_percent=0,
        )
        self.assertEqual(actual, {"probability": 0.8, "displayed_percent": 80})

    def test_zero_threshold_is_forbidden_and_positive_probability_is_clamped(self):
        # A resource-specific zero is an explicit threshold in native ffY.C;
        # it must stay zero instead of falling through to the family setting.
        self.assertEqual(
            calculate(
                ground_percent=0,
                climate_compatible=True,
                profession_bonus_percent=100,
            ),
            {"probability": 0.0, "displayed_percent": -1},
        )
        self.assertEqual(
            calculate(
                ground_percent=100,
                climate_compatible=True,
                profession_bonus_percent=25,
            ),
            {"probability": 1.0, "displayed_percent": 100},
        )

    def test_ui_rounding_does_not_change_exact_rng_boundary(self):
        actual = calculate(
            ground_percent=51,
            climate_compatible=True,
            profession_bonus_percent=-50,
        )
        # 25.5% rounds to 26% in dev.am, while the roll still uses 0.255.
        self.assertEqual(actual, {"probability": 0.255, "displayed_percent": 26})
        self.assertTrue(succeeds(actual["probability"], 0.254999))
        self.assertFalse(succeeds(actual["probability"], 0.255))
        self.assertFalse(succeeds(actual["probability"], 0.255001))

    def test_invalid_input_types_and_nonfinite_values_are_rejected(self):
        for threshold in (True, -1, 101, 1.0):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                calculate(
                    ground_percent=threshold,
                    climate_compatible=True,
                    profession_bonus_percent=0,
                )
        for compatibility in (1, None):
            with self.subTest(compatibility=compatibility), self.assertRaises(
                ValueError
            ):
                calculate(
                    ground_percent=50,
                    climate_compatible=compatibility,
                    profession_bonus_percent=0,
                )
        for bonus in (True, float("nan"), float("inf"), -float("inf")):
            with self.subTest(bonus=bonus), self.assertRaises(ValueError):
                calculate(
                    ground_percent=50,
                    climate_compatible=True,
                    profession_bonus_percent=bonus,
                )

        for probability, draw in (
            (True, 0.5),
            (float("nan"), 0.5),
            (float("inf"), 0.5),
            (0.5, True),
            (0.5, float("nan")),
            (0.5, float("inf")),
            (0.5, 1),
            (-0.01, 0.5),
            (1.01, 0.5),
        ):
            with self.subTest(probability=probability, draw=draw), self.assertRaises(
                ValueError
            ):
                succeeds(probability, draw)


if __name__ == "__main__":
    unittest.main()
