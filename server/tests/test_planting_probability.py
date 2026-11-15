"""Published climate metadata and World-owned once-only roll comparison.

Probability calculation, native surface policy and golden arithmetic now run
against the real Rust planner instead of the retired Python simulator.
"""

import unittest

from wakfu_server.planting_probability import succeeds
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
        self.assertEqual(len(climates), 533)
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

    def test_ui_rounding_does_not_change_exact_rng_boundary(self):
        # Exact probability fixture from the native Rust golden matrix; World
        # compares the unrounded value and never accepts a displayed percentage.
        actual = {"probability": 0.255}
        self.assertTrue(succeeds(actual["probability"], 0.254999))
        self.assertFalse(succeeds(actual["probability"], 0.255))
        self.assertFalse(succeeds(actual["probability"], 0.255001))

    def test_invalid_input_types_and_nonfinite_values_are_rejected(self):
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
