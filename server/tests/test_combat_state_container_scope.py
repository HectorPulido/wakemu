"""The synchronous Qe fyW container survives removal; stale event UIDs do not."""
import unittest
from types import SimpleNamespace
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_effect_dispatch import EffectInvocation


class StateContainerScopeTests(unittest.TestCase):
    def setUp(self):
        self.old = SimpleNamespace(uid=219, reference=3442, level=14)
        self.new = SimpleNamespace(uid=220, reference=3442, level=15)
        self.ledger = SimpleNamespace(entries=[self.old])
        self.runtime = object.__new__(NativeRetainedRuntime)
        self.runtime.fight = SimpleNamespace(
            actors={7: SimpleNamespace(state_ledger=self.ledger)}
        )
        self.runtime._container_scopes = []
        self.invocation = EffectInvocation(150327, 14, 7, 7, (0, 0, 0), state_uid=219)

    def test_replaced_container_keeps_original_level_until_call_returns(self):
        with self.runtime.container_scope(self.invocation):
            self.ledger.entries = [self.new]
            self.assertEqual(
                self.runtime.container(self.invocation)[1], (3442 << 16) | 14
            )
            with self.runtime.container_scope(self.invocation):
                self.assertEqual(
                    self.runtime.container(self.invocation)[1], (3442 << 16) | 14
                )
        self.assertEqual(self.runtime._container_scopes, [])
        with self.assertRaisesRegex(ValueError, "Missing unique"):
            self.runtime.container(self.invocation)
        with self.assertRaisesRegex(ValueError, "Missing unique"):
            with self.runtime.container_scope(self.invocation):
                self.fail("stale UID outside native call must reject")

    def test_unknown_or_ambiguous_container_still_rejects_and_failure_closes_scope(
        self,
    ):
        self.ledger.entries = [self.old, self.old]
        with self.assertRaisesRegex(ValueError, "Missing unique"):
            with self.runtime.container_scope(self.invocation):
                pass
        self.ledger.entries = [self.old]
        with self.assertRaisesRegex(RuntimeError, "mandatory failure"):
            with self.runtime.container_scope(self.invocation):
                self.ledger.entries = []
                raise RuntimeError("mandatory failure")
        self.assertEqual(self.runtime._container_scopes, [])
        with self.assertRaisesRegex(ValueError, "Missing unique"):
            self.runtime.container(self.invocation)

    def test_actual_applied_instant_entry_is_bound_for_entire_child_iterator(self):
        from wakfu_server.combat_state_ledger import RunningState

        entry = RunningState(
            219, 3442, 14, 7, 7, 0, "target", False, (), 0, False, None
        )
        self.ledger.entries = []
        with self.runtime.applied_state_scope(entry):
            with self.runtime.container_scope(self.invocation):
                self.assertEqual(
                    self.runtime.container(self.invocation)[1], (3442 << 16) | 14
                )
            # A sibling child has its own wrapper, while the native fyW iterator
            # remains active after the earlier child's state replacement.
            with self.runtime.container_scope(self.invocation):
                self.assertEqual(
                    self.runtime.container(self.invocation)[1], (3442 << 16) | 14
                )
        with self.assertRaisesRegex(ValueError, "Missing unique"):
            self.runtime.container(self.invocation)

    def test_damage_authority_uses_same_scoped_fyw_and_isolates_other_fight(self):
        from wakfu_server.combat_ordinary_authority import ordinary_container_type
        from wakfu_server.combat_native_container import resolve_state_container

        with self.runtime.container_scope(self.invocation):
            self.ledger.entries = [self.new]
            self.assertEqual(
                ordinary_container_type(self.runtime.fight, {}, self.invocation), 3
            )
            self.assertIs(resolve_state_container(self.runtime.fight, 219), self.old)
            other = SimpleNamespace(actors={})
            with self.assertRaisesRegex(ValueError, "Missing unique"):
                resolve_state_container(other, 219)
        with self.assertRaisesRegex(ValueError, "Missing unique"):
            ordinary_container_type(self.runtime.fight, {}, self.invocation)

    def test_direct_container_declared_type_matches_retention_contract(self):
        from wakfu_server.combat_ordinary_authority import ordinary_container_type

        invocation = EffectInvocation(150327, 14, 7, 7, (0, 0, 0))
        self.assertEqual(
            ordinary_container_type(
                self.runtime.fight,
                {"native_retained_container": {"present": True, "type": 25}},
                invocation,
            ),
            25,
        )
