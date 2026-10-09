"""Casting restrictions remain distinct from native path options."""
import unittest
from unittest.mock import patch

from wakfu_server.combat_native_spell_casting import catalog, definition


class CastingEligibilityMetadataTests(unittest.TestCase):
    def test_complete_installed_tables_preserve_distinct_boolean_flags(self):
        fields = (
            "free_cell",
            "path_option",
            "diagonal",
            "linear_path",
            "allow_self",
            "line_of_sight",
            "linear",
            "range_modifiable",
        )
        records = catalog()
        self.assertEqual(len(records), 4143)
        distinct = 0
        for record in records.values():
            for table in (record, *record["conditional"]):
                for field in fields:
                    self.assertIs(type(table[field]), bool)
                distinct += table["free_cell"] != table["path_option"]
            self.assertIs(type(record["forbid_QI_P"]), bool)
            self.assertIs(type(record["cast_criterion_native_present"]), bool)
        self.assertEqual(distinct, 200)

    def test_consumer_does_not_conflate_free_cell_and_path_option(self):
        record = dict(
            costs=[[2, 0, 0]],
            levels=[[1, 4, []]],
            conditional=[],
            categories=[],
            free_cell=False,
            path_option=True,
            diagonal=True,
            linear_path=False,
            allow_self=True,
            line_of_sight=True,
            linear=False,
            range_modifiable=True,
            forbid_QI_P=True,
            cast_criterion_raw="native criterion",
            cast_criterion_native_present=True,
        )
        with patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={"1": record},
        ):
            selected = definition(1, 1, None, {})
        for field in (
            "free_cell",
            "path_option",
            "diagonal",
            "linear_path",
            "allow_self",
            "forbid_QI_P",
            "cast_criterion_raw",
            "cast_criterion_native_present",
        ):
            self.assertEqual(selected[field], record[field])
