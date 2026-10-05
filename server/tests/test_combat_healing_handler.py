import unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_healing_handler import (
    NativeHealingHandler,
    HealingExecutionContext,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields


class HealingHandlerTests(unittest.TestCase):
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
        self.assertEqual(target.hp - before, 7)

    def test_runner_callback_after_lifecycle_includes_virtual_healing(self):
        from dataclasses import replace
        from wakfu_server.combat_runner_callbacks import runner_value_scope

        order = []

        class Events:
            def phase(_, effect, invocation, **data):
                order.append(data["channel"])

        self.handler.event_lifecycle = Events()
        with runner_value_scope(lambda inv, value: order.append(("h", value))) as token:
            self.assertTrue(
                self.handler(
                    self.effect, {}, replace(self.invocation, native_value_scope=token)
                )
            )
        self.assertEqual(order, [2, 3, 4, ("h", 25)])
        self.assertEqual(self.fight.actors[-7].hp, 100)  # HP alone gained10.

    def test_transferred_heal_overrides_calculation_before_clamping(self):
        from dataclasses import replace
        from wakfu_server.combat_value_transfer import transfer_value_context

        invocation = replace(
            self.invocation, native_context_hex=transfer_value_context(b"", 7).hex()
        )
        self.assertTrue(self.handler(self.effect, {}, invocation))
        target = self.fight.actors[-7]
        self.assertEqual((target.hp, target.effect_stats[92]), (97, 5))
        self.assertEqual(_identity_fields(self.packets[0][1][19:])[4], 7)

    def test_negative_native_base_with_transfer_reaches_wire_and_callback(self):
        from dataclasses import replace
        from wakfu_server.combat_value_transfer import transfer_value_context
        from wakfu_server.combat_runner_callbacks import runner_value_scope

        values = []
        invocation = replace(
            self.invocation, native_context_hex=transfer_value_context(b"", 7).hex()
        )
        effect = dict(self.effect, parameters=[-1, 0])
        with runner_value_scope(lambda inv, value: values.append(value)) as token:
            self.assertTrue(
                self.handler(effect, {}, replace(invocation, native_value_scope=token))
            )
        self.assertEqual(self.fight.actors[-7].hp, 97)
        self.assertEqual(values, [7])
        self.assertEqual(_identity_fields(self.packets[0][1][19:])[4], 7)

    def test_light_healing_uses_highest_elemental_mastery_and_common_consumption(self):
        source = self.fight.actors[7]
        source.effect_stats.update({21: 100, 22: 300, 109: 10000})
        effect = dict(self.effect, effect_class=1084, parameters=[5, 0])
        self.assertTrue(self.handler(effect, {}, self.invocation))
        target = self.fight.actors[-7]
        self.assertEqual((target.hp, target.effect_stats[92]), (100, 15))
        self.assertEqual(_identity_fields(self.packets[0][1][19:])[4], 20)

    def test_life_steal_native_bonus_resistance_and_actual_consumption(self):
        from dataclasses import replace
        from wakfu_server.combat_value_transfer import transfer_value_context

        source = self.fight.actors[7]
        target = self.fight.actors[-7]
        source.effect_stats[53] = 50
        target.effect_stats[32] = 200
        inv = replace(
            self.invocation, native_context_hex=transfer_value_context(b"", 10).hex()
        )
        self.assertTrue(
            self.handler(
                dict(effect_class=24, parameters=[0, 0], native_effect_flags=[29]),
                {},
                inv,
            )
        )
        self.assertEqual(target.hp, 100)
        self.assertEqual(target.effect_stats[92], 7)  # actual12:HP10+virtual2.
        self.assertEqual(_identity_fields(self.packets[0][1][19:])[4], 12)

    def test_native_ko_and_direct_loss_flags_do_not_change_living_heal(self):
        from dataclasses import replace

        self.context = replace(self.context, target_ko=False)
        effect = dict(self.effect, native_effect_flags=[4, 15, 34])
        self.assertTrue(self.handler(effect, {}, self.invocation))
        self.assertEqual(self.fight.actors[-7].hp, 100)
        self.assertEqual(_identity_fields(self.packets[0][1][19:])[4], 25)

    def test_ko_unknown_and_undead_branch_remain_guarded(self):
        from dataclasses import replace

        effect = dict(self.effect, native_effect_flags=[4, 15, 34])
        with self.assertRaisesRegex(ValueError, "KO healing authority"):
            self.handler(effect, {}, self.invocation)
        self.context = replace(self.context, target_ko=True)
        with self.assertRaisesRegex(ValueError, "KO healing lifecycle"):
            self.handler(effect, {}, self.invocation)
        self.context = replace(self.context, target_ko=False, undead=True)
        with self.assertRaisesRegex(ValueError, "undead conversion"):
            self.handler(effect, {}, self.invocation)
        self.assertEqual(self.fight.actors[-7].hp, 90)

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
