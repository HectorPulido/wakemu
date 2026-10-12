"""Prepared native children must not depend on prior active DB membership."""
import unittest
from export_monster_cell_groups import required_effect_ids


class PreparedCellGroupDependencyTests(unittest.TestCase):
    def test_imported_child_absent_active_records_is_selected(self):
        # Native spell5819:330/184991 ->349/184992 ->994/184993.
        graph = {
            "effects": {
                "184991": {"effect_class": 330, "children": [184992]},
                "184992": {"effect_class": 349, "children": [184993]},
                "184993": {"effect_class": 994, "children": []},
            }
        }
        self.assertEqual(required_effect_ids([121204], graph), [121204, 184992])

    def test_deduplicates_active_and_prepared_without_other_families(self):
        graph = {"effects": {"12": {"effect_class": 349}, "13": {"effect_class": 330}}}
        self.assertEqual(required_effect_ids([12, 12], graph), [12])

    def test_missing_graph_or_invalid_reference_rejects(self):
        for graph in (
            {},
            {"effects": {"0": {"effect_class": 349}}},
            {"effects": {"12": None}},
        ):
            with self.subTest(graph=graph), self.assertRaises(ValueError):
                required_effect_ids([], graph)
