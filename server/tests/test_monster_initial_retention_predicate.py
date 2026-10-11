"""Constructor receipt carrier counts use the production native predicate."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import validate_monster_spell_activation as validation


class InitialRetentionPredicateTests(unittest.TestCase):
    def test_permanent_flag_changes_negative_turn_clock_retention(self):
        profiles = {
            1: dict(duration=-1, realtime_duration=0, skip_turn_timer=True),
            2: dict(duration=-1, realtime_duration=0, skip_turn_timer=False),
            3: dict(duration=0, realtime_duration=-1, skip_turn_timer=True),
            4: dict(duration=0, realtime_duration=0, skip_turn_timer=False),
        }
        plan = tuple(SimpleNamespace(state_id=i, level=1) for i in profiles)
        with patch(
            "wakfu_server.combat_summon_initial_states.initial_state_plan",
            return_value=plan,
        ), patch(
            "wakfu_server.combat_server_spell.states_catalog", return_value={}
        ), patch(
            "wakfu_server.combat_definitions.state_profile",
            side_effect=lambda catalog, state_id, level: profiles[state_id],
        ):
            self.assertEqual(
                validation.nonretained_initial_states([1, 1, 0], 98), [1, 4]
            )
