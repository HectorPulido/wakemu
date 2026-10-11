"""Enabled Eliotrope passive consumers through actual owned casts."""
import os
import unittest
import test_combat_eliotrope_runtime as runtime


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EliotropePassiveSemanticsRuntimeTests(unittest.TestCase):
    fixture = runtime.EliotropeRuntimeTests.fixture
    cast = runtime.EliotropeRuntimeTests.cast

    def test_quietude_restores_ap_after_actual_exaltation_only_when_equipped(self):
        observations = {}
        for passive in (None, 7204):
            with self.subTest(passive=passive):
                data = self.fixture(passives=() if passive is None else (passive,))
                initial = data[2].actors[7].ap
                spent = self.cast(
                    data, 4692, target=data[2].actors[-7].position, action_id=10
                )
                data = (*data[:2], spent.fight, *data[3:])
                self.assertLess(data[2].actors[7].ap, initial)
                before = data[2].actors[7].ap
                toggled = self.cast(
                    data, 4682, target=data[2].actors[7].position, action_id=11
                )
                after = toggled.fight.actors[7].ap
                self.assertIn(
                    3303,
                    {s.reference for s in toggled.fight.actors[7].state_ledger.entries},
                )
                # Native346520 external1025 requires4682; child346521 is AP gain3.
                observations[passive] = after - before
                if passive == 7204:
                    self.assertEqual(after, min(initial, before + 3))
        self.assertGreater(observations[7204], observations[None])
