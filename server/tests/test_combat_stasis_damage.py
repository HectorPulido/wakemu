import struct
import unittest

from wakfu_server.combat_damage_healing import damage_amount, stasis_resistance_element
from wakfu_server.combat_damage_events import damage_event_ids
from wakfu_server.combat_effects import direct_damage


class StasisDamageTests(unittest.TestCase):
    def test_original_fau_coefficient_results_and_snapshot_preservation(self):
        source = {21: 100, 22: 200, 23: 0, 24: 0}
        target = {28: 0, 29: 100, 30: 200, 31: 300}
        original = dict(target)
        context = dict(
            critical=False,
            single_target=False,
            area=False,
            melee=True,
            berserk=False,
            front=True,
        )
        for mask, expected in enumerate((100, 300, 100, 300)):
            self.assertEqual(
                damage_amount(
                    100,
                    917,
                    source,
                    target,
                    arithmetic_context=dict(context),
                    coefficient_mask=mask,
                    rng=lambda: 0.99,
                ),
                expected,
            )
        self.assertEqual(target, original)

    def test_native_resistance_presence_and_ties(self):
        self.assertEqual(stasis_resistance_element({28: 100, 29: 100}), 2)
        self.assertEqual(stasis_resistance_element({29: -10, 30: -10}), 4)
        self.assertEqual(stasis_resistance_element({30: -20, 31: 0}), 3)
        with self.assertRaises(ValueError):
            stasis_resistance_element({32: 0})

    def test_running_effect_retains_stasis_identity_and_event(self):
        events = damage_event_ids(
            dict(effect_class=917, native_effect_flags=[], target_masks=[None] * 7),
            container_type=11,
            phase=3,
            blocked=False,
            localization="FRONT",
            context_is_native_fight=True,
        )
        self.assertEqual(events, (0, 2, 9))
        packet = direct_damage(
            1,
            2,
            uid=3,
            generic_effect=4,
            element=917,
            caster_id=5,
            target_id=6,
            damage=7,
        )
        self.assertEqual(struct.unpack_from(">i", packet, 13)[0], 917)
