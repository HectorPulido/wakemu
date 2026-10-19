import unittest
from dataclasses import FrozenInstanceError, asdict
from unittest.mock import patch

from wakfu_server.combat_retained_effects import (
    NativeRetainedEffectView,
    RetainedEffect,
)
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

    def test_warmed_hex_facts_still_validate_current_owned_target_and_population(self):
        from wakfu_server.combat_effect_removal import _cached_hex_identity_fields

        fight, _ = cell_groups.RetainedCellGroupTests().fixture()
        _cached_hex_identity_fields.cache_clear()
        expected = ((350552, 949, 901),)
        self.assertEqual(native_retained_condition_effects(fight, 7), expected)
        self.assertEqual(native_retained_condition_effects(fight, 7), expected)
        self.assertGreater(_cached_hex_identity_fields.cache_info().hits, 0)
        row = fight.native_owned_group_effects[901]
        row["target_id"] = 7
        with self.assertRaisesRegex(ValueError, "disagrees with owned identity"):
            native_retained_condition_effects(fight, 7)
        row["target_id"] = None
        self.assertEqual(native_retained_condition_effects(fight, 7), expected)
        actor = fight.actors.pop(7)
        with self.assertRaises(ValueError):
            native_retained_condition_effects(fight, 7)
        fight.actors[7] = actor
        fight.native_owned_group_effects.clear()
        with self.assertRaises(ValueError):
            native_retained_condition_effects(fight, 7)

    def test_warmed_hex_facts_reject_changed_valid_identity_and_malformed_payload(self):
        from wakfu_server.combat_effect_removal import _proto_replace
        from wakfu_server.combat_effects import _integer

        fight, payload = cell_groups.RetainedCellGroupTests().fixture()
        expected = ((350552, 949, 901),)
        self.assertEqual(native_retained_condition_effects(fight, 7), expected)
        row = fight.native_owned_group_effects[901]
        row["payload"] = _proto_replace(payload, 3, 0, _integer(3, 350553)).hex()
        with self.assertRaisesRegex(ValueError, "disagrees with owned identity"):
            native_retained_condition_effects(fight, 7)
        row["payload"] = "00"
        with self.assertRaises(ValueError):
            native_retained_condition_effects(fight, 7)
        row["payload"] = payload.hex()
        self.assertEqual(native_retained_condition_effects(fight, 7), expected)

    def test_retained_view_resolves_shared_target_manager_once_per_view(self):
        import wakfu_server.combat_retained_effects as combat_retained_effects

        fight, _ = cell_groups.RetainedCellGroupTests().fixture()
        original = combat_retained_effects.state_manager
        calls = []

        def counted(current_fight, target_id):
            calls.append((current_fight, target_id))
            return original(current_fight, target_id)

        entries = [
            RetainedEffect(9901, 7, 949, 350552),
            RetainedEffect(9902, 7, 949, 350552),
            *(_retained_record(row) for row in fight.native_retained_records.values()),
        ]
        with patch.object(combat_retained_effects, "state_manager", counted):
            NativeRetainedEffectView(fight, entries, population_verified_complete=True)
        self.assertEqual([(target_id) for _, target_id in calls], [7])

    def test_retained_view_rejects_missing_target_and_new_view_sees_mutation(self):
        import wakfu_server.combat_retained_effects as combat_retained_effects

        fight, _ = cell_groups.RetainedCellGroupTests().fixture()
        entry = RetainedEffect(9901, 7, 949, 350552)
        with patch.object(combat_retained_effects, "state_manager", return_value=None):
            with self.assertRaisesRegex(
                ValueError, "Invalid native retained effect owner/family"
            ):
                NativeRetainedEffectView(
                    fight,
                    [
                        entry,
                        *(
                            _retained_record(row)
                            for row in fight.native_retained_records.values()
                        ),
                    ],
                    population_verified_complete=True,
                )

        NativeRetainedEffectView(
            fight,
            [
                entry,
                *(
                    _retained_record(row)
                    for row in fight.native_retained_records.values()
                ),
            ],
            population_verified_complete=True,
        )
        actor = fight.actors.pop(7)
        try:
            with self.assertRaisesRegex(
                ValueError, "Invalid native retained effect owner/family"
            ):
                NativeRetainedEffectView(
                    fight,
                    [
                        entry,
                        *(
                            _retained_record(row)
                            for row in fight.native_retained_records.values()
                        ),
                    ],
                    population_verified_complete=True,
                )
        finally:
            fight.actors[7] = actor

    def test_shared_area_target_is_resolved_once_with_live_geometry(self):
        import wakfu_server.combat_retained_effects as combat_retained_effects
        from test_combat_state_managers import StateManagerTests

        fight = StateManagerTests().fixture()
        fight.id = 12
        fight.owned_stat_effects = {}
        fight.state_wire_payloads = {}
        fight.native_owned_group_effects = {}
        fight.native_owned_area_effects = {}
        fight.native_owned_spatial_effects = {}
        fight.native_retained_records = {}
        entries = [RetainedEffect(uid, 901, 949, 350552) for uid in (9901, 9902, 9903)]
        original = combat_retained_effects.state_manager
        calls = []

        def counted(current_fight, target_id):
            calls.append((current_fight, target_id))
            return original(current_fight, target_id)

        with patch.object(combat_retained_effects, "state_manager", counted):
            NativeRetainedEffectView(fight, entries, population_verified_complete=True)
        self.assertEqual([(target_id) for _, target_id in calls], [901])
        self.assertEqual(tuple(fight.native_effect_areas[901]["cell"]), (2, 3, 4))
