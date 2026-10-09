import json
from types import SimpleNamespace
import unittest

from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    global_pv_iterator,
    register_global_area,
    unregister_global_area,
    register_global_fighter,
    set_global_fighter_status,
)


class NativeGlobalPVCollectionsTests(unittest.TestCase):
    def fight(self):
        fight = SimpleNamespace(
            actors={9: object(), 2: object()}, native_effect_areas={}
        )
        initialize_global_pv_collections(fight, (9, 2))
        return fight

    def test_fresh_registration_consumes_native_trove_order(self):
        fight = self.fight()
        fight.native_effect_areas[-4] = {}
        register_global_area(fight, -4)
        self.assertEqual(list(global_pv_iterator(fight, caster_id=9)), [9, 2, -4])

    def test_removal_during_delivery_skips_snapshotted_area(self):
        fight = self.fight()
        fight.native_effect_areas[-4] = {}
        register_global_area(fight, -4)
        iterator = global_pv_iterator(fight, caster_id=9)
        self.assertEqual(next(iterator), 9)
        unregister_global_area(fight, -4)
        del fight.native_effect_areas[-4]
        self.assertEqual(list(iterator), [2])

    def test_status_transition_preserves_off_play_but_excludes_out_of_play(self):
        fight = self.fight()
        set_global_fighter_status(fight, 9, "OFF_PLAY")
        self.assertEqual(list(global_pv_iterator(fight, caster_id=2)), [9, 2])
        iterator = global_pv_iterator(fight, caster_id=2)
        self.assertEqual(next(iterator), 9)
        set_global_fighter_status(fight, 2, "OUT_OF_PLAY")
        self.assertEqual(list(iterator), [])

    def test_new_fighter_uses_registration_not_final_roster_reconstruction(self):
        fight = self.fight()
        fight.actors[8] = object()
        register_global_fighter(fight, 8)
        self.assertEqual(list(global_pv_iterator(fight, caster_id=9)), [9, 8, 2])

    def test_roundtrip_preserves_topology_and_status(self):
        fight = self.fight()
        set_global_fighter_status(fight, 2, "OUT_OF_PLAY")
        restored = SimpleNamespace(
            actors=dict(fight.actors),
            native_effect_areas={},
            native_global_pv_collections=json.loads(
                json.dumps(fight.native_global_pv_collections)
            ),
        )
        self.assertEqual(list(global_pv_iterator(restored, caster_id=9)), [9])

    def test_missing_legacy_producer_is_not_backfilled(self):
        fight = SimpleNamespace(actors={9: object()})
        with self.assertRaisesRegex(ValueError, "producer"):
            global_pv_iterator(fight, caster_id=9)

    def test_native_rro_mode_keeps_actual_caster_despite_status(self):
        fight = self.fight()
        set_global_fighter_status(fight, 9, "OUT_OF_PLAY")
        self.assertEqual(
            list(global_pv_iterator(fight, caster_id=9, caster_only=True)), [9]
        )
