import unittest
from dataclasses import asdict
from types import SimpleNamespace
from wakfu_server.combat_native_container import (
    state_container_scope,
    capture_owned_state_container,
    resolve_state_container,
)
from wakfu_server.combat_state_ledger import RunningState
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_stat_effects import owned_effect_payload
from wakfu_server.combat_retained_runtime import (
    native_retained_condition_effects,
    NativeRetainedRuntime,
)


class OwnedStateContainerTests(unittest.TestCase):
    def fixture(self):
        state = RunningState(217, 4146, 1, 7, 7, 0, "target", False, (), 0, False, None)
        row = {
            "state_uid": 217,
            "target_id": 7,
            "effect_class": 193,
            "payload": owned_effect_payload(
                uid=220,
                base_uid=None,
                generic_effect=361069,
                caster_id=7,
                target_id=7,
                value=1,
            ).hex(),
        }
        meta = RetainedEffect(
            220,
            7,
            193,
            361069,
            owner_uid=217,
            manager_id=7,
            container_present=True,
            container_type=1,
        )
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(id=7, state_ledger=SimpleNamespace(entries=()))},
            native_owned_state_containers={},
            owned_stat_effects={220: row},
            native_owned_group_effects={},
            state_wire_payloads={},
            native_retained_tracking=True,
            native_retained_records={220: asdict(meta)},
            native_retained_order=[220],
        )
        return fight, state

    def test_actual_instant_pl_remains_owned_by_retained_child_without_qf_carrier(self):
        fight, state = self.fixture()
        with self.assertRaises(ValueError):
            native_retained_condition_effects(fight, 7)
        with state_container_scope(fight, {217: state}):
            capture_owned_state_container(fight, 217)
        self.assertEqual(resolve_state_container(fight, 217), state)
        self.assertEqual(
            native_retained_condition_effects(fight, 7), ((361069, 193, 220),)
        )
        self.assertNotIn(217, fight.native_retained_records)
        self.assertEqual(fight.native_retained_order, [220])
        del fight.owned_stat_effects[220]
        with self.assertRaises(ValueError):
            resolve_state_container(fight, 217)
        runtime = object.__new__(NativeRetainedRuntime)
        runtime.fight = fight
        runtime.synchronize()
        self.assertEqual(fight.native_owned_state_containers, {})

    def test_unknown_or_unowned_fact_never_restores_stale_container(self):
        fight, state = self.fixture()
        with self.assertRaises(ValueError):
            capture_owned_state_container(fight, 217)
        fight.native_owned_state_containers[217] = asdict(state)
        fight.native_owned_state_containers[217]["uid"] = 999
        with self.assertRaises(ValueError):
            resolve_state_container(fight, 217)
        fight.native_owned_state_containers[217] = asdict(state)
        fight.native_retained_records[220]["container_type"] = 11
        with self.assertRaises(ValueError):
            native_retained_condition_effects(fight, 7)
