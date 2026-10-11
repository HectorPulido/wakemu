"""Current gift passive combinations control native range and paid costs."""
import os
import unittest
import eliotrope_allied_fixture as allied


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EliotropeGiftCastingRuntimeTests(
    allied.EliotropeAlliedFixture, unittest.TestCase
):
    def test_all_eight_sword_concentration_medium_native_cost_branches(self):
        for sword in (False, True):
            for concentration in (False, True):
                for medium in (False, True):
                    passives = tuple(
                        p
                        for p, yes in (
                            (7208, sword),
                            (7210, concentration),
                            (4689, medium),
                        )
                        if yes
                    )
                    distance = 3 if sword else 4 if concentration else 1
                    ap = 0 if medium else 2
                    wp = 1 if concentration else 2
                    with self.subTest(passives=passives):
                        data = self.allied_fixture(
                            passives=passives,
                            target_distance=2,
                            compact_arena=False,
                            ally_position=(-8 + distance, -7, -1),
                        )
                        tx = self.allied_cast(data, 7813)
                        self.assertEqual(tx.plan["costs"]["ap"], ap)
                        self.assertEqual(tx.plan["costs"]["wp"], wp)
                        self.assertEqual(
                            tx.fight.actors[7].ap, data[2].actors[7].ap - ap
                        )
                        self.assertEqual(
                            tx.fight.actors[8].mp - data[2].actors[8].mp, 2
                        )
                        states = {
                            s.reference for s in tx.fight.actors[8].state_ledger.entries
                        }
                        self.assertIn(7821, states)
                        self.assertIn(7819, states)
                        self.assertNotIn(3671, states)
                        self.assertEqual(
                            tx.fight.actors[7].effect_stats[4],
                            data[2].actors[7].effect_stats[4] - wp,
                        )
                        self.assertEqual(tx.fight.actors[8].ap, data[2].actors[8].ap)
                        self.assertEqual(tx.fight.actors[8].hp, data[2].actors[8].hp)
                        # Native351697 applies7819 to the validated allied PV;
                        # none of these combinations equips the4686 Rabia gate.
                        for reference in (7819, 7821):
                            entries = [
                                state
                                for state in tx.fight.actors[8].state_ledger.entries
                                if state.reference == reference
                            ]
                            self.assertEqual(len(entries), 1)
                            self.assertEqual(
                                (entries[0].level, entries[0].caster_id), (1, 7)
                            )
                        self.assertNotIn(
                            7819,
                            {
                                state.reference
                                for state in tx.fight.actors[7].state_ledger.entries
                            },
                        )
