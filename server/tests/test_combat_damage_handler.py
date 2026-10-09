import unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_damage_handler import (
    NativeDamageHandler,
    DamageExecutionContext,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields


class DamageHandlerTests(unittest.TestCase):
    def test_live_trigger_value_changes_application_and_wire(self):
        class Events:
            def phase(_, effect, invocation, **data):
                if data["channel"] == 2:
                    data["runner_modifier"].mutate(1, 7, True)

        self.handler.event_lifecycle = Events()
        target = self.fight.actors[self.invocation.target_id]
        before = target.hp
        self.assertTrue(self.handler(self.effect, {}, self.invocation))
        self.assertEqual(_identity_fields(self.packets[0][1][19:])[4], 7)

    def test_runner_callback_after_lifecycle_uses_value_not_hp_loss(self):
        from dataclasses import replace
        from wakfu_server.combat_runner_callbacks import runner_value_scope

        order = []

        class Events:
            def phase(_, effect, invocation, **data):
                order.append(data["channel"])

        self.handler.event_lifecycle = Events()
        with runner_value_scope(lambda inv, value: order.append(("h", value))) as token:
            inv = replace(self.invocation, native_value_scope=token)
            self.assertTrue(self.handler(self.effect, {}, inv))
        self.assertEqual(order, [2, 3, 4, ("h", 101)])
        self.assertEqual(self.fight.actors[-7].hp, 64)  # Actual HP loss36 differs.

    def test_transferred_value_overrides_calculation_before_absorption(self):
        from dataclasses import replace
        from wakfu_server.combat_value_transfer import transfer_value_context

        invocation = replace(
            self.invocation, native_context_hex=transfer_value_context(b"", 70).hex()
        )
        self.assertTrue(self.handler(self.effect, {}, invocation))
        # 70, not original101: barrier15, armor20, virtual30, HP5.
        self.assertEqual(self.fight.actors[-7].hp, 95)
        self.assertEqual(_identity_fields(self.packets[0][1][19:])[4], 70)

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

    def test_light_runner_preserves_native_family_in_packet(self):
        self.effect["effect_class"] = 1083
        self.fight.actors[7].effect_stats.update({21: 0, 22: 100, 23: 0, 24: 0})
        self.assertTrue(self.handler(self.effect, {}, self.invocation))
        fields = _identity_fields(self.packets[0][1][19:])
        import struct

        self.assertEqual(struct.unpack_from(">i", self.packets[0][1], 13)[0], 1083)
        self.assertEqual(fields[4], 202)
        self.assertEqual(self.fight.actors[-7].hp, 0)

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

    def test_live_modifier_before_calculation_and_late_modifier_not_recomputed(self):
        self.effect["parameters"] = [10, 0]
        self.fight.actors[7].effect_stats[100] = 0
        self.fight.actors[-7].effect_stats.update({97: 0, 92: 0})
        seen = []

        class Events:
            def phase(_, effect, invocation, **data):
                modifier = data["final_modifier"]
                seen.append((data["channel"], modifier, data["value"]))
                if data["channel"] in (1, 2):
                    modifier.add(50)

        self.handler.event_lifecycle = Events()
        prepared = self.handler.prepare(self.effect, {}, self.invocation)
        self.assertTrue(self.handler(self.effect, {}, prepared))
        self.assertEqual(self.fight.actors[-7].hp, 85)
        self.assertEqual([row[0] for row in seen], [1, 2, 3, 4])
        self.assertEqual(len({id(row[1]) for row in seen}), 1)
        self.assertEqual(seen[0][1].value, 100)
        self.assertEqual(self.handler.final_modifiers, {})

    def test_native_flag15_preserves_damage_packets_and_resource_mutations(self):
        from copy import deepcopy
        from wakfu_server.fight_checkpoint_store import snapshot

        baseline = deepcopy(self.fight)
        self.assertTrue(self.handler(self.effect, {}, self.invocation))
        expected = snapshot(self.fight)
        packets = tuple(self.packets)
        self.fight = baseline
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
        effect = dict(self.effect, native_effect_flags=[15])
        self.assertTrue(self.handler(effect, {}, self.invocation))
        self.assertEqual(snapshot(self.fight), expected)
        self.assertEqual(tuple(self.packets), packets)
        self.assertEqual(effect["native_effect_flags"], [15])

    def test_flag15_does_not_invent_zero_hp_lifecycle_authority(self):
        self.fight.actors[-7].hp = 0
        effect = dict(self.effect, native_effect_flags=[15])
        with self.assertRaisesRegex(ValueError, "native HP0 runner target status"):
            self.handler(effect, {}, self.invocation)
        self.assertEqual(self.packets, [])

    def test_visual_flag3_preserves_native_damage_for_all_five_elements(self):
        from copy import deepcopy
        from wakfu_server.fight_checkpoint_store import snapshot

        for family in (1, 2, 3, 4, 5):
            with self.subTest(family=family):
                self.setUp()
                self.effect["effect_class"] = family
                baseline = deepcopy(self.fight)
                self.assertTrue(self.handler(self.effect, {}, self.invocation))
                expected = snapshot(self.fight)
                packets = tuple(self.packets)
                self.fight = baseline
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
                effect = dict(self.effect, native_effect_flags=[3])
                self.assertTrue(self.handler(effect, {}, self.invocation))
                self.assertEqual(snapshot(self.fight), expected)
                self.assertEqual(tuple(self.packets), packets)
                self.assertEqual(effect["native_effect_flags"], [3])
