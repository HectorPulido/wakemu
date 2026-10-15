import unittest
from dataclasses import FrozenInstanceError, asdict

from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_retained_runtime import (
    _cached_retained_record,
    _retained_record,
    native_retained_condition_effects,
)
import test_combat_retained_cell_groups as cell_groups


class RetainedMetadataCacheTests(unittest.TestCase):
    def setUp(self):
        _cached_retained_record.cache_clear()

    def test_frozen_record_reuse_and_mutated_content(self):
        row = asdict(RetainedEffect(1, 7, 310, 42, manager_id=7))
        first = _retained_record(row)
        self.assertIs(first, _retained_record(dict(row)))
        with self.assertRaises(FrozenInstanceError):
            first.manager_id = 9
        row["manager_id"] = 9
        self.assertEqual(_retained_record(row).manager_id, 9)
        self.assertEqual(first.manager_id, 7)

    def test_bool_alias_preserves_strict_live_validation(self):
        row = asdict(RetainedEffect(1, 7, 310, 42))
        self.assertIs(type(_retained_record(row).uid), int)
        row["uid"] = True
        self.assertIs(type(_retained_record(row).uid), bool)

    def test_unhashable_and_oversize_values_preserve_constructor_behavior(self):
        for value in ([], "x" * 129, 1 << 65):
            row = asdict(RetainedEffect(1, 7, 310, 42))
            row["manager_id"] = value
            self.assertEqual(_retained_record(row), RetainedEffect(**row))
        self.assertEqual(_cached_retained_record.cache_info().currsize, 0)
        with self.assertRaises(TypeError):
            _retained_record({"unknown": 1})

    def test_warmed_metadata_does_not_cache_live_ownership(self):
        fight, _ = cell_groups.RetainedCellGroupTests().fixture()
        expected = ((350552, 949, 901),)
        self.assertEqual(native_retained_condition_effects(fight, 7), expected)
        fight.native_retained_records[901]["manager_id"] = 999
        with self.assertRaises(ValueError):
            native_retained_condition_effects(fight, 7)
        fight.native_retained_records[901]["manager_id"] = 7
        self.assertEqual(native_retained_condition_effects(fight, 7), expected)
        fight.native_owned_group_effects.clear()
        with self.assertRaises(ValueError):
            native_retained_condition_effects(fight, 7)

    def test_cache_is_bounded(self):
        for uid in range(1, 2200):
            _retained_record(asdict(RetainedEffect(uid, 7, 310, 42)))
        self.assertEqual(_cached_retained_record.cache_info().currsize, 2048)
