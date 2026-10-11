"""Native innate Calm consumers of Eliotrope Meditacion."""
import os
import unittest

import test_combat_eliotrope_runtime as runtime


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EliotropeMeditationRuntimeTests(unittest.TestCase):
    fixture = runtime.EliotropeRuntimeTests.fixture
    next_owned_turn = runtime.EliotropeRuntimeTests.next_owned_turn

    def test_actual_first_turn_calm_selects_damage_or_meditation_ap_resistance(self):
        observed = {}
        for passives in ((), (7720,), (4688,), (7720, 4688)):
            data = self.fixture(passives=passives)
            self.next_owned_turn(data)
            actor = data[2].actors[7]
            observed[passives] = (
                actor.ap,
                actor.max_ap,
                actor.effect_stats.get(48, 0),
                actor.effect_stats.get(27, 0),
            )
        # Family41 restores current AP; at the real turn refill it is capped,
        # and does not increase maximumAP. Damage/resistance remain measurable.
        self.assertEqual(observed[(7720,)][0], observed[()][0], observed)
        self.assertEqual(observed[(7720,)][1], observed[()][1], observed)
        self.assertEqual(observed[(7720,)][2] - observed[()][2], -30, observed)
        self.assertEqual(observed[(7720,)][3] - observed[()][3], 50, observed)
        # Efervescence changes the matching child, not the requested amount.
        self.assertEqual(observed[(4688,)], observed[()], observed)
        self.assertEqual(observed[(7720, 4688)], observed[(7720,)], observed)
