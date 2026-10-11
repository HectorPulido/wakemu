"""Offline recipes must end uncontrolled actors through the server boundary."""
from types import SimpleNamespace
from unittest.mock import Mock
import unittest
from monster_spell_scenarios import finish_current_turn


class MonsterScenarioActorTurnTests(unittest.TestCase):
    def test_server_actor_uses_owned_server_turn_identity(self):
        fight = SimpleNamespace(
            current=SimpleNamespace(id=-200, controlled=False),
            turn_id=7,
            end_turn=Mock(),
            end_server_turn=Mock(),
        )
        finish_current_turn(fight)
        fight.end_server_turn.assert_called_once_with(-200, 7)
        fight.end_turn.assert_not_called()

    def test_player_actor_uses_actual_owner(self):
        fight = SimpleNamespace(
            current=SimpleNamespace(id=9, controlled=True, owner_id=12),
            turn_id=5,
            end_turn=Mock(),
            end_server_turn=Mock(),
        )
        finish_current_turn(fight)
        fight.end_turn.assert_called_once_with(12, 9, 5)
        fight.end_server_turn.assert_not_called()
