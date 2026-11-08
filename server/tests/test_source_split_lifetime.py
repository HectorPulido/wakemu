"""Calculated-source ownership without changing live continuation semantics."""
from copy import deepcopy
import gc
from itertools import count
import unittest
import weakref

from wakfu_server.combat_damage_handler import (
    NativeDamageHandler,
    DamageExecutionContext,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_source_split import (
    NativeCalculatedDamageCloneAuthority,
    bind_calculated_damage_clone,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount


def rng():
    return 0.99


def gate(*args):
    return False


def context(*args):
    return DamageExecutionContext(False, True, False, True, 11, False)


class SourceSplitLifetimeTests(unittest.TestCase):
    def source(self):
        actors = [
            Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, 3, True),
            Actor(-7, 1, (1, 0, 0), 100, 6, 3, 5, 1),
        ]
        fight = Fight(
            77, actors, {(0, 0, 0), (1, 0, 0)}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        )
        handler = NativeDamageHandler(
            fight,
            [],
            action_id=1,
            allocate_uid=count(102).__next__,
            rng=rng,
            context=context,
        )
        handler.calculated_clone_gate = gate
        invocation = EffectInvocation(
            339483, 1, 7, -7, (1, 0, 0), native_running_uid=101
        )
        runner = NativeRunnerAmount(101, 1, rng=rng, value=100)
        bind_calculated_damage_clone(
            handler, {"effect_class": 1}, invocation, context(), {}, runner
        )
        return runner

    def test_attached_release_copies_and_independent_prepared_continuation(self):
        enabled = gc.isenabled()
        gc.disable()
        try:
            runner = self.source()
            authority = runner.native_calculated_clone
            self.assertIs(authority.runner, runner)
            copied = deepcopy(runner)
            self.assertIs(copied.native_calculated_clone.runner, copied)
            self.assertIsNot(
                copied.native_calculated_clone.handler.fight, authority.handler.fight
            )
            clone_refs = tuple(
                weakref.ref(x)
                for x in (
                    copied,
                    copied.native_calculated_clone,
                    copied.native_calculated_clone.handler.fight,
                )
            )
            del copied
            self.assertTrue(all(reference() is None for reference in clone_refs))

            standalone_copy = deepcopy(authority)
            self.assertIs(
                standalone_copy.runner.native_calculated_clone, standalone_copy
            )
            self.assertEqual(standalone_copy.runner.value, 100)
            del standalone_copy

            # An actual prepared clone owns its handler even after its source
            # disappears; rejecting that clone must still clean its UID state.
            prepared = authority.prepare(caster_id=7, target_id=-7, amount=25)
            uid = prepared.uid
            refs = tuple(weakref.ref(x) for x in (runner, authority))
            fight_ref = weakref.ref(authority.handler.fight)
            del authority, runner
            self.assertTrue(all(reference() is None for reference in refs))
            self.assertIsNotNone(fight_ref())
            self.assertFalse(prepared.execute())
            self.assertNotIn(uid, prepared.handler.prepared)
            self.assertNotIn(uid, prepared.handler.runner_modifiers)
            del prepared
            self.assertIsNone(fight_ref())

            observed = self.source()
            observer = observed.native_calculated_clone
            observed_ref = weakref.ref(observed)
            del observed
            self.assertIsNone(observed_ref())
            with self.assertRaisesRegex(ReferenceError, "runner has expired"):
                observer.prepare(caster_id=7, target_id=-7, amount=10)
            del observer

            # Standalone construction and standalone copying retain a usable
            # source; this conservative compatibility path is not the hot path.
            runner = self.source()
            attached = runner.native_calculated_clone
            standalone = NativeCalculatedDamageCloneAuthority(
                attached.handler,
                attached.effect,
                attached.invocation,
                attached.context,
                attached.interpreted,
                runner,
                attached.modifier,
            )
            runner_ref = weakref.ref(runner)
            del attached, runner
            self.assertIs(standalone.runner, runner_ref())
            copied_authority = deepcopy(standalone)
            self.assertEqual(copied_authority.runner.uid, 101)
            self.assertIsNot(copied_authority.runner, standalone.runner)
            self.assertFalse(
                copied_authority.prepare(caster_id=7, target_id=-7, amount=10).execute()
            )
        finally:
            if enabled:
                gc.enable()


if __name__ == "__main__":
    unittest.main()
