import unittest
from unittest.mock import Mock
import test_combat_effect_area_events as fixtures
from wakfu_server.combat_area_removal_masks import (
    area_removal_masks,
    removal_mask_matches,
)
from wakfu_server.combat_effect_area import remove_owned_hour_area


class RemovalMaskTests(unittest.TestCase):
    def test_catalog_mask_is_not_a_fight_property(self):
        definition = {
            "properties": [10010],
            "native_removal_masks": [10010],
            "native_fight_properties": [10010],
        }
        self.assertEqual(area_removal_masks(definition), frozenset({10010}))
        self.assertFalse(removal_mask_matches(definition, (10000,)))
        self.assertTrue(removal_mask_matches(definition, (10010,)))
        with self.assertRaises(ValueError):
            area_removal_masks(dict(definition, properties=[3]))

    def test_parent_removal_is_exact_and_reentrant_safe(self):
        runtime, row, calls = fixtures.AreaEventTests().fixture()
        row["effect_uid"] = 9010
        definition = runtime.definitions["1474"]
        definition["properties"] = [10010]
        runtime.fight.native_owned_area_effects = {9010: {}}
        runtime.fight.native_retained_records = {9010: {}}
        retention = runtime.dispatcher.native_retention
        retention.remove = Mock()
        self.assertTrue(runtime._remove_on_masks(row, definition, (10010,)))
        retention.remove.assert_called_once_with(9010)
        runtime.fight.native_owned_area_effects[9010]["removing"] = True
        self.assertFalse(runtime._remove_on_masks(row, definition, (10010,)))
        self.assertEqual(retention.remove.call_count, 1)

    def test_qs_unregisters_before_removed_callback(self):
        runtime, row, calls = fixtures.AreaEventTests().fixture()
        runtime.fight.native_retired_area_managers = {}
        callback = Mock()
        callback.removed.side_effect = lambda removed: self.assertNotIn(
            901, runtime.fight.native_effect_areas
        )
        remove_owned_hour_area(runtime.fight, 901, callbacks=callback)
        callback.removed.assert_called_once_with(row)
        self.assertEqual(
            remove_owned_hour_area(runtime.fight, 901, callbacks=callback), ()
        )
