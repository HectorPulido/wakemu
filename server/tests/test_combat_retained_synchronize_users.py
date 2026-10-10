"""Container liveness is recomputed from every owned child on each operation."""
import unittest
from types import SimpleNamespace
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_native_container import owned_container_users


class RetainedSynchronizeUsersTests(unittest.TestCase):
    def fixture(self):
        fight = SimpleNamespace(
            actors={},
            owned_stat_effects={},
            native_owned_group_effects={},
            native_owned_area_effects={},
            state_wire_payloads={},
            native_retained_records={},
            native_retained_order=[],
            native_owned_state_containers={},
        )
        runtime = object.__new__(NativeRetainedRuntime)
        runtime.fight = fight
        return runtime, fight

    def test_all_collections_and_next_call_delete_or_reparent_are_fresh(self):
        runtime, fight = self.fixture()
        fight.owned_stat_effects[1] = {"state_uid": 11}
        fight.native_owned_group_effects[2] = {"state_uid": 12}
        fight.native_owned_area_effects[3] = {"state_uid": 13}
        fight.native_owned_state_containers = {uid: {} for uid in (11, 12, 13, 14)}
        runtime.synchronize()
        self.assertEqual(set(fight.native_owned_state_containers), {11, 12, 13})
        del fight.owned_stat_effects[1]
        fight.native_owned_group_effects[2]["state_uid"] = 14
        fight.native_owned_state_containers[14] = {}
        runtime.synchronize()
        self.assertEqual(set(fight.native_owned_state_containers), {13, 14})
        fight.native_owned_area_effects.clear()
        fight.native_owned_group_effects.clear()
        runtime.synchronize()
        self.assertEqual(fight.native_owned_state_containers, {})

    def test_legacy_equality_and_missing_or_unhashable_values_are_preserved(self):
        runtime, fight = self.fixture()
        fight.owned_stat_effects = {
            1: {"state_uid": []},
            2: {},
            3: {"state_uid": 1.0},
            4: {"state_uid": [4]},
            5: {"state_uid": None},
        }
        fight.native_owned_state_containers = {uid: {} for uid in (None, 1, 4, 99)}
        expected = {
            uid
            for uid in fight.native_owned_state_containers
            if owned_container_users(fight, uid)
        }
        runtime.synchronize()
        self.assertEqual(set(fight.native_owned_state_containers), expected)

    def test_removed_child_records_and_order_are_still_pruned(self):
        runtime, fight = self.fixture()
        fight.owned_stat_effects[1] = {"state_uid": 11}
        fight.native_retained_records = {1: {}, 2: {}}
        fight.native_retained_order = [2, 1]
        runtime.synchronize()
        self.assertEqual(fight.native_retained_records, {1: {}})
        self.assertEqual(fight.native_retained_order, [1])


if __name__ == "__main__":
    unittest.main()
