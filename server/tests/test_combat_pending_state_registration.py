import unittest
from dataclasses import asdict
from types import SimpleNamespace
from wakfu_server.combat_pending_state import (
    pending_state_registration,
    pending_state_uids,
)
from wakfu_server.combat_retained_runtime import native_retained_condition_effects
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_state_ledger import RunningState
from wakfu_server.combat_stat_effects import owned_effect_payload
from wakfu_server.combat_effects import _integer


class PendingStateRegistrationTests(unittest.TestCase):
    def fixture(self):
        state = RunningState(101, 3442, 1, 7, 7, 2, "target", False, (), 0, True, None)
        actor = SimpleNamespace(id=7, state_ledger=SimpleNamespace(entries=(state,)))
        entry = RetainedEffect(100, 7, 400, 308265, manager_id=7)
        fight = SimpleNamespace(
            actors={7: actor},
            native_retained_tracking=True,
            owned_stat_effects={
                100: {
                    "payload": owned_effect_payload(
                        uid=100,
                        base_uid=None,
                        generic_effect=308265,
                        caster_id=7,
                        target_id=7,
                        value=0,
                    ).hex(),
                    "target_id": 7,
                    "effect_class": 400,
                }
            },
            state_wire_payloads={
                101: (
                    _integer(1, 101)
                    + _integer(2, 101)
                    + _integer(3, -1)
                    + _integer(6, 7)
                    + _integer(7, 7)
                ).hex()
            },
            native_owned_group_effects={},
            native_retained_records={100: asdict(entry)},
            native_retained_order=[100],
        )
        return fight, state

    def test_child_sees_actual_qf_before_carrier_registration(self):
        fight, state = self.fixture()
        with self.assertRaises(ValueError):
            native_retained_condition_effects(fight, 7)
        with pending_state_registration(fight, state):
            self.assertEqual(pending_state_uids(fight), frozenset({101}))
            self.assertEqual(
                native_retained_condition_effects(fight, 7), ((308265, 400, 100),)
            )
            # An unrelated unregistered effect cannot be hidden by this scope.
            fight.owned_stat_effects[999] = {}
            with self.assertRaises(ValueError):
                native_retained_condition_effects(fight, 7)
            del fight.owned_stat_effects[999]
        self.assertEqual(pending_state_uids(fight), frozenset())
        with self.assertRaises(ValueError):
            native_retained_condition_effects(fight, 7)

    def test_pending_authority_is_owned_identity_isolated_and_exception_safe(self):
        fight, state = self.fixture()
        other, _ = self.fixture()
        with pending_state_registration(fight, state):
            self.assertFalse(pending_state_uids(other))
        fake = RunningState(101, 3442, 1, 7, 7, 2, "target", False, (), 0, True, None)
        with self.assertRaises(ValueError):
            with pending_state_registration(fight, fake):
                pass
        with self.assertRaises(RuntimeError):
            with pending_state_registration(fight, state):
                raise RuntimeError("rollback")
        self.assertFalse(pending_state_uids(fight))

    def test_runtime_registers_carrier_only_after_iterator_and_keeps_complete_view(
        self,
    ):
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        fight, state = self.fixture()
        runtime = object.__new__(NativeRetainedRuntime)
        runtime.fight = fight
        runtime.plan = {"native_retained_container": {"present": False}}
        runtime._carrier_parents = [EffectInvocation(1, 1, 7, 7, (0, 0, 0))]
        runtime._container_scopes = []
        runtime.metadata = {
            "states": {"3442": {"unremovable": False, "dispellable": True}}
        }
        with runtime.applied_state_scope(state):
            self.assertEqual(
                native_retained_condition_effects(fight, 7), ((308265, 400, 100),)
            )
            self.assertNotIn(101, fight.native_retained_records)
            self.assertEqual([e.uid for e in runtime.view().entries], [100])
        self.assertEqual(
            native_retained_condition_effects(fight, 7),
            ((308265, 400, 100), (-1, 310, 101)),
        )
        self.assertEqual(fight.native_retained_order, [100, 101])
        self.assertFalse(pending_state_uids(fight))

    def test_child_owner_can_reference_only_trusted_pending_carrier(self):
        fight, state = self.fixture()
        fight.owned_stat_effects[100]["state_uid"] = 101
        fight.native_retained_records[100]["owner_uid"] = 101
        with pending_state_registration(fight, state):
            self.assertEqual(
                native_retained_condition_effects(fight, 7), ((308265, 400, 100),)
            )
            fight.owned_stat_effects[100]["state_uid"] = 999
            fight.native_retained_records[100]["owner_uid"] = 999
            with self.assertRaises(ValueError):
                native_retained_condition_effects(fight, 7)
