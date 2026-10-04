import unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_damage_handler import (
    NativeDamageHandler,
    DamageExecutionContext,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields


class DamageHandlerTests(unittest.TestCase):
    def setUp(self):
        pc = Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, 3, True)
        npc = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 5, 1)
        self.fight = Fight(
            77,
            [pc, npc],
            {pc.position, npc.position},
            {0: {pc.position}, 1: {npc.position}},
        )
        self.fight.ready(3)
        for actor in (pc, npc):
            actor.effect_stats = {92: 0, 97: 0, 100: 0}
            actor.effect_maxima = {92: 0}
            actor.effect_frozen = frozenset()
            actor.physical_radius = 0
        pc.effect_stats[100] = 15
        npc.effect_stats.update({97: 20, 92: 30})
        npc.effect_maxima[92] = 30
        self.packets = []
        self.handler = NativeDamageHandler(
            self.fight,
            self.packets,
            action_id=1,
            allocate_uid=lambda: 99,
            rng=lambda: 0.99,
            context=lambda *args: DamageExecutionContext(
                False, True, False, True, 11, False
            ),
        )
        self.effect = dict(
            effect_class=1,
            parameters=[101, 0],
            native_effect_flags=[],
            native_localization_enabled=True,
        )
        self.invocation = EffectInvocation(339483, 1, 7, -7, (1, 0, 0))

    def test_resources_and_packet_share_actual_absorption(self):
        self.assertTrue(self.handler(self.effect, {}, self.invocation))
        self.assertEqual(self.fight.actors[-7].hp, 64)
        self.assertEqual(self.fight.actors[7].effect_stats[100], 0)
        self.assertEqual(self.fight.actors[-7].effect_stats[97], 0)
        self.assertEqual(self.fight.actors[-7].effect_stats[92], 0)
        messages = {}
        fields = _identity_fields(self.packets[0][1][19:], messages=messages)
        self.assertEqual(fields[4], 101)
        self.assertEqual(
            _identity_fields(messages[8], integer_fields=(10, 19)), {10: 20, 19: 15}
        )

    def test_unavailable_context_rejects_without_mutation_or_packet(self):
        self.fight.actors[-7].effect_stats = None
        with self.assertRaises(ValueError):
            self.handler(self.effect, {}, self.invocation)
        self.assertEqual(self.fight.actors[-7].hp, 100)
        self.assertEqual(self.fight.actors[7].effect_stats[100], 15)
        self.assertEqual(self.packets, [])

    def test_unhandled_flags_are_not_silently_ignored(self):
        self.effect["native_effect_flags"] = [123]
        with self.assertRaises(ValueError):
            self.handler(self.effect, {}, self.invocation)
        self.assertEqual(self.fight.actors[-7].hp, 100)
        self.assertEqual(self.packets, [])

    def test_bypass_preserves_armor_and_barrier_but_consumes_virtual_hp(self):
        self.effect["native_effect_flags"] = [28]
        self.handler(self.effect, {}, self.invocation)
        self.assertEqual(self.fight.actors[-7].hp, 29)
        self.assertEqual(self.fight.actors[-7].effect_stats[97], 20)
        self.assertEqual(self.fight.actors[7].effect_stats[100], 15)
