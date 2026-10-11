"""Concentration's current native exact range excludes a near friendly target."""
import os
import unittest
import eliotrope_allied_fixture as allied


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EliotropeConcentrationRuntimeTests(
    allied.EliotropeAlliedFixture, unittest.TestCase
):
    def test_concentration_rejects_near_target_and_preserves_atomic_state(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        data = self.allied_fixture(passives=(7210,))
        before = snapshot(data[2])
        rng_before = data[4].getstate()
        with self.assertRaisesRegex(ValueError, "twI"):
            self.allied_cast(data, 7813)
        self.assertEqual(snapshot(data[2]), before)
        self.assertEqual(data[4].getstate(), rng_before)
