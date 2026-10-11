"""Xelor Tic/Tac transitions use real end/ACK/start boundaries."""
import os
import unittest
import test_combat_xelor_passive_semantics_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class XelorTickTockRuntimeTests(unittest.TestCase):
    fixture = helpers.XelorPassiveSemanticsRuntimeTests.fixture

    @staticmethod
    def states(fight):
        return {
            entry.reference: entry.level
            for entry in fight.actors[7].state_ledger.entries
        }

    def test_three_owned_tick_tock_passives_initialize_and_alternate_with_real_turns(
        self,
    ):
        from test_combat_pandawa_runtime import PandawaRuntimeTests

        baseline = self.fixture()
        self.assertFalse({6771, 6772} & set(self.states(baseline[2])))
        for passive in (764, 5353, 7184):
            with self.subTest(passive=passive):
                data = self.fixture((passive,))
                self.assertEqual(self.states(data[2]).get(6771), 1)
                self.assertNotIn(6772, self.states(data[2]))
                data = PandawaRuntimeTests.next_owned_turn(self, data)
                self.assertEqual(self.states(data[2]).get(6772), 1)
                self.assertNotIn(6771, self.states(data[2]))
                data = PandawaRuntimeTests.next_owned_turn(self, data)
                self.assertEqual(self.states(data[2]).get(6771), 1)
                self.assertNotIn(6772, self.states(data[2]))
