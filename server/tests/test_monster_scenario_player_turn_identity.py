from types import SimpleNamespace
from unittest.mock import Mock
import unittest

from monster_spell_scenarios import finish_current_turn


class MonsterScenarioPlayerTurnIdentityTests(unittest.TestCase):
    def test_player_end_turn_uses_actor_turn_count_not_global_turn_id(self):
        fight = SimpleNamespace(
            current=SimpleNamespace(id=9, controlled=True, owner_id=12, turn_count=2),
            turn_id=11,
            end_turn=Mock(),
            end_server_turn=Mock(),
        )

        finish_current_turn(fight)

        fight.end_turn.assert_called_once_with(12, 9, 2)
        fight.end_server_turn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
