import unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_healing_handler import (
    NativeHealingHandler,
    HealingExecutionContext,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields


class HealingHandlerTests(unittest.TestCase):
    def setUp(self):
        pc = Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, 3, True)
        npc = Actor(-7, 1, (1, 0, 0), 90, 6, 3, 5, 1, max_hp=100)
        self.fight = Fight(
            77,
            [pc, npc],
            {pc.position, npc.position},
            {0: {pc.position}, 1: {npc.position}},
        )
        self.fight.ready(3)
        for actor in (pc, npc):
            actor.effect_stats = {92: 0, 97: 0, 100: 0, 32: 0}
            actor.effect_maxima = {92: 0}
            actor.effect_frozen = frozenset()
            actor.physical_radius = 0
        npc.effect_stats[92] = 5
        npc.effect_maxima[92] = 20
        self.context = HealingExecutionContext(
            False, True, False, False, 0, 0, True, 0, 1000, True
        )
        self.packets = []
        self.handler = NativeHealingHandler(
            self.fight,
            self.packets,
            action_id=1,
            allocate_uid=lambda: 99,
            context=lambda *args: self.context,
            rng=lambda: 0.99,
        )
        self.effect = dict(effect_class=25, parameters=[30, 0], native_effect_flags=[])
        self.invocation = EffectInvocation(123, 1, 7, -7, (1, 0, 0), base_uid=80)

    def test_actual_heal_virtual_hp_and_resistance_match_wire(self):
        self.assertTrue(self.handler(self.effect, {}, self.invocation))
        target = self.fight.actors[-7]
        self.assertEqual(
            (target.hp, target.effect_stats[92], target.effect_stats[32]), (100, 20, 50)
        )
        fields = _identity_fields(self.packets[0][1][19:])
        self.assertEqual((fields[4], fields[2]), (25, 80))

    def test_frozen_hp_still_heals_virtual_hp(self):
        self.fight.actors[-7].effect_frozen = frozenset({1})
        self.handler(self.effect, {}, self.invocation)
        target = self.fight.actors[-7]
        self.assertEqual(
            (target.hp, target.effect_stats[92], target.effect_stats[32]), (90, 20, 30)
        )
        self.assertEqual(_identity_fields(self.packets[0][1][19:])[4], 15)

    def test_undead_conversion_rejected_without_false_healing(self):
        from dataclasses import replace

        self.context = replace(self.context, undead=True)
        with self.assertRaises(ValueError):
            self.handler(self.effect, {}, self.invocation)
        self.assertEqual((self.fight.actors[-7].hp, self.packets), (90, []))

    def test_unknown_guards_rejected_without_mutating(self):
        from dataclasses import replace

        self.context = replace(self.context, flags_verified=False)
        with self.assertRaises(ValueError):
            self.handler(self.effect, {}, self.invocation)
        self.assertEqual((self.fight.actors[-7].hp, self.packets), (90, []))

    def test_native_flag33_allows_healing_undead(self):
        from dataclasses import replace

        self.context = replace(self.context, undead=True, bypass_undead=True)
        self.effect["native_effect_flags"] = [33]
        self.assertTrue(self.handler(self.effect, {}, self.invocation))
        self.assertEqual(self.fight.actors[-7].hp, 100)

    def test_independent_melee_and_ranged_masteries_are_applied(self):
        self.effect["parameters"] = [5, 0]
        self.effect["native_effect_flags"] = [23, 24]
        self.fight.actors[7].effect_stats.update({103: 100, 104: 200})
        self.handler(self.effect, {}, self.invocation)
        self.assertEqual(_identity_fields(self.packets[0][1][19:])[4], 20)

    def test_event_callback_observes_applied_resources_and_packet_in_order(self):
        seen = []

        def emit(effect, invocation, packet):
            seen.append(
                (
                    self.fight.actors[-7].hp,
                    self.fight.actors[-7].effect_stats[92],
                    tuple(self.packets),
                    packet,
                )
            )

        self.handler.emit_events = emit
        self.assertTrue(self.handler(self.effect, {}, self.invocation))
        self.assertEqual(seen[0][:2], (100, 20))
        self.assertEqual(seen[0][2], ((12613, seen[0][3]),))

    def test_event_failure_propagates_for_transaction_rollback(self):
        def fail(*args):
            raise RuntimeError("clone execution failed")

        self.handler.emit_events = fail
        with self.assertRaisesRegex(RuntimeError, "clone execution failed"):
            self.handler(self.effect, {}, self.invocation)
        # The caller must discard this private preview and its outbox.
        self.assertEqual(self.fight.actors[-7].hp, 100)
        self.assertEqual(len(self.packets), 1)
