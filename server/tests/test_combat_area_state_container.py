"""An actual retained area runner keeps its original state PL alive."""
import unittest
from types import SimpleNamespace
from wakfu_server.combat_state_ledger import StateLedger, RunningState
from wakfu_server.combat_native_container import (
    capture_owned_state_container,
    owned_state_container,
    owned_container_users,
)


class AreaStateContainerTests(unittest.TestCase):
    def test_area_only_child_captures_and_preserves_actual_parent_after_removal(self):
        ledger = StateLedger(7)
        state = RunningState(21, 3442, 1, 7, 7, -1, "target", False, (), 0, True, None)
        ledger._entries = (state,)
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(id=7, state_ledger=ledger)},
            owned_stat_effects={},
            native_owned_group_effects={},
            native_owned_area_effects={22: {"state_uid": 21}},
            native_owned_state_containers={},
            native_effect_areas={},
        )
        self.assertEqual(owned_container_users(fight, 21), (22,))
        capture_owned_state_container(fight, 21)
        ledger.remove(21)
        self.assertEqual(owned_state_container(fight, 21), state)
        del fight.native_owned_area_effects[22]
        with self.assertRaisesRegex(ValueError, "Missing unique"):
            owned_state_container(fight, 21)

    def test_unrelated_area_does_not_authorize_parent_snapshot(self):
        ledger = StateLedger(7)
        ledger._entries = (
            RunningState(21, 3442, 1, 7, 7, -1, "target", False, (), 0, True, None),
        )
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(id=7, state_ledger=ledger)},
            owned_stat_effects={},
            native_owned_group_effects={},
            native_owned_area_effects={22: {"state_uid": 99}},
            native_owned_state_containers={},
            native_effect_areas={},
        )
        with self.assertRaisesRegex(ValueError, "Missing actual"):
            capture_owned_state_container(fight, 21)
        self.assertFalse(fight.native_owned_state_containers)
