import unittest
from types import SimpleNamespace as NS
from wakfu_server.combat_spell_cost_effect import NativeSpellCostHandler, modify
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_state_timing import StateTimer


class SpellCostEffectsTests(unittest.TestCase):
    def setUp(self):
        self.actor = NS(id=7, spell_ap_cost_modifiers={}, spell_range_modifiers={})
        self.fight = NS(
            id=8, phase="active", actors={7: self.actor}, owned_stat_effects={}
        )
        self.packets = []
        self.uid = 100

        def allocate():
            self.uid += 1
            return self.uid

        self.handler = NativeSpellCostHandler(
            self.fight,
            self.packets,
            action_id=1,
            allocate_uid=allocate,
            context=lambda *a: StatExecutionContext(
                True, True, None, True, None, StateTimer(7, 2, "start")
            ),
        )
        self.effect = dict(effect_class=1065, parameters=[1.0, 0.0, 8.0, 0.0])
        self.invocation = EffectInvocation(999, 1, 7, 7, (0, 0, 0))

    def test_stack_and_removal_reverse_each_owned_amount(self):
        self.assertTrue(self.handler(self.effect, [], self.invocation))
        self.assertTrue(self.handler(self.effect, [], self.invocation))
        self.assertEqual(self.actor.spell_ap_cost_modifiers, {8: -2})
        remover = NativeStatHandler(
            self.fight,
            self.packets,
            {"effects": {}},
            action_id=2,
            allocate_uid=None,
            context=None,
        )
        remover.remove(101)
        self.assertEqual(self.actor.spell_ap_cost_modifiers, {8: -1})
        remover.remove(102)
        self.assertEqual(self.actor.spell_ap_cost_modifiers, {8: 0})
        self.assertEqual([op for op, _ in self.packets], [13497, 13497, 13560, 13560])
        self.assertEqual(self.fight.owned_stat_effects, {})

    def test_category_invalid_and_unknown_snapshot_do_not_mutate(self):
        self.assertFalse(
            self.handler(
                dict(self.effect, parameters=[1.0, 0.0, 99.0, 0.0]), [], self.invocation
            )
        )
        self.assertEqual((self.uid, self.packets), (100, []))
        self.actor.spell_ap_cost_modifiers = None
        with self.assertRaises(ValueError):
            self.handler(self.effect, [], self.invocation)
        self.assertEqual((self.uid, self.packets), (100, []))

    def test_native_int_overflow_and_zero_entry(self):
        self.actor.spell_ap_cost_modifiers = {8: 2147483647}
        modify(self.actor, 8, 1)
        self.assertEqual(self.actor.spell_ap_cost_modifiers[8], -2147483648)

    def test_range_modifier_stacks_and_removal_use_separate_snapshot(self):
        effect = dict(self.effect, effect_class=1066)
        self.assertTrue(self.handler(effect, [], self.invocation))
        self.assertTrue(self.handler(effect, [], self.invocation))
        self.assertEqual(self.actor.spell_range_modifiers, {8: 2})
        self.assertEqual(self.actor.spell_ap_cost_modifiers, {})
        self.assertEqual(
            [row["family"] for row in self.fight.owned_stat_effects.values()],
            ["eZg", "eZg"],
        )

        remover = NativeStatHandler(
            self.fight,
            self.packets,
            {"effects": {}},
            action_id=2,
            allocate_uid=None,
            context=None,
        )
        remover.remove(101)
        self.assertEqual(self.actor.spell_range_modifiers, {8: 1})
        self.assertEqual(self.actor.spell_ap_cost_modifiers, {})
        remover.remove(102)
        self.assertEqual(self.actor.spell_range_modifiers, {8: 0})
        self.assertEqual(self.actor.spell_ap_cost_modifiers, {})
        self.assertEqual([op for op, _ in self.packets], [13497, 13497, 13560, 13560])

    def test_expiration_reverses_modifier_in_atomic_preview(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_timed_expiration import prepare_timed_expiration

        caster = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True)
        npc = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1)
        fight = Fight(
            8,
            [caster, npc],
            {caster.position, npc.position},
            {0: {caster.position}, 1: {npc.position}},
        )
        fight.ready(3)
        caster.spell_ap_cost_modifiers = {}
        handler = NativeSpellCostHandler(
            fight,
            [],
            action_id=1,
            allocate_uid=lambda: 101,
            context=self.handler.context,
        )
        handler(self.effect, [], self.invocation)
        early, packets = prepare_timed_expiration(
            fight,
            actor_id=7,
            round_number=1,
            phase="start",
            action_id=2,
            registry={"effects": {}},
        )
        self.assertEqual(
            (early.actors[7].spell_ap_cost_modifiers, packets), ({8: -1}, [])
        )
        preview, packets = prepare_timed_expiration(
            fight,
            actor_id=7,
            round_number=2,
            phase="start",
            action_id=2,
            registry={"effects": {}},
        )
        self.assertEqual(preview.actors[7].spell_ap_cost_modifiers, {8: 0})
        self.assertEqual(preview.owned_stat_effects, {})
        self.assertEqual([op for op, _ in packets], [13560])
        self.assertEqual(caster.spell_ap_cost_modifiers, {8: -1})

    def test_range_modifier_expiration_reverses_range_sign_and_preserves_ap(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_timed_expiration import prepare_timed_expiration

        caster = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True)
        npc = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1)
        fight = Fight(
            8,
            [caster, npc],
            {caster.position, npc.position},
            {0: {caster.position}, 1: {npc.position}},
        )
        fight.ready(3)
        caster.spell_range_modifiers = {}
        caster.spell_ap_cost_modifiers = {8: -3}
        range_effect = dict(self.effect, effect_class=1066)
        handler = NativeSpellCostHandler(
            fight,
            [],
            action_id=1,
            allocate_uid=lambda: 101,
            context=self.handler.context,
        )
        handler(range_effect, [], self.invocation)
        self.assertEqual(caster.spell_range_modifiers, {8: 1})
        self.assertEqual(caster.spell_ap_cost_modifiers, {8: -3})

        early, packets = prepare_timed_expiration(
            fight,
            actor_id=7,
            round_number=1,
            phase="start",
            action_id=2,
            registry={"effects": {}},
        )
        self.assertEqual(early.actors[7].spell_range_modifiers, {8: 1})
        self.assertEqual(early.actors[7].spell_ap_cost_modifiers, {8: -3})
        self.assertEqual(packets, [])

        preview, packets = prepare_timed_expiration(
            fight,
            actor_id=7,
            round_number=2,
            phase="start",
            action_id=2,
            registry={"effects": {}},
        )
        self.assertEqual(preview.actors[7].spell_range_modifiers, {8: 0})
        self.assertEqual(preview.actors[7].spell_ap_cost_modifiers, {8: -3})
        self.assertEqual([op for op, _ in packets], [13560])
        self.assertEqual(caster.spell_range_modifiers, {8: 1})
        self.assertEqual(caster.spell_ap_cost_modifiers, {8: -3})
