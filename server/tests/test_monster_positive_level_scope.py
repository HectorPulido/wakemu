"""Positive actor scope preserves native source and excludes level-zero execution."""
import copy
import unittest

from expand_monster_positive_level_scope import expand, positive_actor_interval
import test_monster_offline_source_import as source_import_tests
from prepare_monster_offline_source_import import prepare_source_import


class PositiveLevelScopeTests(unittest.TestCase):
    def test_zero_minimum_with_positive_maximum_keeps_native_range(self):
        native = {
            "ref": 7,
            "name": "Native summon",
            "min_level": 0,
            "max_level": 245,
            "abilities": [{"spell_id": 9}],
            "initial_states": [],
        }
        base = {
            "rows": [],
            "published_enabled": 1,
            "unpublished": 0,
            "outside_eligible_count": 1,
            "unpublished_exclusive_categories": {},
            "outside_eligible_exclusive_categories": {
                "owned_but_native_minimum_zero": 1
            },
        }
        original = copy.deepcopy(native)
        result, added = expand(base, [native], {1})
        self.assertEqual(result["eligible_scope"], 2)
        self.assertEqual(added[0]["validation_ranges"], [[1, 245]])
        self.assertEqual(added[0]["native_range"], [0, 245])
        self.assertEqual(native, original)
        self.assertFalse(added[0]["admission"])

    def test_no_positive_level_is_not_selected(self):
        self.assertIsNone(positive_actor_interval({"min_level": 0, "max_level": 0}))
        self.assertEqual(
            positive_actor_interval({"min_level": 0, "max_level": 1}), [1, 1]
        )
        self.assertIsNone(positive_actor_interval({"min_level": -1, "max_level": 245}))

    def test_source_import_explicit_positive_subset_preserves_policy(self):
        args = source_import_tests.OfflineSourceImportTests().inputs()
        args[5][1]["min_level"] = 0
        npc, roots, rows = prepare_source_import(*args, positive_actor_levels_only=True)
        self.assertEqual(rows[0]["blockers"], [])
        self.assertEqual(rows[0]["min_level"], 0)
        self.assertEqual(rows[0]["validation_min_level"], 1)
        self.assertEqual(npc["activation_policy"], args[0]["activation_policy"])
        self.assertEqual(npc["spells"], args[1]["spells"])

    def test_positive_subset_does_not_import_zero_only_actor(self):
        args = source_import_tests.OfflineSourceImportTests().inputs()
        args[5][1].update(min_level=0, max_level=0)
        npc, roots, rows = prepare_source_import(*args, positive_actor_levels_only=True)
        self.assertIn("invalid_native_level_interval", rows[0]["blockers"])
        self.assertEqual(npc["spells"], {})
