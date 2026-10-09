import unittest
from dataclasses import replace
from types import SimpleNamespace
from wakfu_server.combat_fight_property_clear import (
    NativeFightPropertyClearHandler,
    remove_fight_property_clear,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext, NativeStatHandler
from wakfu_server.combat_property_stack import clear_property
from wakfu_server.combat_value_transfer import transfer_value_context


class FightPropertyClearTests(unittest.TestCase):
    def fixture(self, *, retained=True, executable=True):
        actor = SimpleNamespace(
            id=1,
            hp=100,
            native_fight_property_counts={69: 3, 28: 2},
            native_fight_properties=frozenset((69, 28)),
        )
        fight = SimpleNamespace(
            id=4, phase="active", actors={1: actor}, owned_stat_effects={}
        )
        packets, phases = [], []
        authority = lambda *args: None
        authority.property_counts = lambda f, a: dict(a.native_fight_property_counts)
        handler = NativeFightPropertyClearHandler(
            fight,
            packets,
            action_id=5,
            allocate_uid=lambda: 101,
            context=lambda *args: StatExecutionContext(
                executable, True, None, retained, b"", None
            ),
            rng=lambda: 0,
            authority=authority,
        )

        class Events:
            def phase(self, e, i, **kwargs):
                phases.append(kwargs["channel"])

            def register_applied(self, e, i, uid):
                self.uid = uid

        handler.event_lifecycle = Events()
        effect = dict(
            effect_class=446, parameters=[69, 0], target_masks=[[] for _ in range(7)]
        )
        invocation = EffectInvocation(380044, 1, 1, 1, (0, 0, 0))
        return actor, fight, packets, phases, handler, effect, invocation

    def test_pb_clear_removes_entire_signed_counter(self):
        for count in (-128, -1, 0, 1, 2, 127):
            counts = {69: count, 28: 2}
            clear_property(counts, 69)
            self.assertEqual(counts, {28: 2})
            clear_property(counts, 69)
            self.assertEqual(counts, {28: 2})

    def test_apply_and_stat_removal_never_restore_property(self):
        for level in (0, 1, 200, 245):
            actor, fight, packets, phases, handler, effect, invocation = self.fixture()
            invocation = replace(invocation, level=level)
            self.assertTrue(
                handler(effect, {}, handler.prepare(effect, {}, invocation))
            )
            self.assertEqual(actor.native_fight_property_counts, {28: 2})
            self.assertEqual(actor.native_fight_properties, frozenset((28,)))
            self.assertEqual(actor.hp, 100)
            self.assertEqual(phases, [1, 2, 3, 4])
            self.assertEqual(packets[0][0], 12613)
            stat = NativeStatHandler(
                fight,
                packets,
                {"effects": {}},
                action_id=5,
                allocate_uid=lambda: 999,
                context=lambda *args: None,
            )
            stat.remove(101)
            self.assertEqual(actor.native_fight_property_counts, {28: 2})
            self.assertEqual(packets[-1][0], 13560)
            self.assertFalse(fight.owned_stat_effects)

    def test_context_override_and_invalid_lookup(self):
        actor, fight, packets, phases, handler, effect, invocation = self.fixture()
        invocation = replace(
            invocation, native_context_hex=transfer_value_context(b"", 28).hex()
        )
        self.assertTrue(handler(effect, {}, handler.prepare(effect, {}, invocation)))
        self.assertEqual(actor.native_fight_property_counts, {69: 3})
        actor, fight, packets, phases, handler, effect, invocation = self.fixture()
        effect["parameters"] = [2147483647, 0]
        self.assertFalse(handler(effect, {}, handler.prepare(effect, {}, invocation)))
        self.assertEqual(actor.native_fight_property_counts, {69: 3, 28: 2})
        self.assertFalse(packets)
        self.assertFalse(handler.runners)

    def test_owned_exi_collateral_contract_rejects_without_partial_clear(self):
        actor, fight, packets, phases, handler, effect, invocation = self.fixture()
        fight.owned_stat_effects[99] = dict(family="eXI", target_id=1, property_id=69)
        with self.assertRaisesRegex(ValueError, "collateral PL"):
            handler(effect, {}, handler.prepare(effect, {}, invocation))
        self.assertEqual(actor.native_fight_property_counts, {69: 3, 28: 2})
        self.assertFalse(packets)
        self.assertFalse(handler.prepared)


if __name__ == "__main__":
    unittest.main()
