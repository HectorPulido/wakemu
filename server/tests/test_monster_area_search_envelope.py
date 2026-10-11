"""Native area search fixes scenes without extending actual casting range."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_pending_scenarios import effect_search_envelope


class MonsterAreaSearchEnvelopeTests(unittest.TestCase):
    def test_directional_inverted_t_needs_enemy_beyond_target_range(self):
        effect = dict(
            area_class="anJ",
            area_native="t inv-barre:1-pied:1",
            native_area_points=[[0, 0], [0, 1], [0, -1], [1, 0]],
            children=[],
        )
        self.assertEqual(effect_search_envelope({"181239": effect}, [181239], 1), 2)

    def test_point_spell_keeps_its_original_search_range(self):
        effect = dict(area_class="anD", area_native="point", children=[])
        self.assertEqual(effect_search_envelope({"1": effect}, [1], 4), 4)

    def test_group_child_extent_is_included_without_cyclic_recursion(self):
        effects = {
            "1": dict(area_class="anD", area_native="point", children=[2]),
            "2": dict(
                area_class="anJ", native_area_points=[[0, 0], [3, 0]], children=[1]
            ),
        }
        self.assertEqual(effect_search_envelope(effects, [1], 2), 5)

    def test_large_search_is_bounded_and_unknown_geometry_not_invented(self):
        effect = dict(area_class="anJ", native_area_points=[[100, 0]], children=[])
        self.assertEqual(effect_search_envelope({"1": effect}, [1], 1), 12)
        self.assertEqual(
            effect_search_envelope({"2": dict(area_class="unknown")}, [2], 3), 3
        )
