import unittest
from types import SimpleNamespace

from wakfu_server.combat_test_commands import finish


class Fight(SimpleNamespace):
    def _event(self, kind, **values):
        self.events.append(dict(kind=kind, **values))


class CombatTestCommandsTests(unittest.TestCase):
    def setUp(self):
        self.fight = Fight(
            phase="active",
            winner=None,
            events=[],
            actors={
                1: SimpleNamespace(id=1, team=0, controlled=True, owner_id=10, hp=50),
                2: SimpleNamespace(id=2, team=0, controlled=True, owner_id=10, hp=30),
                3: SimpleNamespace(id=3, team=0, controlled=True, owner_id=20, hp=25),
                4: SimpleNamespace(
                    id=4, team=1, controlled=False, owner_id=None, hp=90
                ),
            },
        )
        self.runtime = SimpleNamespace(fight=self.fight, awaiting_ack=7)

    def outcome(self, win):
        return finish(self.fight, self.runtime, account_id=10, character_id=1, win=win)

    def test_victory_preserves_heroes_and_teammates_and_input_state(self):
        result = self.outcome(True)
        self.assertEqual(result.fight.winner, 0)
        self.assertEqual(result.fight.phase, "finished")
        self.assertEqual(
            [result.fight.actors[i].hp for i in (1, 2, 3, 4)], [50, 30, 25, 0]
        )
        self.assertEqual(self.fight.phase, "active")
        self.assertEqual(self.fight.actors[4].hp, 90)
        self.assertIs(result.runtime.fight, result.fight)
        self.assertEqual(result.packets, ())  # Normal finish owns terminal packets.

    def test_defeat_affects_the_whole_team_including_heroes(self):
        result = self.outcome(False)
        self.assertEqual(result.fight.winner, 1)
        self.assertEqual(
            [result.fight.actors[i].hp for i in (1, 2, 3, 4)], [0, 0, 0, 90]
        )
        self.assertEqual(result.fight.events, [{"kind": "finished", "winner": 1}])

    def test_foreign_owner_cannot_force_outcome(self):
        with self.assertRaises(ValueError):
            finish(self.fight, self.runtime, account_id=99, character_id=1, win=True)
        self.assertEqual(self.fight.events, [])

    def test_placement_and_unsettled_finished_fights_can_be_finished(self):
        for phase in ("placement", "finished"):
            with self.subTest(phase=phase):
                self.fight.phase = phase
                result = self.outcome(True)
                self.assertEqual(result.fight.phase, "finished")
                self.assertEqual(result.fight.winner, 0)

    def test_withdrawn_character_cannot_finish_remaining_fight(self):
        self.fight.actors[1].pve_withdrawn = True
        with self.assertRaises(ValueError):
            self.outcome(True)

    def test_no_fight_rejected(self):
        with self.assertRaises(ValueError):
            finish(None, None, account_id=10, character_id=1, win=True)

    def test_rift_forced_win_closes_administratively_without_invented_turns(self):
        self.fight.rift_wave_state = dict(
            instance_id=99, turn_budget=40, wave=3, pending_wave=None
        )
        self.fight.native_timeline_round = 7
        result = self.outcome(True)
        self.assertEqual(result.fight.winner, 0)
        self.assertEqual(result.fight.phase, "finished")
        self.assertEqual(
            result.fight.rift_wave_state["outcome"], "administrative_victory"
        )
        self.assertEqual(result.fight.native_timeline_round, 7)
        self.assertNotIn("outcome", self.fight.rift_wave_state)
        lost = self.outcome(False)
        self.assertEqual(lost.fight.winner, 1)
        self.assertEqual(lost.fight.rift_wave_state, self.fight.rift_wave_state)

    def test_repeating_same_finished_outcome_does_not_duplicate_terminal_event(self):
        terminal = self.outcome(True)
        again = finish(
            terminal.fight, terminal.runtime, account_id=10, character_id=1, win=True
        )
        self.assertEqual(again.fight.events, terminal.fight.events)
