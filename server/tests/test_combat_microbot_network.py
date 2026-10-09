import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_microbot_network import (
    SOURCE,
    build_microbot_segments,
    microbot_cells,
    register_microbot,
    unregister_microbot,
    preflight_microbot_owner,
)
from wakfu_server.combat_trove_int_map import NativeTroveIntMap


class MicrobotNetworkTests(unittest.TestCase):
    def test_native_intervening_distance_merges_links_and_keeps_crossing_axes(self):
        rows = [dict(cell=(x, y, 0)) for x, y in ((0, 0), (4, 0), (8, 0), (4, 4))]
        segments = build_microbot_segments(rows, 3, lambda start, end: True)
        self.assertEqual(
            set(segments), {((0, 0, 0), (8, 0, 0)), ((4, 0, 0), (4, 4, 0))}
        )
        cells = microbot_cells(segments, lambda x, y: 2)
        self.assertEqual(len(cells), 13)
        self.assertIn((4, 4, 2), cells)

    def test_native_failed_sn_breaks_chain_without_bridging_previous_gap(self):
        rows = [dict(cell=(x, 0, 0)) for x in (0, 3, 6, 9)]
        segments = build_microbot_segments(rows, 2, lambda start, end: start[0] != 3)
        self.assertEqual(segments, (((0, 0, 0), (3, 0, 0)), ((6, 0, 0), (9, 0, 0))))
        with self.assertRaises(ValueError):
            build_microbot_segments(rows, 2, lambda start, end: None)

    def test_owner_range_is_captured_once_and_removal_retains_empty_network(self):
        owner = SimpleNamespace(id=7, effect_stats={93: 3})
        fight = SimpleNamespace(map_id=1134, actors={7: owner}, native_effect_areas={})
        projection = SimpleNamespace(
            segment_is_passable=lambda start, end: True, surface_z=lambda x, y: 0
        )
        with patch(
            "wakfu_server.combat_microbot_path.microbot_path_projection",
            return_value=projection,
        ):
            for uid, x in ((20, 0), (21, 4)):
                row = dict(
                    uid=uid,
                    owner_id=7,
                    cell=(x, 0, 0),
                    native_faw_constructor=dict(kind=4),
                )
                fight.native_effect_areas[uid] = row
                register_microbot(fight, row)
                self.assertEqual(row["native_microbot_network_source"], SOURCE)
            owner.effect_stats[93] = 0
            self.assertEqual(preflight_microbot_owner(fight, 7), 3)
            first = fight.native_effect_areas.pop(20)
            unregister_microbot(fight, first)
            self.assertEqual(fight.native_microbot_networks[7]["segments"], [])
            second = fight.native_effect_areas.pop(21)
            unregister_microbot(fight, second)
            self.assertEqual(fight.native_microbot_networks[7]["microbot_ids"], [])
            self.assertEqual(preflight_microbot_owner(fight, 7), 3)
            with self.assertRaises(ValueError):
                unregister_microbot(fight, second)

    def test_missing_actual_owner_characteristic_is_not_native_absence_default(self):
        fight = SimpleNamespace(actors={7: SimpleNamespace(effect_stats={})})
        with self.assertRaises(ValueError):
            preflight_microbot_owner(fight, 7)

    def test_actual_978_area_handler_registers_qf_without_fighter_roster_or_slot(self):
        from test_combat_fake_fighter_area import NativeFakeFighterAreaTests
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_effect_area import remove_owned_hour_area
        from wakfu_server.combat_state_managers import state_manager

        fight, handler, allocated, packets = NativeFakeFighterAreaTests().create()
        fight.map_id = 1134
        fight.actors[7].effect_stats = {93: 3}
        projection = SimpleNamespace(
            segment_is_passable=lambda start, end: True, surface_z=lambda x, y: 0
        )
        with patch(
            "wakfu_server.combat_microbot_path.microbot_path_projection",
            return_value=projection,
        ):
            self.assertTrue(
                handler(
                    {"effect_class": 339},
                    {"parameters": [978]},
                    EffectInvocation(100, 1, 7, None, (2, 3, 0)),
                )
            )
            row = fight.native_effect_areas[901]
            self.assertEqual(row["native_microbot_network_source"], SOURCE)
            self.assertEqual(row["native_obstacle_id"], -1)
            self.assertIsNotNone(state_manager(fight, 901))
            self.assertEqual(set(fight.actors), {7})
            self.assertEqual(fight.native_microbot_networks[7]["microbot_ids"], [901])
            self.assertEqual(fight.native_microbot_networks[7]["segments"], [])
            remove_owned_hour_area(fight, 901)
            self.assertEqual(fight.native_microbot_networks[7]["microbot_ids"], [])
        self.assertEqual(allocated, [901, 902])
        self.assertEqual(len(packets), 1)

    def test_int_hash_preserves_negative_key_and_rehash_history(self):
        mapping = NativeTroveIntMap()
        for key in (-1, 0, 1, -(1 << 31), 2147483647, 11, 22, -22):
            mapping.put(key)
        self.assertEqual(
            set(mapping.order()), {-1, 0, 1, -(1 << 31), 2147483647, 11, 22, -22}
        )
        with self.assertRaises(ValueError):
            mapping.put(1 << 31)

    def test_missing_map_identity_is_rejected_before_geometry_projection(self):
        from wakfu_server.combat_microbot_path import microbot_path_projection

        with self.assertRaisesRegex(ValueError, "Missing native microbot map identity"):
            microbot_path_projection(SimpleNamespace())
