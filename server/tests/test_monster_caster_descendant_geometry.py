import unittest
from caster_empty_anchor import (
    spatial_enemy_descendants,
    rank_enemy_geometry,
    rank_empty_geometry,
    caster_centered_enemy_cells,
)


class DescendantGeometryTests(unittest.TestCase):
    def setUp(self):
        self.child = dict(
            effect_class=4,
            area_class="anJ",
            area_native="t inv-barre:0-pied:4",
            native_target_selector=dict(class_="fcE"),
        )
        self.child["native_target_selector"] = {"class": "fcE", "mask": 9}
        self.records = {
            "183846": dict(effect_class=330, children=[120076]),
            "120076": self.child,
        }

    def test_actual_directed_t_prefers_enemy_with_intermediate_empty_anchor(self):
        source = (0, 0, 0)
        enemies = [(1, 0, 0), (3, 0, 0)]
        anchors = [(1, 0, 0), (2, 0, 0), (3, 0, 0), (0, 1, 0)]
        effects = spatial_enemy_descendants([183846], self.records)
        self.assertEqual(
            rank_enemy_geometry(
                source, enemies, anchors, effects, 1, 4, {"linear": True}
            )[0],
            (3, 0, 0),
        )
        ranked = rank_empty_geometry(
            source, [(4, 0, 0), (2, 0, 0)], [(3, 0, 0)], effects
        )
        self.assertEqual(ranked[0], (2, 0, 0))

    def test_missing_and_cycle_ancestry_do_not_produce_geometry_authority(self):
        self.records.pop("120076")
        self.assertIsNone(spatial_enemy_descendants([183846], self.records))
        self.records["183846"]["children"] = [183846]
        self.assertIsNone(spatial_enemy_descendants([183846], self.records))

    def test_unknown_shape_or_selector_does_not_get_ranked(self):
        self.child["area_class"] = "unknown"
        self.assertIsNone(spatial_enemy_descendants([183846], self.records))
        self.child["area_class"] = "anJ"
        self.child["native_target_selector"]["mask"] = 1 << 39
        self.assertIsNone(spatial_enemy_descendants([183846], self.records))

    def test_alignment_cannot_be_invented_to_get_a_hit(self):
        effects = spatial_enemy_descendants([183846], self.records)
        enemies = [(1, 0, 0), (3, 0, 0)]
        self.assertEqual(
            rank_enemy_geometry(
                (0, 0, 0), enemies, [(1, 1, 0)], effects, 1, 4, {"linear": True}
            ),
            enemies,
        )

    def test_native_actor_branch_centers_on_caster_with_real_facing(self):
        self.records["183846"]["parameter_count"] = 1
        self.records["183846"]["parameters"] = [0, 0]
        cells = [(-1, 0, 0), (0, 1, 0), (0, 4, 0), (1, 0, 0)]
        self.assertEqual(
            caster_centered_enemy_cells((0, 0, 0), 3, [183846], self.records, cells),
            [(0, 1, 0), (0, 4, 0)],
        )
        self.assertEqual(
            caster_centered_enemy_cells((0, 0, 0), None, [183846], self.records, cells),
            [],
        )
        self.records["183846"]["parameter_count"] = 6
        self.assertEqual(
            caster_centered_enemy_cells((0, 0, 0), 3, [183846], self.records, cells), []
        )
