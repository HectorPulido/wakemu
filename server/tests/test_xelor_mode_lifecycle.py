"""Real granted Distortion, paid attack, caster-clock expiry and fresh fight."""
import json
import unittest
import test_xelor_runtime_pipeline as helpers
from wakfu_server.fight_checkpoint_store import Checkpoints, snapshot


class XelorModeLifecycleTests(unittest.TestCase):
    def test_actual_distortion_paid_action_expiry_memory_and_fresh_reset(self):
        h = helpers.XelorRuntimePipelineTests()
        for passive in (None, 756):
            with self.subTest(passive=passive):
                data = h.fixture(passives=() if passive is None else (passive,))
                baseline = data[2].actors[7]
                maxima = (baseline.max_ap, baseline.max_mp, baseline.effect_maxima[4])
                tx = h.dial(data)
                data = h.adopt(data, tx.fight)
                tx = h.cast(data, 7794, action_id=20)
                data = h.adopt(data, tx.fight)
                self.assertEqual(h.states(data[2].actors[7])[6744], 6)
                saved = snapshot(data[2])
                restored = Checkpoints._read_snapshot(json.loads(json.dumps(saved)))
                self.assertEqual(
                    restored["native_effect_areas"], saved["native_effect_areas"]
                )
                before = data[2].actors[7].ap
                attack = h.cast(data, 775, data[2].actors[-7].position, action_id=21)
                self.assertLess(attack.fight.actors[7].ap, before)
                self.assertIn(6744, h.states(attack.fight.actors[7]))
                self.assertEqual(
                    (
                        attack.fight.actors[7].max_ap,
                        attack.fight.actors[7].max_mp,
                        attack.fight.actors[7].effect_maxima[4],
                    ),
                    maxima,
                )
                data = h.next_owned_turn(h.adopt(data, attack.fight))
                self.assertNotIn(6744, h.states(data[2].actors[7]))
                self.assertEqual(
                    (
                        data[2].actors[7].max_ap,
                        data[2].actors[7].max_mp,
                        data[2].actors[7].effect_maxima[4],
                    ),
                    maxima,
                )
                fresh = h.fixture(passives=() if passive is None else (passive,))
                self.assertNotIn(6744, h.states(fresh[2].actors[7]))
                self.assertNotIn(6779, h.states(fresh[2].actors[7]))
                self.assertFalse(
                    any(
                        1546 <= row["reference"] <= 1558
                        for row in fresh[2].native_effect_areas.values()
                    )
                )
