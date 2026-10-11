"""Finite turn advancement uses real lifecycle calls without changing resources."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_spell_scenarios import advance_to


class MonsterScenarioTurnTests(unittest.TestCase):
    def test_advancement_uses_current_actor_and_native_turn_identity(self):
        class Fight:
            actors = {7: object(), -200: object()}
            current = SimpleNamespace(id=7)
            turn_id = 19
            calls = []

            def end_turn(self, request, actor, turn):
                self.calls.append((request, actor, turn))
                self.current = SimpleNamespace(id=-200)
                self.turn_id += 1

        fight = Fight()
        advance_to(fight, -200)
        self.assertEqual(fight.calls, [(3, 7, 19)])
        advance_to(fight, -200)
        self.assertEqual(fight.calls, [(3, 7, 19)])

    def test_unavailable_turn_does_not_loop_indefinitely(self):
        class Fight:
            actors = {7: object()}
            current = SimpleNamespace(id=7)
            turn_id = 19
            calls = 0

            def end_turn(self, request, actor, turn):
                self.calls += 1

        fight = Fight()
        with self.assertRaisesRegex(ValueError, "could not establish"):
            advance_to(fight, -200)
        self.assertEqual(fight.calls, 3)


if __name__ == "__main__":
    unittest.main()
