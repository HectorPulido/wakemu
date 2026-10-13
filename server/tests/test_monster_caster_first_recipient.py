import unittest
from caster_empty_anchor import caster_centered_enemy_cells


class FirstRecipientTests(unittest.TestCase):
    def setUp(self):
        self.records = {
            "283748": {
                "effect_class": 330,
                "parameter_count": 0,
                "parameters": [],
                "children": [283752],
            },
            "283752": {
                "effect_class": 865,
                "area_class": "anJ",
                "area_native": "t inv-barre:0-pied:15",
                "native_target_selector": {"class": "fcE", "mask": (1 << 50) | 9},
                "children": [283753],
            },
            "283753": {
                "effect_class": 4,
                "area_class": "anD",
                "area_native": "point",
                "native_target_selector": {"class": "fcE", "mask": 9},
            },
        }

    def choose(self):
        return caster_centered_enemy_cells(
            (0, 0, 0),
            3,
            [283748],
            self.records,
            [(1, 0, 0), (0, 1, 0), (0, 15, 0), (0, 16, 0)],
        )

    def test_native865_selects_recipient_in_own_area_before_value_transfer_children(
        self,
    ):
        self.assertEqual(self.choose(), [(0, 1, 0), (0, 15, 0)])

    def test_leaf_geometry_is_not_projected_onto_caster(self):
        self.records["283753"]["area_native"] = "unknown"
        self.records["283753"]["area_class"] = "unknown"
        self.assertEqual(self.choose(), [(0, 1, 0), (0, 15, 0)])

    def test_direct_group_recipient_uses_same_native_selection_boundary(self):
        self.records["283752"]["effect_class"] = 330
        self.assertEqual(self.choose(), [(0, 1, 0), (0, 15, 0)])

    def test_missing_direct_child_and_unknown_native_area_fail_closed(self):
        self.records["283752"]["area_class"] = "unknown"
        self.assertEqual(self.choose(), [])
        del self.records["283752"]
        self.assertEqual(self.choose(), [])
