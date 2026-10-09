import unittest
from types import SimpleNamespace
from copy import deepcopy
from wakfu_server.combat_spell_usage import validate_usage, consume_usage, limits


class UsageTests(unittest.TestCase):
    def fixture(self):
        actor = SimpleNamespace(
            id=7, physical_radius=0, position=(0, 0, 0), turn_count=1
        )
        enemy = SimpleNamespace(
            id=-8, physical_radius=0, position=(1, 0, 0), turn_count=0
        )
        fight = SimpleNamespace(
            actors={7: actor, -8: enemy},
            native_spell_usage={},
            native_table_turn=1,
            native_effect_areas={},
        )
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        initialize_global_pv_collections(fight, tuple(fight.actors))
        return fight, actor

    def cast(self, fight, caster, reference=4776, cell=(1, 0, 0)):
        rule = validate_usage(fight, caster, reference, 20, cell)
        consume_usage(fight, dict(actor_id=7, spell_id=reference, native_usage=rule))

    def test_juicio_third_same_target_rejected_other_target_allowed(self):
        fight, caster = self.fixture()
        self.assertEqual(limits(4776, 20), dict(per_target=2, per_turn=4, interval=0))
        self.cast(fight, caster)
        self.cast(fight, caster)
        before = deepcopy(fight.native_spell_usage)
        with self.assertRaisesRegex(ValueError, "per target"):
            self.cast(fight, caster)
        self.assertEqual(before, fight.native_spell_usage)
        self.cast(fight, caster, cell=(0, 0, 0))
        self.cast(fight, caster, cell=(0, 0, 0))
        with self.assertRaisesRegex(ValueError, "per turn"):
            self.cast(fight, caster, cell=(2, 0, 0))

    def test_new_personal_turn_resets_counts(self):
        fight, caster = self.fixture()
        self.cast(fight, caster)
        self.cast(fight, caster)
        caster.turn_count += 1
        self.cast(fight, caster)
        self.assertEqual(fight.native_spell_usage["7"]["targets"]["4776"]["-8"], 1)

    def test_preview_discard_preserves_original(self):
        fight, caster = self.fixture()
        preview = deepcopy(fight)
        self.cast(preview, preview.actors[7])
        self.assertEqual(fight.native_spell_usage, {})

    def test_target_footprint_counts_xy_ignoring_height(self):
        fight, caster = self.fixture()
        fight.actors[-8].physical_radius = 1
        self.cast(fight, caster, cell=(2, 0, 8))
        self.cast(fight, caster, cell=(2, 0, 8))
        with self.assertRaisesRegex(ValueError, "per target"):
            self.cast(fight, caster, cell=(2, 0, -8))

    def test_native_population_keeps_off_play_and_excludes_retired_history(self):
        from wakfu_server.combat_global_pv_collections import (
            set_global_fighter_status,
            unregister_global_fighter,
        )
        from wakfu_server.combat_usage_targets import usage_targets

        fight, caster = self.fixture()
        set_global_fighter_status(fight, -8, "OFF_PLAY")
        self.assertEqual([t.identity for t in usage_targets(fight, (1, 0, 12))], [-8])
        unregister_global_fighter(fight, -8)
        self.assertIn(-8, fight.actors)
        self.assertEqual(usage_targets(fight, (1, 0, -12)), ())

    def test_area_is_validated_but_bcR_controls_consumption(self):
        from unittest.mock import patch
        from wakfu_server.combat_global_pv_collections import register_global_area
        from wakfu_server.combat_usage_targets import usage_targets

        fight, caster = self.fixture()
        fight.native_effect_areas[90] = dict(
            uid=90, reference=1, native_area_contract="faY", cell=(1, 0, 99)
        )
        register_global_area(fight, 90)
        definition = dict(type="GLYPH", raw_bcR=False)
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"1": definition},
        ):
            targets = {t.identity: t.consume for t in usage_targets(fight, (1, 0, -99))}
            self.assertEqual(targets, {-8: True, 90: False})
            definition["raw_bcR"] = True
            self.assertTrue(
                dict((t.identity, t.consume) for t in usage_targets(fight, (1, 0, 0)))[
                    90
                ]
            )

    def test_native_interval_survives_turn_reset(self):
        fight, caster = self.fixture()
        self.cast(fight, caster, 1013)
        caster.turn_count += 1
        fight.native_table_turn = 3
        with self.assertRaisesRegex(ValueError, "interval"):
            self.cast(fight, caster, 1013)
        fight.native_table_turn = 4
        self.cast(fight, caster, 1013)

    def test_all_native_tables_are_already_byte_narrowed(self):
        from wakfu_server.combat_spell_usage import native_limits

        tables = [r["limits"] for r in native_limits().values()]
        tables += [
            a["limits"] for r in native_limits().values() for a in r["conditional"]
        ]
        self.assertEqual(len(native_limits()), 4143)
        self.assertEqual(len(tables), 4943)
        self.assertTrue(
            all(type(v) is int and -128 <= v <= 127 for row in tables for v in row)
        )
        self.assertEqual({row[2] for row in tables}, {0})
