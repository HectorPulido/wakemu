"""Native Steamer opening, regeneration, caps and state-form inverse branches."""
import os
import unittest
import test_combat_steamer_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerResourcesRuntimeTests(unittest.TestCase):
    fixture = helpers.SteamerRuntimeTests.fixture
    cast = helpers.SteamerRuntimeTests.cast
    adopt = helpers.SteamerRuntimeTests.adopt
    next_owned_turn = helpers.SteamerRuntimeTests.next_owned_turn

    def test_real_regeneration_and_inversion_preserve_native_sp_cap(self):
        for passive in (None, 6935):
            with self.subTest(passive=passive):
                fixture = self.fixture(() if passive is None else (passive,))
                actor = fixture[2].actors[7]
                self.assertEqual(
                    (actor.effect_stats[4], actor.effect_stats[123]), (3, 3)
                )
                observed = []
                for _ in range(4):
                    fixture = self.next_owned_turn(fixture)
                    actor = fixture[2].actors[7]
                    observed.append((actor.effect_stats[4], actor.effect_stats[123]))
                    self.assertLessEqual(
                        actor.effect_stats[123], actor.effect_maxima[123]
                    )
                    self.assertGreaterEqual(
                        actor.effect_stats[123], actor.effect_minima[123]
                    )
                # Normal natural regeneration restores WP;6935 switches to SP.
                # Startup1201 expands the native base maximum; use the actual
                # initialized bound instead of mistaking base6 for the live cap.
                self.assertEqual(observed[0], (4, 3) if passive is None else (3, 4))
                self.assertEqual(observed[-1], (6, 3) if passive is None else (3, 7))

    def test_real_stasis_toggle_inverse_removes_state_and_restores_characteristics(
        self,
    ):
        fixture = self.fixture()
        before = dict(fixture[2].actors[7].effect_stats)
        entered = self.cast(fixture, 6923, target=fixture[2].actors[7].position)
        self.assertIn(
            7647, {s.reference for s in entered.fight.actors[7].state_ledger.entries}
        )
        fixture = self.adopt(fixture, entered.fight)
        # Native6923 has interval2. Its increasing native end-turn SP drain
        # reaches zero and invokes the original state321 inverse automatically.
        for _ in range(2):
            fixture = self.next_owned_turn(fixture)
        removed = fixture[2]
        self.assertNotIn(
            7647, {s.reference for s in removed.actors[7].state_ledger.entries}
        )
        self.assertEqual(removed.actors[7].effect_stats.get(101), before.get(101))
