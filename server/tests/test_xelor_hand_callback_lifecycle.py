"""Actual Hand casts retain no one-cast refund listeners across boundaries."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_effect_dispatch import EffectDispatcher


REFUND_LISTENERS = {314209, 412984, 412987, 412981}
REFUND_LEAVES = {314211, 412985, 412988, 412982}


class XelorHandCallbackLifecycleTests(unittest.TestCase):
    def assert_clean(self, fight):
        transient = [
            row
            for row in fight.native_retained_records.values()
            if row["generic_effect"] in REFUND_LISTENERS
        ]
        self.assertEqual(transient, [])

    def test_actual_critical_kill_refunds_once_and_success_cleans_listener(self):
        import test_xelor_runtime_pipeline as helpers

        helper = helpers.XelorRuntimePipelineTests()
        original_fixture = helpers.native_fixture.fixture

        def jalato(*args, **kwargs):
            kwargs.update(monster_reference=1, monster_level=8)
            return original_fixture(*args, **kwargs)

        with patch.object(helpers.native_fixture, "fixture", jalato):
            data = helper.fixture(level=200, actives=(754,))
        before = helpers.snapshot(data[2])
        trace = []
        execute = EffectDispatcher.execute
        prepare = helpers.prepare_server_spell

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if result and invocation.reference in REFUND_LEAVES | {99040}:
                trace.append((invocation.reference, invocation.caster_id))
            return result

        def critical(*args, **kwargs):
            kwargs["critical"] = True
            return prepare(*args, **kwargs)

        with patch.object(helpers, "prepare_server_spell", critical), patch.object(
            EffectDispatcher, "execute", observe
        ):
            tx = helper.cast(data, 754, data[2].actors[-7].position)
        self.assertEqual(tx.fight.actors[-7].hp, 0)
        self.assertEqual(tx.fight.actors[7].ap, 6)
        self.assertEqual([ref for ref, _ in trace if ref in REFUND_LEAVES], [412982])
        self.assertIn((99040, 7), trace)
        self.assert_clean(tx.fight)
        self.assertEqual(helpers.snapshot(data[2]), before)

    def test_successive_nonlethal_casts_and_next_turn_leave_no_kill_listener(self):
        import test_xelor_runtime_pipeline as helpers

        helper = helpers.XelorRuntimePipelineTests()
        data = helper.fixture(level=20, actives=(754,))
        for action_id, expected_ap in ((3, 2), (4, 0)):
            before = helpers.snapshot(data[2])
            tx = helper.cast(
                data, 754, data[2].actors[-7].position, action_id=action_id
            )
            self.assertGreater(tx.fight.actors[-7].hp, 0)
            self.assertEqual(tx.fight.actors[7].ap, expected_ap)
            self.assert_clean(tx.fight)
            self.assertEqual(helpers.snapshot(data[2]), before)
            data = helper.adopt(data, tx.fight)
        data = helper.next_owned_turn(data)
        self.assertEqual(data[2].current.id, 7)
        self.assertEqual(data[2].actors[7].ap, 6)
        self.assert_clean(data[2])
        tx = helper.cast(data, 754, data[2].actors[-7].position, action_id=30)
        self.assertEqual(tx.fight.actors[7].ap, 2)
        self.assert_clean(tx.fight)


class HandCleanupOwnerIsolationTests(unittest.TestCase):
    def test_exact_listener_removal_is_scoped_to_manager_not_foreign_owner(self):
        from wakfu_server.combat_dispel import NativeDispelHandler
        from wakfu_server.combat_retained_effects import RetainedEffect

        entries = (
            RetainedEffect(101, 7, 330, 412981, manager_id=7),
            RetainedEffect(102, 8, 330, 412981, manager_id=8),
            # A triggering target may differ from the retained manager.
            RetainedEffect(103, 7, 330, 412981, manager_id=8),
            RetainedEffect(104, 7, 330, 412987, manager_id=7),
        )
        view = SimpleNamespace(
            entries=entries, fight=SimpleNamespace(actors={7: 1, 8: 1})
        )
        removed = []
        removal = SimpleNamespace(view=view, remove=lambda ids: removed.extend(ids))
        handler = NativeDispelHandler(
            view_provider=lambda: view, removal_provider=lambda actual: removal
        )
        handler._apply({"parameters": [412981]}, SimpleNamespace(target_id=7))
        self.assertEqual(removed, [101])


if __name__ == "__main__":
    unittest.main()
