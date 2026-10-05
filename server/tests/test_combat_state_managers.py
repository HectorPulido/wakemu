import copy, unittest
from types import SimpleNamespace
from wakfu_server.combat_state_ledger import StateLedger, RunningState
from wakfu_server.combat_state_managers import state_manager, state_managers
from wakfu_server.combat_native_container import resolve_state_container
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.combat_range_conditions import area_state_count


class StateManagerTests(unittest.TestCase):
    def fixture(self):
        row = dict(
            uid=901,
            reference=1477,
            cell=(2, 3, 4),
            native_area_contract="faY",
            native_running_effect_manager=True,
            state_ledger=StateLedger(901),
        )
        fighter = SimpleNamespace(id=7, state_ledger=StateLedger(7))
        return SimpleNamespace(actors={7: fighter}, native_effect_areas={901: row})

    def test_area_qf_owns_states_without_fighter_resources(self):
        fight = self.fixture()
        state = RunningState(
            1001, 6339, 1, 7, 901, -1, "target", False, (), 0, True, None
        )
        fight.native_effect_areas[901]["state_ledger"]._entries = (state,)
        manager = state_manager(fight, 901)
        self.assertEqual(manager.position, (2, 3, 4))
        self.assertFalse(hasattr(manager, "hp"))
        self.assertEqual(tuple(x.id for x in state_managers(fight)), (7, 901))
        self.assertIs(resolve_state_container(fight, 1001), state)
        self.assertEqual(set(fight.actors), {7})
        preview = copy.deepcopy(fight)
        state_manager(preview, 901).state_ledger.remove(1001)
        self.assertEqual(len(manager.state_ledger.entries), 1)
        self.assertNotEqual(snapshot(preview), snapshot(fight))

    def test_qf_null_is_known_absence_and_not_generated(self):
        fight = self.fixture()
        row = fight.native_effect_areas[901]
        row["native_running_effect_manager"] = False
        del row["state_ledger"]
        self.assertIsNone(state_manager(fight, 901))
        self.assertEqual(tuple(x.id for x in state_managers(fight)), (7,))

    def test_native_area_state_range_has_no_fighter_inplay_filter(self):
        rows = (((2, 3, 8), ((6339, 1, 7),)),)
        args = dict(center=(0, 3, 0), minimum=2, maximum=2, reference=6339, caster=7)
        self.assertEqual(area_state_count(rows, **args), 1)
        self.assertEqual(area_state_count(rows, **dict(args, caster=8)), 0)
        self.assertEqual(area_state_count(rows, **dict(args, minimum=99, maximum=0)), 1)

    def test_unregister_area_preserves_actual_qf_until_owned_state_removed(self):
        from wakfu_server.combat_effect_area import remove_owned_hour_area
        from wakfu_server.combat_state_managers import prune_retired_state_managers
        from wakfu_server.combat_effect_area_queries import _rows

        fight = self.fixture()
        ledger = fight.native_effect_areas[901]["state_ledger"]
        state = RunningState(
            1001, 6339, 1, 7, 901, -1, "target", False, (), 0, True, None
        )
        ledger._entries = (state,)
        remove_owned_hour_area(fight, 901)
        self.assertEqual(_rows(fight), ())
        self.assertIs(resolve_state_container(fight, 1001), state)
        self.assertNotIn(901, fight.actors)
        prune_retired_state_managers(fight)
        self.assertIn(901, fight.native_retired_area_managers)
        ledger.remove(1001)
        prune_retired_state_managers(fight)
        self.assertNotIn(901, fight.native_retired_area_managers)
