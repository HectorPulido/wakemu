"""Pure source-gate regressions for whole-map stochastic scene preparation."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from native_wholemap_scene_fixture import requires_wholemap_cell_scene


class WholemapSceneFixtureTests(unittest.TestCase):
    def test_reachable_native_wholemap_sampler_is_required(self):
        effects = {
            "1": {"effect_class": 330, "children": [2]},
            "2": {
                "effect_class": 349,
                "area_class": "anA",
                "area_native": "empty",
                "children": [],
            },
        }
        self.assertTrue(requires_wholemap_cell_scene([1], effects))
        effects["2"]["area_class"] = "anD"
        effects["2"]["area_native"] = "point"
        self.assertFalse(requires_wholemap_cell_scene([1], effects))

    def test_missing_malformed_children_fail_and_cycles_are_bounded(self):
        with self.assertRaises(ValueError):
            requires_wholemap_cell_scene([1], {})
        with self.assertRaises(ValueError):
            requires_wholemap_cell_scene([1], {"1": {"children": "2"}})
        with self.assertRaises(ValueError):
            requires_wholemap_cell_scene([True], {"True": {}})
        self.assertFalse(
            requires_wholemap_cell_scene(
                [1], {"1": {"effect_class": 330, "children": [1]}}
            )
        )
