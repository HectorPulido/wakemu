"""Actual Milky Instinct barrel countdown ends in its source kill branch."""
import os
import unittest
import test_combat_pandawa_runtime as helper


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class PandawaMilkyInstinctRuntimeTests(unittest.TestCase):
    fixture = helper.PandawaRuntimeTests.fixture
    cast = helper.PandawaRuntimeTests.cast
    next_owned_turn = helper.PandawaRuntimeTests.next_owned_turn

    def test_actual_barrel_countdown_kills_only_with_milky_instinct(self):
        from wakfu_server.combat_qi_fight import current_registry

        for passive in (None, 4726):
            with self.subTest(passive=passive):
                fixture = self.fixture(() if passive is None else (passive,))
                created = self.cast(fixture, 4718)
                fixture = (*fixture[:2], created.fight, *fixture[3:])
                barrel = next(
                    a
                    for a in created.fight.actors.values()
                    if getattr(a, "native_summon_source", None)
                )
                states = {e.reference: e.level for e in barrel.state_ledger.entries}
                self.assertEqual(9356 in states, passive == 4726)
                if passive == 4726:
                    self.assertEqual(states[9356], 3)
                self.assertGreater(barrel.hp, 0)
                for _ in range(3):
                    fixture = self.next_owned_turn(fixture)
                result = fixture[2].actors[barrel.id]
                if passive == 4726:
                    self.assertEqual(result.hp, 0)
                    self.assertEqual(result.native_obstacle_id, -1)
                else:
                    self.assertGreater(result.hp, 0)
                current_registry(fixture[2])
