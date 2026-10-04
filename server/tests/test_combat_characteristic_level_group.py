import unittest
from types import SimpleNamespace
from wakfu_server.combat_characteristic_level_group import (
    characteristic_group_override,
    runtime_group_level,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation


def effect(stat=1, lookup=1, mode=2):
    values = [0, 0, 1, 0, 1, 0, stat, lookup, 0, 1, mode]
    return dict(
        effect_class=913,
        parameters=[n for v in values for n in (v, 0)],
        native_execution_mode=0,
    )


class CharacteristicGroupTests(unittest.TestCase):
    def test_native_selected_characteristic_modes_do_not_add_virtual_hp(self):
        self.assertEqual(
            [
                characteristic_group_override(
                    effect(mode=m), 1, current=60, maximum=100
                )
                for m in range(5)
            ],
            [60, 100, 60, 40, 40],
        )

    def test_native_caster_target_selection_and_unknown_snapshot(self):
        actors = {
            7: SimpleNamespace(effect_stats={1: 60}, effect_maxima={1: 100}),
            8: SimpleNamespace(effect_stats={1: 10}, effect_maxima={1: 50}),
        }
        i = EffectInvocation(308066, 1, 7, 8, (0, 0, 0))
        for lookup, expected in ((1, 60), (0, 20)):
            e = effect(lookup=lookup)
            values = dict(parameters=[0, 0, 1, 0, 1, 0, 1, lookup, 0, 1, 2])
            self.assertEqual(runtime_group_level(e, values, i, actors), expected)
        del actors[7].effect_stats[1]
        with self.assertRaisesRegex(ValueError, "snapshot"):
            runtime_group_level(
                effect(), dict(parameters=[0, 0, 1, 0, 1, 0, 1, 1, 0, 1, 2]), i, actors
            )

    def test_null_target_preserves_native_override_sentinel(self):
        i = EffectInvocation(308066, 10, 7, None, (0, 0, 0))
        e = effect(lookup=0)
        values = dict(parameters=[0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 2])
        self.assertEqual(
            runtime_group_level(e, values, i, {}, return_native_override=True), -1
        )
        self.assertEqual(runtime_group_level(e, values, i, {}), 10)

    def test_native_int32_snapshot_and_zero_maximum(self):
        with self.assertRaises(ValueError):
            characteristic_group_override(effect(), 1, current=None, maximum=100)
        with self.assertRaisesRegex(ValueError, "zero"):
            characteristic_group_override(effect(), 1, current=1, maximum=0)
