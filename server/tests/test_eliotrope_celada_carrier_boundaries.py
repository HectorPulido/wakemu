"""Actual gift-carrier ownership across attacks, turn and interruption boundary."""
import os
import unittest
from copy import deepcopy
from unittest.mock import patch
import test_celada_second_attack_lifetime as pipeline
from wakfu_server.combat_runtime_messages import RuntimeMessages


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class CeladaCarrierBoundaryTests(unittest.TestCase):
    def test_carrier_stays_recipient_owned_across_consumption_turn_and_fight_exit(self):
        pipeline.suite.setUpClass()
        original = pipeline.suite.allied_cast
        captured, successful = [], []

        def capture(data, reference, *args, **kwargs):
            tx = original(data, reference, *args, **kwargs)
            if reference == 4692 and kwargs.get("actor_id") == 7:
                successful.append(tx)
                if len(successful) % 2 == 0:
                    captured.append((*data[:2], tx.fight, *data[3:]))
            return tx

        with patch.object(pipeline.suite, "allied_cast", capture):
            rows = pipeline.run_cases()
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(captured), 4)
        for row, data in zip(rows, captured):
            with self.subTest(back=row["back"], passive=row["passive"]):
                self.assertNotIn("error", row["result"], row)
                self.assertEqual(
                    row["result"]["second_damage"], 122 if row["back"] else 98
                )
                fight = data[2]
                entries = [
                    e
                    for e in fight.actors[8].state_ledger.entries
                    if e.reference == 3671
                ]
                self.assertEqual(len(entries), 1)
                carrier = entries[0]
                self.assertEqual(
                    (
                        carrier.caster_id,
                        carrier.target_id,
                        carrier.level,
                        carrier.duration,
                    ),
                    (7, 8, 1, -1),
                )
                self.assertFalse(
                    any(
                        e.reference == 3671
                        for e in fight.actors[7].state_ledger.entries
                    )
                )
                uid = carrier.uid
                pipeline.suite.advance_to(data, 8)
                after = [
                    e
                    for e in fight.actors[8].state_ledger.entries
                    if e.reference == 3671
                ]
                self.assertEqual(
                    [(e.uid, e.caster_id, e.target_id, e.duration) for e in after],
                    [(uid, 7, 8, -1)],
                )
                # Actual interrupted-fight protocol boundary ends this Fight;
                # it does not pretend the infinite native carrier timed out.
                ledger_before = deepcopy(fight.actors[8].state_ledger.entries)
                packets = RuntimeMessages(fight).interrupted_cleanup(7)
                self.assertEqual(fight.phase, "finished")
                self.assertIn(12238, [opcode for opcode, _ in packets])
                self.assertEqual(fight.actors[8].state_ledger.entries, ledger_before)
                fresh = pipeline.suite.allied_fixture(
                    passives=(4686, 4687) if row["passive"] else (4686,),
                    ally_spells=(4785,),
                    target_distance=2,
                )
                self.assertFalse(
                    any(
                        e.reference == 3671
                        for actor in fresh[2].actors.values()
                        for e in actor.state_ledger.entries
                    )
                )
                self.assertIsNot(
                    fresh[2].actors[8].state_ledger, fight.actors[8].state_ledger
                )
