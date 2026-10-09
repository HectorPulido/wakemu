import copy
from dataclasses import replace
from types import SimpleNamespace
import unittest
from wakfu_server.combat_disabled_spell_level import (
    NativeDisabledSpellLevelHandler,
    remove_disabled_spell_level,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext


class DisabledSpellLevelTests(unittest.TestCase):
    def fixture(self, *, retained=True, executable=True):
        actor = SimpleNamespace(
            id=1, hp=100, spell_levels={4678: 25}, native_controlled_by_ai=False
        )
        fight = SimpleNamespace(
            id=4, phase="active", actors={1: actor}, owned_stat_effects={}
        )
        packets, phases = [], []
        handler = NativeDisabledSpellLevelHandler(
            fight,
            packets,
            action_id=5,
            allocate_uid=lambda: 101,
            context=lambda *args: StatExecutionContext(
                executable, True, None, retained, b"", None
            ),
            rng=lambda: 0,
        )

        class Events:
            def phase(self, effect, invocation, **kwargs):
                phases.append(
                    (kwargs["channel"], kwargs["value"], kwargs["_event_ids"])
                )

            def register_applied(self, effect, invocation, uid):
                self.uid = uid

        handler.event_lifecycle = Events()
        effect = dict(
            effect_class=47,
            parameters=[4678, 0, 1, 0],
            target_masks=[[] for _ in range(7)],
        )
        invocation = EffectInvocation(316359, 1, 1, 1, (0, 0, 0))
        return actor, fight, packets, phases, handler, effect, invocation

    def test_disabled_native_parameters_and_levels_never_mutate_book(self):
        for level in (0, 1, 200, 245):
            for parameters in ([], [4678, 0, 1, 0], [6291, 0, -32768, 200], [None]):
                (
                    actor,
                    fight,
                    packets,
                    phases,
                    handler,
                    effect,
                    invocation,
                ) = self.fixture()
                before = copy.deepcopy(vars(actor))
                effect["parameters"] = parameters
                invocation = replace(invocation, level=level)
                self.assertTrue(
                    handler(effect, {}, handler.prepare(effect, {}, invocation))
                )
                self.assertEqual(vars(actor), before)
                self.assertEqual(
                    phases, [(channel, 0, (0,)) for channel in (1, 2, 3, 4)]
                )
                self.assertEqual(fight.owned_stat_effects[101]["actual"], 0)
                self.assertEqual(packets[0][0], 12613)
                remove_disabled_spell_level(handler, 101)
                self.assertEqual(vars(actor), before)
                self.assertEqual(packets[-1][0], 13560)
                self.assertFalse(fight.owned_stat_effects)
                self.assertFalse(handler.prepared)
                self.assertFalse(handler.runners)

    def test_inherited_native_context_overrides_runner_only(self):
        from wakfu_server.combat_value_transfer import transfer_value_context

        for value in (-3, 0, 17):
            actor, fight, packets, phases, handler, effect, invocation = self.fixture()
            before = copy.deepcopy(vars(actor))
            invocation = replace(
                invocation, native_context_hex=transfer_value_context(b"", value).hex()
            )
            self.assertTrue(
                handler(effect, {}, handler.prepare(effect, {}, invocation))
            )
            self.assertEqual(fight.owned_stat_effects[101]["actual"], value)
            self.assertEqual(vars(actor), before)

    def test_unretained_still_delivers_without_owned_record(self):
        actor, fight, packets, phases, handler, effect, invocation = self.fixture(
            retained=False
        )
        self.assertTrue(handler(effect, {}, handler.prepare(effect, {}, invocation)))
        self.assertFalse(fight.owned_stat_effects)
        self.assertEqual(len(packets), 1)

    def test_guard_rejection_and_prepared_cancel_leave_state_unchanged(self):
        actor, fight, packets, phases, handler, effect, invocation = self.fixture(
            executable=False
        )
        invocation = handler.prepare(effect, {}, invocation)
        self.assertFalse(handler(effect, {}, invocation))
        self.assertFalse(packets)
        self.assertFalse(fight.owned_stat_effects)
        self.assertFalse(handler.prepared)
        actor, fight, packets, phases, handler, effect, invocation = self.fixture()
        invocation = handler.prepare(effect, {}, invocation)
        handler.cancel_prepared(invocation)
        self.assertFalse(handler.runners)
        self.assertFalse(handler.prepared)


if __name__ == "__main__":
    unittest.main()
