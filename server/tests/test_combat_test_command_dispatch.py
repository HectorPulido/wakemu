"""Operator outcomes must use the live shared dispatcher's transition identity."""
import unittest
from types import SimpleNamespace

from wakfu_server.combat.combat_test_commands import finish
from wakfu_server.combat_shared import Registry, Transition


class Fight(SimpleNamespace):
    def _event(self, kind, **values):
        self.events.append(dict(kind=kind, **values))


class CombatTestCommandDispatchTests(unittest.TestCase):
    def test_win_and_loss_replace_the_live_registry_state(self):
        for win in (True, False):
            with self.subTest(win=win):
                fight = Fight(
                    phase="active",
                    winner=None,
                    events=[],
                    actors={
                        1: SimpleNamespace(controlled=True, owner_id=10, team=0, hp=50),
                        2: SimpleNamespace(
                            controlled=False, owner_id=None, team=1, hp=90
                        ),
                    },
                )
                runtime = SimpleNamespace(fight=fight)
                terminal = finish(
                    fight, runtime, account_id=10, character_id=1, win=win
                )
                self.assertIsInstance(terminal, Transition)
                candidate, messages, packets = Registry._transition(
                    terminal, fight, runtime
                )
                self.assertIs(candidate, terminal.fight)
                self.assertIs(messages.fight, candidate)
                self.assertEqual(candidate.phase, "finished")
                self.assertEqual(candidate.winner, 0 if win else 1)
                self.assertEqual(packets, ())
                self.assertEqual(fight.phase, "active")


if __name__ == "__main__":
    unittest.main()
